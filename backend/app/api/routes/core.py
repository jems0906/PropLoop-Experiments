from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.config import settings
from app.measurement import comparison
from app.models import Decision, Experiment, ImplementationTask, Metric, QualityRecord, VariantAssignment
from app.quality import build_quality_artifact
from app.schemas import AssignmentCreate, BlockerUpdate, DecisionCreate, ExperimentCreate, MetricCreate, QualityEvidence, QualityIngest, SpecUpdate, TaskCreate, TaskUpdate
from app.spec_generator import generate_spec
from app.templates import TEMPLATES
from app.auth import current_user, reviewer, require_same_origin
from app.lifecycle import has_approval, record_approval, require_stage
from app.outcomes import computed_metrics
from app.models import Observation
from app.schemas import ObservationCreate

def protect_requests(request: Request, user=Depends(current_user)):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_same_origin(request, user)


router = APIRouter(dependencies=[Depends(protect_requests)])
ci_router = APIRouter()
VALID_STAGES = {"hypothesis", "design", "plan", "build", "measure", "decision", "complete", "stopped"}


def _experiment(db: Session, experiment_id: int) -> Experiment:
    item = db.scalar(select(Experiment).options(selectinload(Experiment.tasks), selectinload(Experiment.metrics), selectinload(Experiment.decisions), selectinload(Experiment.quality_records), selectinload(Experiment.assignments), selectinload(Experiment.observations)).where(Experiment.id == experiment_id).with_for_update().execution_options(populate_existing=True))
    if item is None:
        raise HTTPException(404, "Experiment not found")
    return item


def _task_dict(task: ImplementationTask) -> dict:
    return {"id": task.id, "title": task.title, "description": task.description, "status": task.status, "sort_order": task.sort_order}


def _metric_dict(metric: Metric) -> dict:
    return comparison({"id": metric.id, "name": metric.name, "baseline": metric.baseline, "observed": metric.observed, "unit": metric.unit, "direction": metric.direction, "comparison_mode": metric.comparison_mode, "sample_size": metric.sample_size, "control_sample_size": metric.control_sample_size, "treatment_sample_size": metric.treatment_sample_size})


def _decision_dict(decision: Decision) -> dict:
    return {"id": decision.id, "outcome": decision.outcome, "rationale": decision.rationale, "reviewer_id": decision.reviewer_id, "reviewer_name": decision.reviewer_name, "created_at": decision.created_at.isoformat()}


def _experiment_dict(item: Experiment) -> dict:
    completed = sum(task.status == "done" for task in item.tasks)
    assignment_summary = {
        "control": sum(assignment.variant == "control" for assignment in item.assignments),
        "treatment": sum(assignment.variant == "treatment" for assignment in item.assignments),
    }
    return {
        "id": item.id, "name": item.name, "template_id": item.template_id,
        "hypothesis": item.hypothesis, "problem_statement": item.problem_statement,
        "target_metric": item.target_metric, "stage": item.stage,
        "spec_approved": item.spec_approved, "plan_approved": item.plan_approved,
        "spec": item.spec, "blocker": item.blocker,
        "cycle": item.cycle, "approvals": item.approvals, "history": item.history,
        "computed_metrics": computed_metrics(item),
        "observations": [{"subject_key": row.subject_key, "exposed": row.exposed, "completed": row.completed, "errored": row.errored, "csat": row.csat, "duration_minutes": row.duration_minutes} for row in item.observations],
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "tasks": [_task_dict(task) for task in sorted(item.tasks, key=lambda value: value.sort_order)],
        "task_progress": {"completed": completed, "total": len(item.tasks)},
        "metrics": [_metric_dict(metric) for metric in item.metrics],
        "assignment_summary": assignment_summary,
        "decisions": [_decision_dict(decision) for decision in item.decisions],
    }


@router.get("/templates", dependencies=[Depends(current_user)])
def list_templates():
    return TEMPLATES


@router.get("/experiments", dependencies=[Depends(current_user)])
def list_experiments(db: Session = Depends(get_db)):
    items = db.scalars(select(Experiment).options(selectinload(Experiment.tasks), selectinload(Experiment.metrics), selectinload(Experiment.decisions), selectinload(Experiment.assignments), selectinload(Experiment.observations)).order_by(Experiment.updated_at.desc())).all()
    return [_experiment_dict(item) for item in items]


@router.post("/experiments", status_code=201, dependencies=[Depends(current_user)])
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    template = next((item for item in TEMPLATES if item["id"] == payload.template_id), None)
    if payload.template_id and template is None:
        raise HTTPException(404, "Template not found")
    item = Experiment(**payload.model_dump())
    db.add(item)
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.get("/experiments/{experiment_id}", dependencies=[Depends(current_user)])
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    return _experiment_dict(_experiment(db, experiment_id))


