from datetime import datetime
from hashlib import sha256
import hmac

from fastapi import APIRouter, Body, Depends, Header, HTTPException
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

router = APIRouter()
VALID_STAGES = {"hypothesis", "design", "plan", "build", "measure", "decision", "complete", "stopped"}


def _experiment(db: Session, experiment_id: int) -> Experiment:
    item = db.scalar(select(Experiment).options(selectinload(Experiment.tasks), selectinload(Experiment.metrics), selectinload(Experiment.decisions), selectinload(Experiment.quality_records), selectinload(Experiment.assignments)).where(Experiment.id == experiment_id))
    if item is None:
        raise HTTPException(404, "Experiment not found")
    return item


def _task_dict(task: ImplementationTask) -> dict:
    return {"id": task.id, "title": task.title, "description": task.description, "status": task.status, "sort_order": task.sort_order}


def _metric_dict(metric: Metric) -> dict:
    return comparison({"id": metric.id, "name": metric.name, "baseline": metric.baseline, "observed": metric.observed, "unit": metric.unit, "direction": metric.direction, "comparison_mode": metric.comparison_mode, "sample_size": metric.sample_size, "control_sample_size": metric.control_sample_size, "treatment_sample_size": metric.treatment_sample_size})


def _decision_dict(decision: Decision) -> dict:
    return {"id": decision.id, "outcome": decision.outcome, "rationale": decision.rationale, "created_at": decision.created_at.isoformat()}


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
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "tasks": [_task_dict(task) for task in sorted(item.tasks, key=lambda value: value.sort_order)],
        "task_progress": {"completed": completed, "total": len(item.tasks)},
        "metrics": [_metric_dict(metric) for metric in item.metrics],
        "assignment_summary": assignment_summary,
        "decisions": [_decision_dict(decision) for decision in item.decisions],
    }


@router.get("/templates")
def list_templates():
    return TEMPLATES


@router.get("/experiments")
def list_experiments(db: Session = Depends(get_db)):
    items = db.scalars(select(Experiment).options(selectinload(Experiment.tasks), selectinload(Experiment.metrics), selectinload(Experiment.decisions), selectinload(Experiment.assignments)).order_by(Experiment.updated_at.desc())).all()
    return [_experiment_dict(item) for item in items]


@router.post("/experiments", status_code=201)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    template = next((item for item in TEMPLATES if item["id"] == payload.template_id), None)
    if payload.template_id and template is None:
        raise HTTPException(404, "Template not found")
    item = Experiment(**payload.model_dump())
    db.add(item)
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    return _experiment_dict(_experiment(db, experiment_id))


