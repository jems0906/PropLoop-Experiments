from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    hypothesis: str = Field(min_length=10)
    problem_statement: str = Field(min_length=10)
    target_metric: str = Field(min_length=2, max_length=180)
    template_id: str | None = None


class DecisionCreate(BaseModel):
    outcome: str
    rationale: str = Field(min_length=8)


class SpecUpdate(BaseModel):
    spec: dict


class MetricCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    baseline: float
    observed: float
    unit: str = "%"
    direction: Literal["higher", "lower"] = "higher"
    comparison_mode: Literal["before_after", "controlled"] = "before_after"
    sample_size: int = Field(default=100, ge=1)


class AssignmentCreate(BaseModel):
    subject_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class QualityEvidence(BaseModel):
    files_changed: int | None = Field(default=None, ge=0)
    lines_changed: int | None = Field(default=None, ge=0)
    dependency_changes: int | None = Field(default=None, ge=0)
    coverage_before: float | None = Field(default=None, ge=0, le=100)
    coverage_after: float | None = Field(default=None, ge=0, le=100)
    lint_issues: int | None = Field(default=None, ge=0)
    tests_passed: int | None = Field(default=None, ge=0)
    tests_total: int | None = Field(default=None, ge=1)


class QualityIngest(QualityEvidence):
    experiment_id: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_test_counts(self):
        if self.tests_passed is not None and self.tests_total is not None and self.tests_passed > self.tests_total:
            raise ValueError("tests_passed cannot exceed tests_total")
        return self


class TaskUpdate(BaseModel):
    status: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    description: str = ""


class BlockerUpdate(BaseModel):
    blocker: str | None = None
