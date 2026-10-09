import math


def confidence_for_metric(
    baseline: float,
    observed: float,
    unit: str,
    control_sample_size: int,
    treatment_sample_size: int | None = None,
) -> dict:
    """Estimate significance for percentage outcomes using unequal arm sizes when provided."""
    treatment_sample_size = treatment_sample_size or control_sample_size
    if unit != "%" or min(control_sample_size, treatment_sample_size) < 2 or baseline < 0 or observed < 0 or baseline > 100 or observed > 100:
        return {"label": "Insufficient data", "confidence": None, "significant": False}
    p1, p2 = baseline / 100, observed / 100
    pooled = (p1 * control_sample_size + p2 * treatment_sample_size) / (control_sample_size + treatment_sample_size)
    standard_error = math.sqrt(max(pooled * (1 - pooled) * (1 / control_sample_size + 1 / treatment_sample_size), 1e-12))
    z_score = abs(p2 - p1) / standard_error
    p_value = math.erfc(z_score / math.sqrt(2))
    confidence = round((1 - p_value) * 100, 1)
    return {
        "label": "High confidence" if p_value < 0.05 else "Directional",
        "confidence": confidence,
        "significant": p_value < 0.05,
        "p_value": round(p_value, 4),
        "z_score": round(z_score, 2),
    }


def comparison(metric: dict) -> dict:
    baseline = metric["baseline"]
    observed = metric["observed"]
    change = observed - baseline
    relative = (change / abs(baseline) * 100) if baseline else None
    direction = metric.get("direction", "higher")
    control_size = metric.get("control_sample_size") or metric["sample_size"]
    treatment_size = metric.get("treatment_sample_size") or metric["sample_size"]
    return {
        **metric,
        "improved": change >= 0 if direction == "higher" else change <= 0,
        "change": round(change, 2),
        "relative_change": round(relative, 1) if relative is not None else None,
        "confidence": confidence_for_metric(baseline, observed, metric["unit"], control_size, treatment_size),
    }
