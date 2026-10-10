from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    template_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hypothesis: Mapped[str] = mapped_column(Text)
    problem_statement: Mapped[str] = mapped_column(Text)
    target_metric: Mapped[str] = mapped_column(String(180))
    stage: Mapped[str] = mapped_column(String(24), default="hypothesis")
    spec_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    spec: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    blocker: Mapped[str | None] = mapped_column(Text, nullable=True)
    cycle: Mapped[int] = mapped_column(Integer, default=1)
    approvals: Mapped[list] = mapped_column(JSON, default=list)
    history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    tasks: Mapped[list["ImplementationTask"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    metrics: Mapped[list["Metric"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    quality_records: Mapped[list["QualityRecord"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    assignments: Mapped[list["VariantAssignment"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    observations: Mapped[list["Observation"]] = relationship(cascade="all, delete-orphan")


class ImplementationTask(Base):
    __tablename__ = "implementation_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    experiment: Mapped[Experiment] = relationship(back_populates="tasks")


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    baseline: Mapped[float] = mapped_column(Float, default=0)
    observed: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(30), default="%")
    direction: Mapped[str] = mapped_column(String(12), default="higher")
    comparison_mode: Mapped[str] = mapped_column(String(20), default="before_after")
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    control_sample_size: Mapped[int] = mapped_column(Integer, default=0)
    treatment_sample_size: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    experiment: Mapped[Experiment] = relationship(back_populates="metrics")


class VariantAssignment(Base):
    __tablename__ = "variant_assignments"
    __table_args__ = (UniqueConstraint("experiment_id", "subject_key", name="uq_assignment_experiment_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    subject_key: Mapped[str] = mapped_column(String(128))
    variant: Mapped[str] = mapped_column(String(12))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    experiment: Mapped[Experiment] = relationship(back_populates="assignments")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    outcome: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text)
    reviewer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    experiment: Mapped[Experiment] = relationship(back_populates="decisions")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("experiment_id", "subject_key", name="uq_observation_subject"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    subject_key: Mapped[str] = mapped_column(String(128))
    exposed: Mapped[bool] = mapped_column(Boolean)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    errored: Mapped[bool] = mapped_column(Boolean, default=False)
    csat: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class QualityRecord(Base):
    __tablename__ = "quality_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    experiment: Mapped[Experiment] = relationship(back_populates="quality_records")
