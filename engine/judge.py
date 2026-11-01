"""Съдията — диалектика: теза (инженерът) vs антеза (структурни проверки
+ реален гейт) → FeedbackPacket (синтез).

В сглобката антезата е механична (файлове съществуват, не са празни, няма
TODO/FIXME/NotImplementedError, реалните тестове минават). Живият LLM-адвокат
(анти-галусинация) е оставаща работа.
"""
from __future__ import annotations

from pathlib import Path

from .schemas import FeedbackPacket, Task, Verdict

BANNED = ("TODO", "FIXME", "NotImplementedError", "XXX")


def structural_issues(task: Task, project: Path) -> list[str]:
    issues: list[str] = []
    if not task.files:
        issues.append(f"{task.id}: планът не посочва файлове")
    for rel in task.files:
        p = project / rel
        if not p.exists():
            issues.append(f"липсва файл {rel}")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            issues.append(f"{rel} е празен")
        for b in BANNED:
            if b in text:
                issues.append(f"{rel} съдържа {b}")
    return issues


def feedback(
    task: Task,
    gate_ok: bool,
    gate_output: str,
    round_no: int,
    project: Path,
    found_by: str = "gate",
) -> FeedbackPacket:
    issues = structural_issues(task, project)
    ok = gate_ok and not issues
    if ok:
        human = (
            f"{task.id}: гейтът мина ({round_no}. опит) — кодът отговаря "
            f"на критериите."
        )
    else:
        reasons = []
        if not gate_ok:
            reasons.append("реалните тестове провалиха")
        reasons.extend(issues)
        human = f"{task.id}: провал ({round_no}. опит): {'; '.join(reasons)}."
        if gate_output:
            human += "\nИзход от тестовете:\n" + gate_output[-800:]
    return FeedbackPacket(
        task_id=task.id,
        round_no=round_no,
        verdict=Verdict.PASS if ok else Verdict.FAIL,
        machine_readable=[f"gate={'pass' if gate_ok else 'fail'}"] + issues,
        human_readable=human,
        blocking_issues=[] if ok else ["gate_fail"] + issues,
        found_by=found_by,
    )



