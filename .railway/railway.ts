import {
  defineRailway,
  github,
  postgres,
  preserve,
  project,
  service,
} from "railway/iac";

const repository = process.env.PROPLOOP_GITHUB_REPOSITORY;
if (!repository || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
  throw new Error("Set PROPLOOP_GITHUB_REPOSITORY to the pushed owner/repository before planning Railway changes.");
}

export default defineRailway(() => {
  const database = postgres("proploop-postgres-reset");
  const backend = service("backend", {
    source: github(repository, { rootDirectory: "backend" }),
    healthcheck: "/api/health",
    env: {
      DATABASE_URL: database.env.DATABASE_URL,
      PORT: "8000",
      AI_PROVIDER: preserve(),
      QUALITY_INGEST_TOKEN: preserve(),
      BOOTSTRAP_TOKEN: preserve(),
      COOKIE_SECURE: "true",
      FRONTEND_URL: preserve(),
      ANTHROPIC_API_KEY: preserve(),
      OPENAI_API_KEY: preserve(),
      GEMINI_API_KEY: preserve(),
      GITHUB_TOKEN: preserve(),
      GITHUB_REPOSITORY: preserve(),
      GITHUB_BASE_BRANCH: preserve(),
      CODING_AGENT_MODEL: preserve(),
    },
  });
  const frontend = service("frontend", {
    source: github(repository, { rootDirectory: "frontend" }),
    env: {
      BACKEND_HOST: backend.env.RAILWAY_PRIVATE_DOMAIN,
    },
  });

  return project("proploop-experiments", {
    resources: [database, backend, frontend],
  });
});
