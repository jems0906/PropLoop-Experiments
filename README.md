# PropLoop Experiments

A product experimentation workspace for property-management teams. Turn a hypothesis into a human-reviewed design brief, approved build plan, tracked implementation, before/after evidence, and a ship / iterate / stop decision.

## What is included

- Five property-management starters: maintenance triage, rent delinquency reminders, lease renewal outreach, owner reporting, and support ticket routing.
- Mock-first spec generation, with optional OpenAI, Anthropic, and Gemini adapters.
- Human gates for spec approval, task-plan approval, and release decisions.
- Editable implementation checklist, blocker reporting, and decision history.
- Metric comparison for activation, completion, simulated CSAT, time saved, and error rate. Percentage inputs include an approximate confidence indicator; teams should define their statistical design before running production experiments.
- PR review checklist, ADR template, refactor-risk heuristic, coverage tracker, release notes, and code-quality trend.
- Admin-only GitHub coding-agent flow that sends a small allowlisted source context and approved build plan to OpenAI, then opens a draft PR for human review; it never merges or claims to run tests.
- FastAPI + SQLAlchemy + SQLite locally, PostgreSQL on Railway; React + Vite + Recharts; Docker and GitHub Actions.

## Local development

Prerequisites: Python 3.12+, Node.js 22+, and npm.

1. Start the API in PowerShell:

   ```powershell
   cd backend
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload --port 8000
   ```

   The first startup creates the schema and seeds a maintenance-triage demo experiment when the database is empty. Local storage defaults to `backend/proploop.db` when launched from this folder.

2. Start the frontend in a second terminal:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

3. Open the Vite URL (normally `http://localhost:5173`). The Vite development proxy forwards `/api` to `http://127.0.0.1:8000`. API documentation is at `http://localhost:8000/docs`.

To add the other sample experiments, run `python scripts/generate_sample_experiments.py` from the repository root after installing the backend requirements. `python scripts/seed_database.py` initializes and seeds an empty database.

### Optional AI providers

Mock generation is the default and requires no API key. Set `AI_PROVIDER` to `openai`, `anthropic`, or `gemini` and provide the matching `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`. Copy `.env.example` to `backend/.env` for local settings. Do not commit credentials.

### GitHub coding agent

The admin-only coding agent is optional and disabled until all three backend variables are set: `OPENAI_API_KEY`, `GITHUB_TOKEN`, and `GITHUB_REPOSITORY` (`owner/repository`). `GITHUB_BASE_BRANCH` defaults to `main`; `CODING_AGENT_MODEL` defaults to `gpt-4o-mini`. Use a GitHub fine-grained personal access token restricted to this repository, with **Contents: read/write**, **Pull requests: read/write**, and the repository **Metadata: read** permission. Store it directly in the backend's secret variables; never put token values in source control or chat.

The agent is available only to administrators when an experiment is in the build stage with its spec and task plan approved, at least one task, and no active blocker. It reads a bounded set of allowlisted source files, screens common credential patterns, sends that context with the approved plan to OpenAI, and creates a **draft** pull request. Reviewers must inspect every generated change and CI must pass before any merge. The agent cannot execute tests, access authentication/configuration/migrations/deployment files, or merge pull requests. Even with source screening, enabling it means selected repository code and the approved plan are sent to OpenAI; do not enable it for repositories whose code cannot be shared with that provider.

## Verification

```powershell
python -m pytest backend/tests -q
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

The Playwright end-to-end suite uses a fresh local SQLite database, mock AI provider, and test-only bootstrap account. From `frontend`, install its browser once with `npx playwright install chromium`, then run `npm run test:e2e`. It covers failed and successful sign-in, the experiment lifecycle through a ship decision, the admin coding-agent readiness panel, and invitation creation/acceptance. It does not connect to Railway or call live AI/GitHub services.

## Railway deployment

Railway's current project-level configuration is in `.railway/railway.ts`; the root `railway.json` service array format is not used.

1. Push this repository to GitHub and create or select a Railway project/environment.
2. Set `PROPLOOP_GITHUB_REPOSITORY` to the pushed `owner/repository`, install dependencies with `npm install`, then link the Railway CLI with `railway login` and `railway link`.
3. Review `railway config plan`. It describes the backend and frontend services plus a Railway-managed PostgreSQL database. Apply only after reviewing the plan with `railway config apply`.
4. The backend service uses the `backend` repository root and Dockerfile; it receives `DATABASE_URL` from the managed database and applies Alembic migrations before startup. The frontend service uses `frontend` and proxies `/api` to the backend private domain.
5. Set optional AI provider keys and `QUALITY_INGEST_TOKEN` in Railway variables. To enable the coding agent, also set a repository-scoped `GITHUB_TOKEN`, `GITHUB_REPOSITORY=owner/repository`, and (optionally) `GITHUB_BASE_BRANCH` and `CODING_AGENT_MODEL`. The token must grant Contents read/write, Pull requests read/write, and Metadata read only for that repository. Set the same quality-ingest token and `QUALITY_INGEST_URL` as GitHub repository secrets to enable authenticated CI quality uploads. The backend healthcheck is `/api/health`; expose the frontend service's public domain.

Railway application of the IaC plan requires a linked Railway project and a pushed GitHub repository. Neither can be inferred from this local workspace.

## API outline

- `GET /api/templates`, `GET|POST /api/experiments`, `GET /api/experiments/{id}`
- `POST /api/experiments/{id}/spec/generate`, `PUT /api/experiments/{id}/spec`, `POST /api/experiments/{id}/spec/approve`
- `POST /api/experiments/{id}/plan/approve`, `GET|POST /api/experiments/{id}/tasks`, `PATCH /api/tasks/{id}`
- `PATCH /api/experiments/{id}/blocker`
- `GET|POST /api/experiments/{id}/metrics`, `POST /api/experiments/{id}/assignments`
- `POST /api/experiments/{id}/decisions` (requires approvals, completed tasks, and at least one metric)
- `GET /api/experiments/{id}/quality`, `POST /api/experiments/{id}/quality/{kind}`, `GET /api/quality/trends`
- `POST /api/quality/ingest` (requires `QUALITY_INGEST_TOKEN`), `GET /api/dashboards/overview`, `GET /api/health`
- `GET /api/agent/status`, `GET|POST /api/experiments/{id}/agent-runs` (administrator-only; POST requires an approved, unblocked build plan and configured providers)

## Project map

- `backend/app`: API, domain logic, providers, SQLAlchemy models, and Alembic migrations.
- `backend/tests`: lifecycle, approval, metrics, and quality API tests.
- `frontend/src`: responsive overview, experiment detail, checklist, measurement, quality views, and the admin coding-agent panel.
- `frontend/e2e`: isolated Playwright user journeys for auth, experiment decisions, and team invitations.
- `data_samples`, `scripts`: templates, sample metric data, and local seed helpers.
- `docs`: lifecycle methodology, property-management templates, quality practice, decision criteria, and architecture.
- `.railway/railway.ts`: project-level Railway IaC for backend, frontend, and PostgreSQL resources.

See [experimentation methodology](docs/experimentation_methodology.md), [property templates](docs/property_management_experiments.md), [dev-loop quality](docs/dev_loop_quality.md), [decision framework](docs/decision_framework.md), and [architecture](docs/architecture.md).
