import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import admin, require_same_origin
from app.coding_agent import configuration_status, create_agent_pull_request
from app.database import get_db
from app.models import AgentRun, Experiment

router = APIRouter()
logger = logging.getLogger(__name__)


def _run_dict(run: AgentRun) -> dict:
    return {
        "id": run.id,
        "experiment_id": run.experiment_id,
        "status": run.status,
        "repository": run.repository,
        "branch": run.branch,
        "pull_request_url": run.pull_request_url,
        "summary": run.summary,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/agent/status")
def agent_status(user=Depends(admin)) -> dict:
    return configuration_status()


@router.get("/experiments/{experiment_id}/agent-runs")
def list_agent_runs(experiment_id: int, user=Depends(admin), db: Session = Depends(get_db)) -> list[dict]:
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(404, "Experiment not found")
    rows = db.scalars(
        select(AgentRun).where(AgentRun.experiment_id == experiment_id)
        .order_by(AgentRun.id.desc()).limit(20)
    )
    return [_run_dict(run) for run in rows]


@router.post(
    "/experiments/{experiment_id}/agent-runs",
    status_code=201,
    dependencies=[Depends(require_same_origin)],
)
def create_agent_run(
    experiment_id: int,
    user=Depends(admin),
    db: Session = Depends(get_db),
) -> dict:
    item = db.scalar(
        select(Experiment).options(selectinload(Experiment.tasks))
        .where(Experiment.id == experiment_id)
    )
    if item is None:
        raise HTTPException(404, "Experiment not found")
    if item.stage != "build" or not item.plan_approved or not item.spec_approved:
        raise HTTPException(409, "Approve the experiment brief and task plan before requesting an implementation PR")
    if item.blocker:
        raise HTTPException(409, "Resolve the experiment blocker before requesting an implementation PR")
    if not item.tasks:
        raise HTTPException(409, "The approved implementation plan has no tasks")

    status = configuration_status()
    if not status["enabled"]:
        raise HTTPException(503, "GitHub coding agent is not configured: " + ", ".join(status["missing"]))

    run = AgentRun(
        experiment_id=item.id,
        requested_by=user.id,
        status="running",
        repository=status.get("repository") or "configured-repository",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    experiment = {
        "id": item.id,
        "name": item.name,
        "hypothesis": item.hypothesis,
        "problem_statement": item.problem_statement,
        "target_metric": item.target_metric,
        "approved_spec": item.spec,
    }
    tasks = [
        {"title": task.title, "description": task.description}
        for task in sorted(item.tasks, key=lambda row: row.sort_order)
    ]
    try:
        result = create_agent_pull_request(experiment, tasks, run.id)
    except HTTPException as exc:
        run.status = "failed"
        run.error = exc.detail[:300] if isinstance(exc.detail, str) else "Coding agent request failed."
        db.commit()
        raise
    except Exception as exc:
        logger.error("Coding agent run %s failed unexpectedly (%s)", run.id, type(exc).__name__)
        run.status = "failed"
        run.error = "Coding agent request failed unexpectedly."
        db.commit()
        raise HTTPException(502, run.error) from exc
    run.status = "pull_request"
    run.repository = result["repository"]
    run.branch = result["branch"]
    run.pull_request_url = result["pull_request_url"]
    run.summary = result["summary"]
    db.commit()
    db.refresh(run)
    return _run_dict(run)
