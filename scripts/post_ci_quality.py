import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def junit_counts(path: Path) -> tuple[int, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0)) + int(suite.attrib.get("skipped", 0)) for suite in suites)
    return max(0, total - failures), total


def read_lint_diagnostics(path: Path) -> int:
    content = path.read_bytes()
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    report = json.loads(content.decode(encoding))
    return len(report.get("diagnostics", []))


def ingest():
    endpoint = os.getenv("QUALITY_INGEST_URL", "").rstrip("/")
    token = os.getenv("QUALITY_INGEST_TOKEN", "")
    experiment_id = os.getenv("EXPERIMENT_ID", "")
    if not endpoint or not token or not experiment_id:
        print("Quality upload skipped; set QUALITY_INGEST_URL, QUALITY_INGEST_TOKEN, and EXPERIMENT_ID to enable it.")
        return

    if endpoint.endswith("/api/quality/ingest"):
        url = endpoint
    elif endpoint.endswith("/api"):
        url = f"{endpoint}/quality/ingest"
    else:
        url = f"{endpoint}/api/quality/ingest"

    coverage_path = Path(os.getenv("COVERAGE_JSON", "backend/coverage.json"))
    junit_path = Path(os.getenv("JUNIT_XML", "backend/test-results.xml"))
    lint_path = Path(os.getenv("LINT_JSON", "backend/lint-results.json"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))["totals"]["percent_covered"]
    tests_passed, tests_total = junit_counts(junit_path)
    lint_issues = read_lint_diagnostics(lint_path)
    payload = {
        "experiment_id": int(experiment_id),
        "lint_issues": lint_issues,
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "coverage_after": round(float(coverage), 1),
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"Quality snapshot stored for experiment {result['experiment_id']}.")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Quality upload failed ({exc.code}): {detail}") from exc


if __name__ == "__main__":
    try:
        ingest()
    except Exception as error:
        print(f"Quality upload failed: {error}", file=sys.stderr)
        raise
