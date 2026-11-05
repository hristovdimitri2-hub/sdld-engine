"""Журнал на опитите — .ai-brain/journal.tsv (модел: results.tsv от
karpathy/autoresearch).

Всеки опит оставя един таб-разделен ред:

    at  task  round  status  gate_s  loc  usd  description

status: keep    — гейтът минa → промяната се запазва;
        discard — гейтът провали/таймаут → промяната се отхвърля;
        crash   — инструментът/извикването гръмна преди гейт.

Историята се ЧЕТЕ (last_loc храни предишния обем за критерия за
простота), а не се помни в главата на агента. Записът е append-only;
описанието се чисти от таб/нови редове, за да не се счупи TSV.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .memory import Memory

HEADER = "at\ttask\tround\tstatus\tgate_s\tloc\tusd\tdescription"
FIELDS = ("at", "task", "round", "status", "gate_s", "loc", "usd",
          "description")
VALID_STATUS = frozenset({"keep", "discard", "crash"})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(value) -> str:
    """TSV умира от таб/нов ред в клетка — заменя се с интервал."""
    return str(value).replace("\t", " ").replace("\n", " ").replace("\r", " ")


class Journal:
    def __init__(self, brain: Memory):
        self.brain = brain

    @property
    def path(self):
        return self.brain.path("journal.tsv")

    def _ensure_header(self) -> None:
        if not self.path.exists():
            self.brain.write_text("journal.tsv", HEADER + "\n")

    def record(self, *, task: str, round_no: int, status: str,
               gate_s: float = 0.0, loc: int | None = None, usd: float = 0.0,
               description: str = "") -> None:
        if status not in VALID_STATUS:
            raise ValueError(
                f"непознат статус в журнала: {status!r} "
                f"(очаквано едно от {sorted(VALID_STATUS)})"
            )
        self._ensure_header()
        row = "\t".join([
            _now(),
            _clean(task),
            _clean(int(round_no)),
            status,
            _clean(float(gate_s)),
            "" if loc is None else _clean(int(loc)),
            _clean(float(usd)),
            _clean(description),
        ])
        with self.path.open("a", encoding="utf-8") as f:
            f.write(row + "\n")

    def rows(self) -> list[dict]:
        """Всички редове (без главата) като речници — низове, както са."""
        if not self.path.exists():
            return []
        out: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line or line == HEADER:
                continue
            parts = line.split("\t")
            if len(parts) != len(FIELDS):
                continue  # повреден ред (напр. от ръчна редакция) — пропускаме
            out.append(dict(zip(FIELDS, parts)))
        return out

    def last_loc(self, task_id: str) -> int | None:
        """Последният измерен обем (редове код) за задачата — опората на
        критерия за простота. None = няма предистория (първият опит)."""
        for row in reversed(self.rows()):
            if row["task"] != task_id:
                continue
            if row["loc"] == "":
                continue  # crash преди измерване — не е база за сравнение
            try:
                return int(row["loc"])
            except ValueError:
                continue
        return None
