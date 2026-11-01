"""Бюджетен леджър — pre-check ПРЕДИ скъпо действие, лимити, симулация на 402.

Правило: бюджетът спира, преди да се плати — не след това.
В dry режим записите са $0.00 (реални разходи няма).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .memory import Memory

EPS = 1e-9


class BudgetPause(Exception):
    """Проектираната стойност надхвърля твърдия лимит — спираме преди плащане."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Ledger:
    def __init__(self, policy, brain: Memory | None = None):
        self.policy = policy
        self.brain = brain
        self.limit_usd = float(policy.limit_usd)
        self.soft_pause_usd = float(policy.soft_pause_usd)
        data = brain.read_json("budget.json") if brain else None
        self.entries: list = (data or {}).get("entries", [])

    @property
    def spent_usd(self) -> float:
        return sum(float(e.get("usd", 0.0)) for e in self.entries)

    def precheck(self, need_usd: float) -> str | None:
        """Връща предупреждение при soft лимит; хвърля BudgetPause при твърд."""
        projected = self.spent_usd + float(need_usd)
        if projected > self.limit_usd + EPS:
            raise BudgetPause(
                f"проектирано {projected:.4f} $ ({self.spent_usd:.4f} $ платени "
                f"+ {need_usd:.4f} $ нужно) > лимит {self.limit_usd:.4f} $"
            )
        if projected > self.soft_pause_usd + EPS:
            return (
                f"бюджет: проектирано {projected:.4f} $ минава soft лимита "
                f"{self.soft_pause_usd:.4f} $"
            )
        return None

    def record(self, usd: float, note: str) -> None:
        self.entries.append(
            {"at": _now(), "usd": round(float(usd), 6), "note": note}
        )
        self._save()

    def _save(self) -> None:
        if self.brain:
            self.brain.write_json(
                "budget.json", {"entries": self.entries, "spent": self.spent_usd}
            )


def remaining_need(plan, allowance_per_task_usd: float) -> float:
    """Колко още е нужно за НЕприключилите задачи (одит №6).

    Старото: len(plan.tasks) — брои и приключените, които няма да се
    повтарят → resume спираше излишно (fail-safe посока, но грешно).
    """
    return (
        sum(1 for t in plan.tasks if t.state != "passed")
        * float(allowance_per_task_usd)
    )
