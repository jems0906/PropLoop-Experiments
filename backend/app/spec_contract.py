from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonemptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DraftTask(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=1, max_length=2000)


class DraftRisk(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    risk: str = Field(min_length=3)
    mitigation: str = Field(min_length=3)


class SuccessMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=180)
    definition: str = Field(min_length=10)
    guardrails: list[NonemptyText] = Field(min_length=1)


class ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    user_story: str = Field(min_length=10)
    success_metric: SuccessMetric
    risks: list[DraftRisk] = Field(min_length=1)
    acceptance_criteria: list[NonemptyText] = Field(min_length=1)
    implementation_checklist: list[DraftTask] = Field(min_length=1)
    estimated_effort: str = Field(min_length=3)
    design_brief: str = Field(min_length=10)
    provider: str = "mock"
