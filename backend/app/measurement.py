def comparison(metric: dict) -> dict:
    baseline = metric["baseline"]
    observed = metric["observed"]
    change = observed - baseline
    relative = (change / abs(baseline) * 100) if baseline else None
    direction = metric.get("direction", "higher")
    return {
        **metric,
        "improved": change >= 0 if direction == "higher" else change <= 0,
        "change": round(change, 2),
        "relative_change": round(relative, 1) if relative is not None else None,
        "confidence": {"label": "Descriptive legacy controlled result; no validated outcomes" if metric.get("comparison_mode") == "controlled" else "Descriptive before/after; no causal significance", "confidence": None, "significant": False},
    }
