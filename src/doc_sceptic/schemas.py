from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Requirements(BaseModel):
    data_types: list[str] = Field(default_factory=list)
    development_styles: list[str] = Field(default_factory=list)
    multi_table_transactions: bool | None = None
    power_bi: bool | None = None
    streaming: bool | None = None
    unstructured_data: bool | None = None
    constraints: list[str] = Field(default_factory=list)
    missing_constraints: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    source_id: str
    title: str
    section: str
    source_path: str
    url: str
    text: str
    score: float


class AgentAnswer(BaseModel):
    action: Literal["recommend", "clarify", "abstain", "chat"]
    answer: str
    requirements: Requirements
    citations: list[Evidence] = Field(default_factory=list)
    confidence: float = 0.0
    trace: list[str] = Field(default_factory=list)
