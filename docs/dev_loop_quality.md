# Development-Loop Quality

The quality workspace generates review artifacts for each experiment:

- **PR checklist:** hypothesis and acceptance-criteria coverage, data handling, retries, instrumentation, tests, rollback.
- **ADR template:** context, decision, alternatives, consequences, and rollback notes.
- **Refactor risk:** a lightweight score from changed files/lines, dependency changes, coverage delta, and test pass rate. Enter measured review or CI values; it is a prompt for review, not an automated approval.
- **Coverage tracker:** before/after display from supplied CI/review measurements.
- **Release notes:** summarizes the problem, hypothesis, metric, task completion, and decision.
- **Code quality trend:** persists measured lint issues, test pass rate, and coverage snapshots across experiments.

## Optional GitHub Actions upload

Set backend `QUALITY_INGEST_TOKEN` and repository secrets `QUALITY_INGEST_URL` (backend base URL or `/api` URL) and `QUALITY_INGEST_TOKEN`. Run the CI workflow manually with an experiment ID. It uploads JUnit test counts, Python coverage, and the clean Oxlint result to the authenticated quality-ingest endpoint. Push and pull-request CI runs still test/build only and do not upload experiment data.

## Suggested review loop

Run lint and targeted tests before the full suite. Review the diff against the accepted spec. Check migration compatibility and failure modes. Keep release notes tied to the experiment rationale. Only ingest values produced by CI or an explicitly reviewed measurement; the application does not synthesize coverage or test results.
