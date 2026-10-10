import math
from statistics import mean, variance

from scipy.stats import fisher_exact, t


def binary_confidence(control, treatment):
    if not control or not treatment:
        return {"label": "Insufficient data", "significant": False, "p_value": None}
    result = fisher_exact([[sum(control), len(control) - sum(control)], [sum(treatment), len(treatment) - sum(treatment)]])
    significant = bool(result.pvalue < 0.05)
    return {"label": "Significant" if significant else "Directional", "significant": significant, "p_value": round(float(result.pvalue), 6), "method": "Fisher exact, two-sided"}


def continuous_confidence(control, treatment):
    if min(len(control), len(treatment)) < 2:
        return {"label": "Insufficient data", "significant": False, "p_value": None}
    a, b = variance(control) / len(control), variance(treatment) / len(treatment)
    if a + b == 0:
        return {"label": "Zero variance; inference unavailable", "significant": False, "p_value": None}
    df = (a + b) ** 2 / (a ** 2 / (len(control) - 1) + b ** 2 / (len(treatment) - 1))
    difference = mean(treatment) - mean(control)
    se = math.sqrt(a + b)
    p_value = float(2 * t.sf(abs(difference / se), df))
    margin = float(t.ppf(0.975, df) * se)
    return {"label": "Significant" if p_value < 0.05 else "Directional", "significant": p_value < 0.05, "p_value": round(p_value, 6), "method": "Welch t-test, two-sided", "difference_interval_95": [round(difference - margin, 3), round(difference + margin, 3)]}


def computed_metrics(experiment):
    by_subject = {row.subject_key: row for row in experiment.observations}
    groups = {"control": [], "treatment": []}
    for assignment in experiment.assignments:
        groups[assignment.variant].append(by_subject.get(assignment.subject_key))
    metrics = []
    definitions = [
        ("Activation rate", "%", "higher", lambda rows: [int(bool(row and row.exposed)) for row in rows], True),
        ("Task completion rate", "%", "higher", lambda rows: [int(row.completed) for row in rows if row and row.exposed], True),
        ("Simulated CSAT", "score", "higher", lambda rows: [row.csat for row in rows if row and row.exposed and row.csat is not None], False),
        ("Task duration", "min", "lower", lambda rows: [row.duration_minutes for row in rows if row and row.exposed and row.duration_minutes is not None], False),
        ("Error rate", "%", "lower", lambda rows: [int(row.errored) for row in rows if row and row.exposed], True),
    ]
    for index, (name, unit, direction, extract, binary) in enumerate(definitions):
        control, treatment = extract(groups["control"]), extract(groups["treatment"])
        before = mean(control) * (100 if binary else 1) if control else None
        after = mean(treatment) * (100 if binary else 1) if treatment else None
        change = after - before if before is not None and after is not None else None
        confidence = binary_confidence(control, treatment) if binary else continuous_confidence(control, treatment)
        metrics.append({
            "id": f"computed-{index}", "name": name, "baseline": round(before, 3) if before is not None else None,
            "observed": round(after, 3) if after is not None else None, "unit": unit, "direction": direction,
            "comparison_mode": "controlled", "control_sample_size": len(control), "treatment_sample_size": len(treatment),
            "change": round(change, 3) if change is not None else None,
            "relative_change": round(change / abs(before) * 100, 1) if change is not None and before else None,
            "improved": (change >= 0 if direction == "higher" else change <= 0) if change is not None else None,
            "time_saved_minutes": round(-change, 3) if name == "Task duration" and change is not None else None,
            "confidence": confidence, "source": "participant observations",
        })
    return metrics
