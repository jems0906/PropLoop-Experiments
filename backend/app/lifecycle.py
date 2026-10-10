from datetime import datetime, timezone

from fastapi import HTTPException


def require_stage(experiment, *stages):
    if experiment.stage not in stages:
        raise HTTPException(409, f"This action requires stage: {', '.join(stages)}")


def record_approval(experiment, stage, user):
    if experiment.blocker:
        raise HTTPException(409, "Resolve the blocker before approving progression")
    experiment.approvals = [*experiment.approvals, {
        "stage": stage, "cycle": experiment.cycle, "reviewer_id": user.id,
        "reviewer_name": user.name, "approved_at": datetime.now(timezone.utc).isoformat(),
    }]


def has_approval(experiment, stage):
    return any(row["stage"] == stage and row["cycle"] == experiment.cycle for row in experiment.approvals)