@router.post("/experiments/{experiment_id}/hypothesis/approve")
def approve_hypothesis(experiment_id: int, user=Depends(reviewer), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "hypothesis")
    if has_approval(item, "hypothesis"):
        raise HTTPException(409, "Hypothesis already approved")
    record_approval(item, "hypothesis", user)
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.put("/experiments/{experiment_id}/brief")
def update_brief(experiment_id: int, payload: ExperimentCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "hypothesis")
    if has_approval(item, "hypothesis"):
        raise HTTPException(409, "Approved hypothesis is locked")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.post("/experiments/{experiment_id}/spec/generate", dependencies=[Depends(current_user)])
def create_spec(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "hypothesis", "design")
    if not has_approval(item, "hypothesis"):
        raise HTTPException(409, "Approve the hypothesis before generating its design brief")
    item.spec = generate_spec({"name": item.name, "hypothesis": item.hypothesis, "problem_statement": item.problem_statement, "target_metric": item.target_metric})
    item.spec_approved = False
    item.plan_approved = False
    item.stage = "design"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.put("/experiments/{experiment_id}/spec", dependencies=[Depends(current_user)])
def update_spec(experiment_id: int, payload: SpecUpdate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.spec:
        raise HTTPException(409, "Generate a spec before editing")
    require_stage(item, "design", "plan")
    if item.stage == "plan":
        editable = {"implementation_checklist", "estimated_effort"}
        if any(value != item.spec.get(key) for key, value in payload.spec.model_dump().items() if key not in editable):
            raise HTTPException(409, "Approved design fields are locked; only tasks and effort remain editable")
    item.spec = payload.spec.model_dump()
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.post("/experiments/{experiment_id}/spec/approve")
def approve_spec(experiment_id: int, user=Depends(reviewer), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "design")
    if not item.spec:
        raise HTTPException(409, "Generate a spec before approving it")
    item.spec_approved = True
    record_approval(item, "design", user)
    item.stage = "plan"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.post("/experiments/{experiment_id}/plan/approve")
def approve_plan(experiment_id: int, user=Depends(reviewer), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "plan")
    if not item.spec_approved or not item.spec:
        raise HTTPException(409, "Approve the spec before approving its task plan")
    item.plan_approved = True
    if not item.spec.get("implementation_checklist"):
        raise HTTPException(409, "A plan must contain implementation tasks")
    record_approval(item, "plan", user)
    existing = list(item.tasks)
    for task in existing:
        db.delete(task)
    for index, task in enumerate(item.spec.get("implementation_checklist", [])):
        db.add(ImplementationTask(experiment_id=item.id, title=task["title"], description=task.get("description", ""), sort_order=index))
    item.stage = "build"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.get("/experiments/{experiment_id}/tasks", dependencies=[Depends(current_user)])
def list_tasks(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    return [_task_dict(task) for task in sorted(item.tasks, key=lambda value: value.sort_order)]


@router.post("/experiments/{experiment_id}/tasks", status_code=201, dependencies=[Depends(current_user)])
def create_task(experiment_id: int, payload: TaskCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "build")
    if not item.plan_approved:
        raise HTTPException(409, "Approve the generated task plan before adding implementation tasks")
    task = ImplementationTask(experiment_id=item.id, title=payload.title, description=payload.description, sort_order=len(item.tasks))
    db.add(task)
    db.commit()
    return _task_dict(task)


@router.patch("/tasks/{task_id}", dependencies=[Depends(current_user)])
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(ImplementationTask, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    if payload.status not in {"todo", "in_progress", "done"}:
        raise HTTPException(422, "Status must be todo, in_progress, or done")
    item = _experiment(db, task.experiment_id)
    require_stage(item, "build")
    task.status = payload.status
    db.commit()
    return _task_dict(task)


@router.patch("/experiments/{experiment_id}/blocker", dependencies=[Depends(current_user)])
def update_blocker(experiment_id: int, payload: BlockerUpdate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if item.stage in {"complete", "stopped"}:
        raise HTTPException(409, "Closed experiments are read-only")
    item.blocker = payload.blocker.strip() if payload.blocker and payload.blocker.strip() else None
    db.commit()
    return {"blocker": item.blocker}


@router.post("/experiments/{experiment_id}/assignments", status_code=201, dependencies=[Depends(current_user)])
def assign_variant(experiment_id: int, payload: AssignmentCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.plan_approved or item.stage not in {"build", "measure"}:
        raise HTTPException(409, "Approve the task plan before enrolling experiment participants")
    assignment = db.scalar(select(VariantAssignment).where(VariantAssignment.experiment_id == item.id, VariantAssignment.subject_key == payload.subject_key))
    if assignment is None:
        bucket = int(sha256(f"{item.id}:{item.cycle}:{payload.subject_key}".encode()).hexdigest()[:8], 16) % 100
        assignment = VariantAssignment(experiment_id=item.id, subject_key=payload.subject_key, variant="control" if bucket < 50 else "treatment")
        db.add(assignment)
        db.commit()
    current = _experiment(db, item.id)
    return {"subject_key": assignment.subject_key, "variant": assignment.variant, "assignment_summary": {"control": sum(entry.variant == "control" for entry in current.assignments), "treatment": sum(entry.variant == "treatment" for entry in current.assignments)}}


@router.post("/experiments/{experiment_id}/build/approve")
def approve_build(experiment_id: int, user=Depends(reviewer), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "build")
    if not item.tasks or any(task.status != "done" for task in item.tasks):
        raise HTTPException(409, "Complete the checklist before approving build")
    record_approval(item, "build", user)
    item.stage = "measure"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.put("/experiments/{experiment_id}/observations/{subject_key}", dependencies=[Depends(current_user)])
def observe(experiment_id: int, subject_key: str, payload: ObservationCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "measure")
    if not any(row.subject_key == subject_key for row in item.assignments):
        raise HTTPException(404, "Enroll this participant before recording exposure and outcomes")
    row = next((row for row in item.observations if row.subject_key == subject_key), None)
    if row is None:
        row = Observation(experiment_id=item.id, subject_key=subject_key, **payload.model_dump())
        db.add(row)
    else:
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.post("/experiments/{experiment_id}/measure/approve")
def approve_measurement(experiment_id: int, user=Depends(reviewer), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "measure")
    if not item.metrics and not any(row.exposed for row in item.observations):
        raise HTTPException(409, "Record measured results before approving measurement")
    record_approval(item, "measure", user)
    item.stage = "decision"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.get("/experiments/{experiment_id}/metrics", dependencies=[Depends(current_user)])
def list_metrics(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    return [_metric_dict(metric) for metric in item.metrics]


@router.post("/experiments/{experiment_id}/metrics", status_code=201, dependencies=[Depends(current_user)])
def add_metric(experiment_id: int, payload: MetricCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "measure")
    metric_values = payload.model_dump()
    if payload.comparison_mode == "controlled":
        raise HTTPException(422, "Controlled metrics are computed from participant observations, not manually entered percentages")
    metric = Metric(experiment_id=item.id, **metric_values)
    db.add(metric)
    db.commit()
    return _metric_dict(metric)


@router.post("/experiments/{experiment_id}/decisions", status_code=201)
def make_decision(experiment_id: int, payload: DecisionCreate, user=Depends(reviewer), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    require_stage(item, "decision")
    outcome = payload.outcome.lower()
    if outcome not in {"ship", "iterate", "stop"}:
        raise HTTPException(422, "Decision must be ship, iterate, or stop")
    if not item.spec_approved or not item.plan_approved:
        raise HTTPException(409, "Spec and task plan approval are required before a release decision")
    if not item.tasks or any(task.status != "done" for task in item.tasks):
        raise HTTPException(409, "Complete all implementation tasks before a release decision")
    if not item.metrics and not item.observations:
        raise HTTPException(409, "Record at least one outcome metric before a release decision")
    record_approval(item, "decision", user)
    decision = Decision(experiment_id=item.id, outcome=outcome, rationale=payload.rationale.strip(), reviewer_id=user.id, reviewer_name=user.name)
    db.add(decision)
    db.flush()
    db.refresh(item, attribute_names=["decisions"])
    if outcome == "iterate":
        item.history = [*item.history, {"cycle": item.cycle, "snapshot": _experiment_dict(item) | {"history": []}, "outcome": outcome, "rationale": payload.rationale.strip(), "archived_at": datetime.now(timezone.utc).isoformat()}]
        item.cycle += 1
        for row in [*item.tasks, *item.metrics, *item.assignments, *item.observations]:
            db.delete(row)
        item.spec = None
        item.spec_approved = False
        item.plan_approved = False
    item.stage = {"ship": "complete", "stop": "stopped", "iterate": "hypothesis"}[outcome]
    db.commit()
    return _decision_dict(decision)


@router.get("/experiments/{experiment_id}/quality", dependencies=[Depends(current_user)])
def get_quality(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    return [{"id": record.id, "kind": record.kind, "content": record.content, "created_at": record.created_at.isoformat()} for record in item.quality_records]


@router.get("/quality/trends", dependencies=[Depends(current_user)])
def quality_trends(db: Session = Depends(get_db)):
    rows = db.execute(
        select(QualityRecord, Experiment.name)
        .join(Experiment, QualityRecord.experiment_id == Experiment.id)
        .where(QualityRecord.kind.in_({"coverage", "code-quality"}))
        .order_by(QualityRecord.created_at.asc(), QualityRecord.id.asc())
    ).all()
    return [{"experiment_id": record.experiment_id, "experiment_name": name, "kind": record.kind, "content": record.content, "created_at": record.created_at.isoformat()} for record, name in rows]


@router.post("/experiments/{experiment_id}/quality/{kind}", status_code=201, dependencies=[Depends(current_user)])
def generate_quality(experiment_id: int, kind: str, payload: QualityEvidence = Body(default=QualityEvidence()), db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if kind not in {"pr-checklist", "adr", "refactor-risk", "coverage", "release-notes", "code-quality"}:
        raise HTTPException(404, "Quality tool not found")
    completed = sum(task.status == "done" for task in item.tasks)
    previous = None
    if kind == "code-quality":
        previous_record = db.scalar(select(QualityRecord).where(QualityRecord.experiment_id == item.id, QualityRecord.kind == kind).order_by(QualityRecord.created_at.desc(), QualityRecord.id.desc()).limit(1))
        previous = previous_record.content if previous_record else None
    try:
        content = build_quality_artifact(kind, {"name": item.name, "hypothesis": item.hypothesis, "problem_statement": item.problem_statement, "target_metric": item.target_metric, "decision": item.decisions[-1].outcome if item.decisions else None}, len(item.tasks), completed, len(item.metrics), payload.model_dump(exclude_none=True), previous)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record = QualityRecord(experiment_id=item.id, kind=kind, content=content)
    db.add(record)
    db.commit()
    return {"id": record.id, "kind": record.kind, "content": record.content, "created_at": record.created_at.isoformat()}


@ci_router.post("/quality/ingest", status_code=201)
def ingest_quality(payload: QualityIngest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    expected = f"Bearer {settings.quality_ingest_token}" if settings.quality_ingest_token else ""
    if not expected:
        raise HTTPException(503, "CI quality ingestion is disabled until QUALITY_INGEST_TOKEN is configured")
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(401, "A valid CI quality-ingestion bearer token is required")
    item = _experiment(db, payload.experiment_id)
    previous_record = db.scalar(select(QualityRecord).where(QualityRecord.experiment_id == item.id, QualityRecord.kind == "code-quality").order_by(QualityRecord.created_at.desc(), QualityRecord.id.desc()).limit(1))
    evidence = payload.model_dump(exclude={"experiment_id"}, exclude_none=True)
    content = build_quality_artifact("code-quality", {"name": item.name, "hypothesis": item.hypothesis, "problem_statement": item.problem_statement, "target_metric": item.target_metric}, len(item.tasks), sum(task.status == "done" for task in item.tasks), len(item.metrics), evidence, previous_record.content if previous_record else None)
    record = QualityRecord(experiment_id=item.id, kind="code-quality", content=content)
    db.add(record)
    db.commit()
    return {"id": record.id, "experiment_id": item.id, "kind": record.kind, "content": record.content, "created_at": record.created_at.isoformat()}


@router.get("/dashboards/overview", dependencies=[Depends(current_user)])
def overview(db: Session = Depends(get_db)):
    items = db.scalars(select(Experiment).options(selectinload(Experiment.tasks), selectinload(Experiment.metrics), selectinload(Experiment.decisions), selectinload(Experiment.assignments), selectinload(Experiment.observations)).order_by(Experiment.updated_at.desc())).all()
    records = [_experiment_dict(item) for item in items]
    active = [item for item in records if item["stage"] not in {"complete", "stopped"}]
    return {
        "experiments": records,
        "summary": {
            "active": len(active), "shipped": sum(item["stage"] == "complete" for item in records),
            "needs_approval": sum(item["stage"] in {"design", "plan", "decision"} for item in records),
            "blocked": sum(bool(item["blocker"]) for item in records),
        },
        "trend": _trend(items),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _trend(items):
    today = datetime.now(timezone.utc)
    start = today - timedelta(days=today.weekday())
    weeks = []
    for offset in range(4, -1, -1):
        since = (start - timedelta(weeks=offset)).date()
        until = since + timedelta(days=7)
        created = [item for item in items if since <= item.created_at.date() < until]
        shipped = sum(decision.outcome == "ship" and since <= decision.created_at.date() < until for item in items for decision in item.decisions)
        weeks.append({"week": since.isoformat(), "active": len(created), "shipped": shipped})
    return weeks
