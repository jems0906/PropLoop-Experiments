def build_quality_artifact(kind: str, experiment: dict, task_count: int, completed_count: int, metric_count: int, evidence: dict | None = None, previous: dict | None = None) -> dict:
    evidence = evidence or {}

    def require(*fields: str) -> None:
        missing = [field for field in fields if field not in evidence]
        if missing:
            raise ValueError(f"Measured evidence required: {', '.join(missing)}")
        if "tests_passed" in evidence and "tests_total" in evidence and evidence["tests_passed"] > evidence["tests_total"]:
            raise ValueError("tests_passed cannot exceed tests_total")

    if kind == "pr-checklist":
        return {"title": f"PR review: {experiment['name']}", "hypothesis": experiment["hypothesis"], "target_metric": experiment["target_metric"], "items": [
            "Hypothesis and acceptance criteria are reflected in the implementation",
            "Resident data is minimized and access controls are verified",
            "Failure paths, retries, and human override are tested",
            "Success and guardrail metrics are instrumented",
            "Tests cover the changed behavior and regression paths",
            "Rollout can be paused or rolled back safely",
        ]}
    if kind == "adr":
        return {"title": f"ADR: {experiment['name']}", "status": "Proposed", "context": experiment["problem_statement"], "decision": "Document the implementation choice, alternatives, and rollback path before release.", "consequences": ["Positive outcomes", "Trade-offs", "Operational risks"], "template": "Context / Decision / Alternatives / Consequences / Rollback"}
    if kind == "refactor-risk":
        require("files_changed", "lines_changed", "dependency_changes", "coverage_before", "coverage_after", "tests_passed", "tests_total")
        pass_rate = evidence["tests_passed"] / evidence["tests_total"] * 100
        scope_risk = min(30, evidence["files_changed"] * 1.2 + evidence["lines_changed"] / 75)
        dependency_risk = min(30, evidence["dependency_changes"] * 10)
        coverage_risk = min(25, max(0, evidence["coverage_before"] - evidence["coverage_after"]) * 1.5)
        test_risk = min(15, (100 - pass_rate) * 0.5)
        score = min(100, round(10 + scope_risk + dependency_risk + coverage_risk + test_risk))
        return {"score": score, "level": "High" if score >= 65 else "Moderate" if score >= 35 else "Low", "factors": {"files_changed": evidence["files_changed"], "lines_changed": evidence["lines_changed"], "dependency_changes": evidence["dependency_changes"], "coverage_before": evidence["coverage_before"], "coverage_after": evidence["coverage_after"], "test_pass_rate": round(pass_rate, 1)}, "recommendation": "Split broad changes and add focused regression tests before release." if score >= 65 else "Keep the diff scoped and verify the experiment guardrails."}
    if kind == "coverage":
        require("coverage_before", "coverage_after")
        before, after = evidence["coverage_before"], evidence["coverage_after"]
        return {"before": before, "after": after, "delta": round(after - before, 1), "source": "measured evidence"}
    if kind == "release-notes":
        return {"title": experiment["name"], "summary": experiment["hypothesis"], "why": experiment["problem_statement"], "metric": experiment["target_metric"], "tasks_completed": completed_count, "total_tasks": task_count, "decision": experiment.get("decision")}
    if kind == "code-quality":
        require("lint_issues", "tests_passed", "tests_total", "coverage_after")
        pass_rate = round(evidence["tests_passed"] / evidence["tests_total"] * 100, 1)
        snapshot = {"lint_issues": evidence["lint_issues"], "test_pass_rate": pass_rate, "coverage": evidence["coverage_after"]}
        trend = "baseline"
        if previous:
            changes = [snapshot[key] - previous[key] for key in snapshot]
            good = [changes[0] < 0, changes[1] > 0, changes[2] > 0]
            bad = [changes[0] > 0, changes[1] < 0, changes[2] < 0]
            trend = "mixed" if any(good) and any(bad) else "improving" if any(good) else "regressing" if any(bad) else "unchanged"
        return {**snapshot, "trend": trend, "tests_passed": evidence["tests_passed"], "tests_total": evidence["tests_total"], "source": "measured evidence"}
    raise ValueError("Unsupported quality artifact")
