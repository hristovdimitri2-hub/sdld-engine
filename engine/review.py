"""Review-фаза — контекст ПРЕДИ всеки инженерски опит (модел: Phase 1 Review
от autoresearch skill).

Инженерът получава:
  1. последните редове от .ai-brain/journal.tsv — какво вече е пробвано и
     какво е keep/discard/crash (историята се ЧЕТЕ, не се помни);
  2. `git log -10` на проекта — какво е пипано напоследък.

Блокът влиза като отделно user-съобщение между program.md и задачата.
Гради се за ВСЕКИ опит (нов ред в журнала след всеки предишен).
Всичко е четене: journal през Journal, git през subprocess с фиксирани
аргументи (без shell, с таймаут) — нито едното не пипа проекта.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .journal import FIELDS, HEADER, Journal

JOURNAL_TAIL = 8   # колко реда от журнала се подават
GIT_LOG_N = 10     # класическото "git log -10"

_NO_REPO = "(няма git история в проекта — пропускам)"
_NO_GIT = "(git не е наличен — пропускам)"
_EMPTY = "(журналът е празен — това е първият опит)"


def journal_tail(journal: Journal, n: int = JOURNAL_TAIL) -> str:
    """Последните n реда от журнала, с глава — както изглеждат в TSV."""
    rows = journal.rows()[-n:]
    if not rows:
        return _EMPTY
    lines = [HEADER] + ["\t".join(row[f] for f in FIELDS) for row in rows]
    return "\n".join(lines)


def git_log(project: Path, n: int = GIT_LOG_N) -> str:
    """Последните n комита (--oneline); извън git/без git — ясна бележка."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(project), "log", f"-{n}", "--oneline",
             "--no-decorate"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _NO_GIT
    if proc.returncode != 0:
        return _NO_REPO
    out = (proc.stdout or "").strip()
    return out or _NO_REPO


def build(project: Path, journal: Journal, *, n_rows: int = JOURNAL_TAIL,
          n_commits: int = GIT_LOG_N) -> str:
    """Целият Review-блок за едно извикване на инженера."""
    return (
        "## Review — какво вече е пробвано (чети го, не го познавай наизуст)\n"
        "\n### journal.tsv (последните редове)\n"
        f"```\n{journal_tail(journal, n_rows)}\n```\n"
        "\n### git log\n"
        f"```\n{git_log(project, n_commits)}\n```\n"
        "\nНе повтаряй discard/crash редовете — промяната, която правиш, "
        "трябва да е различна."
    )
