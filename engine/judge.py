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

# --- критерий за простота (адаптация от program.md на autoresearch) --------
# Брои се КОДЪТ на инженера: тестовете/досието/документацията не са
# негови и не участват в мярката за растеж.
CODE_SUFFIXES = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".h", ".cpp", ".hpp", ".rb", ".php", ".sh",
})
LOC_EXCLUDED_PARTS = frozenset({
    ".ai-brain", ".git", "tests", "__pycache__", ".pytest_cache",
    "node_modules", "e2e",
})
# Минат гейт, но +над това = предупреждение за простота (не блокира).
SIMPLICITY_WARN_GROWTH = 50


def count_loc(project: Path, files: list[str] | None = None) -> int:
    """Редове код в проекта (или само в посочените файлове).

    Пълното сканиране е мярката за растеж между опитите; списъкът с
    файлове е за по-целенасочено измерване (липсващите = 0 реда).
    """
    root = Path(project)
    total = 0
    if files is not None:
        for rel in files:
            p = root / rel
            if p.is_file():
                total += len(p.read_text(
                    encoding="utf-8", errors="replace").splitlines())
        return total
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in LOC_EXCLUDED_PARTS for part in rel.parts):
            continue
        if rel.suffix.lower() not in CODE_SUFFIXES:
            continue
        total += len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    return total


def _simplicity(gate_ok: bool, *, loc: int | None,
                prev_loc: int | None) -> tuple[str, str] | None:
    """(машинен_код, човешки_текст) за критерия за простота; None = нищо."""
    if loc is None or prev_loc is None:
        return None  # няма предистория (първият опит) → няма сравнение
    delta = loc - prev_loc
    if gate_ok:
        if delta < 0:
            return (
                f"simplicity=win:{delta}",
                f"simplification win: {-delta} реда по-малко при минат гейт "
                f"— критерият за простота печели.",
            )
        if delta > SIMPLICITY_WARN_GROWTH:
            return (
                f"simplicity=growth_warn:+{delta}",
                f"simplicity: +{delta} реда при минат гейт — огледай дали може "
                f"по-кратко (критерий за простота).",
            )
        return None
    if delta > 0:
        return (
            f"simplicity=growth_on_fail:+{delta}",
            f"кодът порасна с {delta} реда, а гейтът не минава — търси "
            f"по-просто решение, а не повече код.",
        )
    return None


def simplicity_note(gate_ok: bool, *, loc: int | None,
                    prev_loc: int | None) -> str | None:
    """Само човешкият текст (за тестове/употреба извън feedback)."""
    hit = _simplicity(gate_ok, loc=loc, prev_loc=prev_loc)
    return hit[1] if hit else None


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
    gate_ok: bool | None,
    gate_output: str,
    round_no: int,
    project: Path,
    found_by: str = "gate",
    loc: int | None = None,
    prev_loc: int | None = None,
) -> FeedbackPacket:
    """``gate_ok`` е трисъстояниен: True мина, False не мина, None НЕ е проверен.

    ``None`` не може да даде PASS. Липсата на проверка не е доказателство, че
    кодът е наред — точно както baseline, който не може да се прочете, не е
    доказателство, че нищо не се е променило.
    """
    issues = structural_issues(task, project)
    not_verified = gate_ok is None
    ok = bool(gate_ok) and not issues
    if ok:
        human = (
            f"{task.id}: гейтът мина ({round_no}. опит) — кодът отговаря "
            f"на критериите."
        )
    elif not_verified:
        human = (
            f"{task.id}: НЕ Е ПРОВЕРЕН ({round_no}. опит) — няма gate команда "
            f"в policy, така че нищо не е минало. Това не е успех и не може да "
            f"стане PASS, докато не се конфигурира проверка."
        )
        if issues:
            human += " Отделно, структурни проблеми: " + "; ".join(issues) + "."
    else:
        reasons = []
        if not gate_ok:
            reasons.append("реалните тестове провалиха")
        reasons.extend(issues)
        human = f"{task.id}: провал ({round_no}. опит): {'; '.join(reasons)}."
        if gate_output:
            human += "\nИзход от тестовете:\n" + gate_output[-800:]
    # критерий за простота: оценка на растежа между опитите (адаптация)
    simp = _simplicity(bool(gate_ok), loc=loc, prev_loc=prev_loc)
    if not_verified:
        machine = ["gate=not_verified"] + issues
    else:
        machine = [f"gate={'pass' if gate_ok else 'fail'}"] + issues
    if simp:
        machine.append(simp[0])
        human += " " + simp[1]
    if ok:
        blocking: list[str] = []
    elif not_verified:
        blocking = ["gate_not_verified"] + issues
    else:
        blocking = ["gate_fail"] + issues
    return FeedbackPacket(
        task_id=task.id,
        round_no=round_no,
        verdict=Verdict.PASS if ok else Verdict.FAIL,
        machine_readable=machine,
        human_readable=human,
        blocking_issues=blocking,
        found_by=found_by,
    )



