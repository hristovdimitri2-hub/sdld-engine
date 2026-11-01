"""Pydantic модели — всичко минава през валидация (никакъв dogmatics/raw JSON)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExecutionState(str, Enum):
    DRAFT = "draft"
    INTAKE = "intake"
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED_BUDGET = "paused_budget"
    BLOCKED = "blocked"
    DONE = "done"
    ESCALATED = "escalated"
    ARCHIVED = "archived"


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEED_HUMANS = "need_humans"


class Contract(BaseModel):
    """Договор от intake: какво точно се доставя + критерии за приемане."""

    id: str
    name: str
    objective: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    budget_limit_usd: float = 5.0


class Task(BaseModel):
    """Единична задача от плана на архитекта."""

    id: str
    title: str
    description: str = ""
    files: list[str] = Field(default_factory=list)
    gate: str = "unittest"
    state: str = "planned"  # planned | passed
    attempts: int = 0
    last_error: str = ""


class Plan(BaseModel):
    contract_id: str = ""
    tasks: list[Task] = Field(default_factory=list)


class FeedbackPacket(BaseModel):
    """Машинночетим пакет обратна връзка: къде, защо, кой го е намерил."""

    task_id: str
    round_no: int = 0
    verdict: Verdict
    machine_readable: list[str] = Field(default_factory=list)
    human_readable: str = ""
    blocking_issues: list[str] = Field(default_factory=list)
    found_by: str = "gate"  # gate | judge | auditor | expert:<role>


# --- одит №5: ВСЕКИ отговор на модела минава през схема ---------------------
class ToolCall(BaseModel):
    tool: str = "write_file"
    args: dict[str, Any] = Field(default_factory=dict)


class EngineerReply(BaseModel):
    summary: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class AuditorReply(BaseModel):
    verdict: Verdict
    found_by: str = "auditor"
    confidence: float = 1.0
    message: str = ""
    blocking_issues: list[str] = Field(default_factory=list)


class EscalationReply(BaseModel):
    action: str = "stop_human"
    reason: str = ""


