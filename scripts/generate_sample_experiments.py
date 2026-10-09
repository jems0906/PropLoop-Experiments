import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database import SessionLocal
from app.models import Experiment, ImplementationTask, Metric

SAMPLES = [
    {
        "name": "Rent delinquency reminder flow", "template_id": "rent-delinquency",
        "hypothesis": "Personalized reminders will increase on-time recovery without increasing support escalations.",
        "problem_statement": "Overdue rent outreach is inconsistent and takes staff time away from resident support.",
        "target_metric": "On-time recovery rate", "stage": "measure", "before": 61, "after": 72,
    },
    {
        "name": "Owner report summarizer", "template_id": "owner-report",
        "hypothesis": "Source-linked performance drafts will reduce monthly report preparation time.",
        "problem_statement": "Teams gather and rewrite the same property performance context every month.",
        "target_metric": "Report preparation time", "stage": "build", "before": 95, "after": 0,
    },
]

with SessionLocal() as db:
    for sample in SAMPLES:
        if db.query(Experiment).filter_by(name=sample["name"]).first():
            continue
        experiment = Experiment(**{key: sample[key] for key in ("name", "template_id", "hypothesis", "problem_statement", "target_metric", "stage")}, spec_approved=True, plan_approved=True)
        db.add(experiment)
        db.flush()
        for index, title in enumerate(["Confirm baseline data and cohort", "Build the focused workflow", "Instrument success and guardrail metrics"]):
            status = "done" if index == 0 else "todo"
            db.add(ImplementationTask(experiment_id=experiment.id, title=title, description="Sample implementation task for the experiment.", status=status, sort_order=index))
        if sample["after"]:
            db.add(Metric(experiment_id=experiment.id, name=sample["target_metric"], baseline=sample["before"], observed=sample["after"], unit="%", sample_size=140))
    db.commit()

print("Sample property-management experiments added.")