@router.post("/experiments/{experiment_id}/spec/generate")
def create_spec(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if item.stage not in {"hypothesis", "design", "plan"}:
        raise HTTPException(409, "Spec generation is only available before implementation")
    item.spec = generate_spec({"name": item.name, "hypothesis": item.hypothesis, "problem_statement": item.problem_statement, "target_metric": item.target_metric})
    item.spec_approved = False
    item.plan_approved = False
    item.stage = "design"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.put("/experiments/{experiment_id}/spec")
def update_spec(experiment_id: int, payload: SpecUpdate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.spec or item.spec_approved:
        raise HTTPException(409, "Generate a spec and keep it unapproved before editing")
    item.spec = payload.spec
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.post("/experiments/{experiment_id}/spec/approve")
def approve_spec(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.spec:
        raise HTTPException(409, "Generate a spec before approving it")
    item.spec_approved = True
    item.stage = "plan"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.post("/experiments/{experiment_id}/plan/approve")
def approve_plan(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.spec_approved or not item.spec:
        raise HTTPException(409, "Approve the spec before approving its task plan")
    item.plan_approved = True
    existing = list(item.tasks)
    for task in existing:
        db.delete(task)
    for index, task in enumerate(item.spec.get("implementation_checklist", [])):
        db.add(ImplementationTask(experiment_id=item.id, title=task["title"], description=task.get("description", ""), sort_order=index))
    item.stage = "build"
    db.commit()
    return _experiment_dict(_experiment(db, item.id))


@router.get("/experiments/{experiment_id}/tasks")
def list_tasks(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    return [_task_dict(task) for task in sorted(item.tasks, key=lambda value: value.sort_order)]


@router.post("/experiments/{experiment_id}/tasks", status_code=201)
def create_task(experiment_id: int, payload: TaskCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.plan_approved:
        raise HTTPException(409, "Approve the generated task plan before adding implementation tasks")
    task = ImplementationTask(experiment_id=item.id, title=payload.title, description=payload.description, sort_order=len(item.tasks))
    db.add(task)
    db.commit()
    return _task_dict(task)


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(ImplementationTask, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    if payload.status not in {"todo", "in_progress", "done"}:
        raise HTTPException(422, "Status must be todo, in_progress, or done")
    task.status = payload.status
    db.commit()
    item = _experiment(db, task.experiment_id)
    if item.tasks and all(entry.status == "done" for entry in item.tasks):
        item.stage = "decision" if item.metrics else "measure"
        db.commit()
    elif item.stage in {"measure", "decision"}:
        item.stage = "build"
        db.commit()
    return _task_dict(task)


@router.patch("/experiments/{experiment_id}/blocker")
def update_blocker(experiment_id: int, payload: BlockerUpdate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    item.blocker = payload.blocker.strip() if payload.blocker and payload.blocker.strip() else None
    db.commit()
    return {"blocker": item.blocker}


@router.post("/experiments/{experiment_id}/assignments", status_code=201)
def assign_variant(experiment_id: int, payload: AssignmentCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.plan_approved or item.stage not in {"build", "measure"}:
        raise HTTPException(409, "Approve the task plan before enrolling experiment participants")
    assignment = db.scalar(select(VariantAssignment).where(VariantAssignment.experiment_id == item.id, VariantAssignment.subject_key == payload.subject_key))
    if assignment is None:
        bucket = int(sha256(f"{item.id}:{payload.subject_key}".encode()).hexdigest()[:8], 16) % 100
        assignment = VariantAssignment(experiment_id=item.id, subject_key=payload.subject_key, variant="control" if bucket < 50 else "treatment")
        db.add(assignment)
        db.commit()
    current = _experiment(db, item.id)
    return {"subject_key": assignment.subject_key, "variant": assignment.variant, "assignment_summary": {"control": sum(entry.variant == "control" for entry in current.assignments), "treatment": sum(entry.variant == "treatment" for entry in current.assignments)}}


@router.get("/experiments/{experiment_id}/metrics")
def list_metrics(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    return [_metric_dict(metric) for metric in item.metrics]


@router.post("/experiments/{experiment_id}/metrics", status_code=201)
def add_metric(experiment_id: int, payload: MetricCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    if not item.plan_approved or item.stage not in {"build", "measure", "decision"}:
        raise HTTPException(409, "Metrics can be recorded after implementation begins")
    metric_values = payload.model_dump()
    if payload.comparison_mode == "controlled":
        control_size = sum(assignment.variant == "control" for assignment in item.assignments)
        treatment_size = sum(assignment.variant == "treatment" for assignment in item.assignments)
        if min(control_size, treatment_size) < 2:
            raise HTTPException(409, "Enroll at least two participants in each arm before recording a controlled metric")
        metric_values.update(sample_size=control_size + treatment_size, control_sample_size=control_size, treatment_sample_size=treatment_size)
    metric = Metric(experiment_id=item.id, **metric_values)
    db.add(metric)
    if item.tasks and all(task.status == "done" for task in item.tasks):
        item.stage = "decision"
    db.commit()
    return _metric_dict(metric)


@router.post("/experiments/{experiment_id}/decisions", status_code=201)
def make_decision(experiment_id: int, payload: DecisionCreate, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    outcome = payload.outcome.lower()
    if outcome not in {"ship", "iterate", "stop"}:
        raise HTTPException(422, "Decision must be ship, iterate, or stop")
    if not item.spec_approved or not item.plan_approved:
        raise HTTPException(409, "Spec and task plan approval are required before a release decision")
    if not item.tasks or any(task.status != "done" for task in item.tasks):
        raise HTTPException(409, "Complete all implementation tasks before a release decision")
    if not item.metrics:
        raise HTTPException(409, "Record at least one outcome metric before a release decision")
    decision = Decision(experiment_id=item.id, outcome=outcome, rationale=payload.rationale.strip())
    db.add(decision)
    item.stage = {"ship": "complete", "stop": "stopped", "iterate": "hypothesis"}[outcome]
    if outcome == "iterate":
        item.spec_approved = False
        item.plan_approved = False
    db.commit()
    return _decision_dict(decision)


@router.get("/experiments/{experiment_id}/quality")
def get_quality(experiment_id: int, db: Session = Depends(get_db)):
    item = _experiment(db, experiment_id)
    return [{"id": record.id, "kind": record.kind, "content": record.content, "created_at": record.created_at.isoformat()} for record in item.quality_records]


@router.get("/quality/trends")
def quality_trends(db: Session = Depends(get_db)):
    rows = db.execute(
        select(QualityRecord, Experiment.name)
        .join(Experiment, QualityRecord.experiment_id == Experiment.id)
        .where(QualityRecord.kind.in_({"coverage", "code-quality"}))
        .order_by(QualityRecord.created_at.asc(), QualityRecord.id.asc())
    ).all()
    return [{"experiment_id": record.experiment_id, "experiment_name": name, "kind": record.kind, "content": record.content, "created_at": record.created_at.isoformat()} for record, name in rows]


@router.post("/experiments/{experiment_id}/quality/{kind}", status_code=201)
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


@router.post("/quality/ingest", status_code=201)
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


@router.get("/dashboards/overview")
def overview(db: Session = Depends(get_db)):
    items = db.scalars(select(Experiment).options(selectinload(Experiment.tasks), selectinload(Experiment.metrics), selectinload(Experiment.decisions), selectinload(Experiment.assignments)).order_by(Experiment.updated_at.desc())).all()
    records = [_experiment_dict(item) for item in items]
    active = [item for item in records if item["stage"] not in {"complete", "stopped"}]
    return {
        "experiments": records,
        "summary": {
            "active": len(active), "shipped": sum(item["stage"] == "complete" for item in records),
            "needs_approval": sum(item["stage"] in {"design", "plan", "decision"} for item in records),
            "blocked": sum(bool(item["blocker"]) for item in records),
        },
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
