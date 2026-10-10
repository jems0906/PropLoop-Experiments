import json
from pathlib import Path
import runpy
from unittest.mock import MagicMock, patch


def test_ci_uploader_sends_measured_evidence(tmp_path, monkeypatch):
    reports = {
        "COVERAGE_JSON": ("coverage.json", json.dumps({"totals": {"percent_covered": 82.25}})),
        "JUNIT_XML": ("junit.xml", '<testsuites><testsuite tests="20" failures="1" errors="1" skipped="2"/></testsuites>'),
        "LINT_JSON": ("lint.json", json.dumps({"diagnostics": [{"message": "one finding"}]})),
    }
    for variable, (name, data) in reports.items():
        path = tmp_path / name
        path.write_text(data, encoding="utf-8")
        monkeypatch.setenv(variable, str(path))
    monkeypatch.setenv("QUALITY_INGEST_URL", "https://example.test/api")
    monkeypatch.setenv("QUALITY_INGEST_TOKEN", "test-only-ci-token")
    monkeypatch.setenv("EXPERIMENT_ID", "7")
    script = Path(__file__).parents[2] / "scripts" / "post_ci_quality.py"
    upload = runpy.run_path(str(script))["ingest"]
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"experiment_id": 7}'
    with patch("urllib.request.urlopen", return_value=response) as open_url:
        upload()
    request = open_url.call_args.args[0]
    assert request.full_url == "https://example.test/api/quality/ingest"
    assert request.get_header("Authorization") == "Bearer test-only-ci-token"
    assert json.loads(request.data) == {
        "experiment_id": 7, "coverage_after": 82.2, "tests_passed": 16,
        "tests_total": 20, "lint_issues": 1,
    }
