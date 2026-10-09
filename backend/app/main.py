from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.core import router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Experiment, ImplementationTask, Metric
from app.templates import TEMPLATES

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", description="Human-gated product experimentation for property management teams.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")


def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Experiment).count():
            return
        triage = TEMPLATES[0]
        experiment = Experiment(name=triage["name"], template_id=triage["id"], hypothesis=triage["hypothesis"], problem_statement=triage["problem_statement"], target_metric=triage["target_metric"], stage="build", spec_approved=True, plan_approved=True, spec={"user_story": triage["user_story"], "success_metric": {"name": triage["target_metric"], "definition": "Median elapsed time from request creation to first assignment.", "guardrails": ["Error rate", "Manual reroute rate"]}, "risks": [{"risk": risk, "mitigation": "Require human review for urgent or low-confidence cases."} for risk in triage["risks"]], "acceptance_criteria": triage["acceptance_criteria"], "implementation_checklist": [], "estimated_effort": "3-5 engineering days", "design_brief": "A limited-cohort triage workflow with a visible confidence signal and human override.", "provider": "mock"})
        db.add(experiment)
        db.flush()
        for index, (title, status) in enumerate([("Map the current workflow and baseline", "done"), ("Build the triage queue and priority rules", "in_progress"), ("Instrument routing accuracy and guardrails", "todo"), ("Review with a limited coordinator cohort", "todo")]):
            db.add(ImplementationTask(experiment_id=experiment.id, title=title, description="Track the smallest measurable implementation slice.", status=status, sort_order=index))
        db.add(Metric(experiment_id=experiment.id, name="Median time to first assignment", baseline=42, observed=29, unit="min", direction="lower", sample_size=48))
        db.commit()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "proploop-api"}


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
