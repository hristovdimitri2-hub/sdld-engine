"""Машина на състоянията — всеки преход носи номер (G0, G1, G2...).

Гейтове (преходи) в сглобката:
  G0  draft     -> intake      (intake агентът върна валиден Contract)
  G1  intake    -> planned     (архитектът върна валиден Plan)
  G2  planned   -> active      (бюджет pre-check мина)
  G2b planned   -> paused_budget (бюджетът не стига; exit 1, после resume)
  G3  active    -> escalated   (гейтът провали max опита или одитът е fail)
  G4  active    -> done        (одитът е pass)
  G5  escalated -> blocked     (ескалирацията поиска човек — stop_human)
"""
from __future__ import annotations

from datetime import datetime, timezone

from .memory import CorruptBrain, Memory
from .schemas import ExecutionState as S

VALID: dict[S, set[S]] = {
    S.DRAFT: {S.INTAKE},
    S.INTAKE: {S.PLANNED},
    S.PLANNED: {S.ACTIVE, S.PAUSED_BUDGET, S.BLOCKED},
    S.ACTIVE: {S.DONE, S.BLOCKED, S.ESCALATED, S.PAUSED_BUDGET},
    S.PAUSED_BUDGET: {S.ACTIVE, S.ARCHIVED},
    S.ESCALATED: {S.BLOCKED, S.ACTIVE, S.ARCHIVED},
    S.BLOCKED: {S.ACTIVE, S.ARCHIVED},
    S.DONE: {S.ARCHIVED},
    S.ARCHIVED: set(),
}


class InvalidTransition(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StateMachine:
    def __init__(
        self,
        state: S = S.DRAFT,
        last_gate: str = "",
        history: list | None = None,
        brain: Memory | None = None,
    ):
        self.state = state
        self.last_gate = last_gate
        self.history: list = history or []
        self.brain = brain  # ако е даден, всеки преход се записва веднага

    def can(self, to: S) -> bool:
        return to in VALID[self.state]

    def transition(self, to: S | str, gate: str) -> None:
        to = S(to)
        if not self.can(to):
            raise InvalidTransition(
                f"Невалиден преход {self.state.value} -> {to.value} (gate {gate})"
            )
        self.history.append(
            {
                "from": self.state.value,
                "to": to.value,
                "gate": gate,
                "at": _now(),
            }
        )
        self.state = to
        self.last_gate = gate
        if self.brain:
            self.save(self.brain)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "last_gate": self.last_gate,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StateMachine":
        return cls(
            state=S(data.get("state", "draft")),
            last_gate=data.get("last_gate", ""),
            history=list(data.get("history", [])),
        )

    @classmethod
    def load(cls, brain: Memory) -> "StateMachine":
        # одит №4: счупен state.json КАРА ЯСНО; само наистина липсващ = draft
        p = brain.path("state.json")
        if not p.exists():
            return cls(brain=brain)
        data = brain.read_json_strict("state.json")
        if not data:
            raise CorruptBrain("state.json е празен")
        sm = cls.from_dict(data)
        sm.brain = brain
        return sm

    def save(self, brain: Memory) -> None:
        brain.write_json("state.json", self.to_dict())
