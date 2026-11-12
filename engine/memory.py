"""Памет на екипа — цялата се съхранява в .ai-brain/ в папката на проекта.

Файлове:
  state.json   — текущо състояние + история на преходите
  plan.json    — последният план (за pause/resume)
  contract.json— договорът от intake
  tasks.jsonl  — FeedbackPacket на всеки кръг (append-only)
  budget.json  — бюджетен леджър
  feed.md      — хронологична лента за човека (G-ленти), ред =
                 `- <ts> | <tag> | <текст>` — grep по таг (модел LLM Wiki)
  memory.md    — обобщена памет (компактиране >400 реда = оставаща работа)
  index.md     — съдържателен каталог: файл → какво е → обновен + броеве
                 (генериран автоматично, не се редактира на ръка)
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# Тагове в feed.md: един малък дума без интервали/тръбички — иначе
# grep-конвенцията умира на следващия ред.
_TAG_OK = re.compile(r"[a-z][a-z0-9_-]*\Z")

#: Каталог: файл в .ai-brain → какво е (модел: index.md от LLM Wiki,
#: Karpathy gist 442a6bf). Само наличните файлове влизат в индекса —
#: нищо не се измисля.
INDEX_CATALOG = {
    "state.json": "къде е цикълът G0–G5 + история на преходите",
    "contract.json": "приетият договор (acceptance criteria)",
    "plan.json": "последният план (за pause/resume)",
    "tasks.jsonl": "FeedbackPacket на всеки кръг (append-only)",
    "budget.json": "бюджетен леджър — разходи по опити",
    "journal.tsv": "всеки опит: keep|discard|crash (append-only)",
    "feed.md": "хронологична лента за човека (с тагове)",
    "memory.md": "обобщена памет (компактиране)",
    "last_run.json": "последният машиночитаем отчет (--json)",
    "index.md": "този каталог (генериран автоматично)",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CorruptBrain(Exception):
    """Счупен/нечетим/липсващ ключов файл в .ai-brain/ (одит №4).

    Спира се ЯСНО и се влиза с exit 1 — не се маскира като fresh draft
    и не се презаписва нищо. Човекът поправя; tasks.jsonl/feed.md са четими.
    """


class Memory:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.root / name

    def exists(self, name: str) -> bool:
        return self.path(name).exists()

    def read_json(self, name: str, default=None):
        p = self.path(name)
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def read_json_strict(self, name: str):
        """Чете JSON; при проблем КАРА ЯСНО (одит №4).

        read_json остава толерантен (за optional файлове), но състоянието
        и плановете не бива да изглеждат „празни“ при счупване.
        """
        p = self.path(name)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise CorruptBrain(f"липсва {name}") from None
        except json.JSONDecodeError as e:
            raise CorruptBrain(f"счупен {name}: {e}") from e

    def _atomic_write(self, p: Path, text: str) -> None:
        """Първо в .tmp, после os.replace — прекъсване ≠ половин файл."""
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)

    def write_text(self, name: str, text: str) -> None:
        self._atomic_write(self.path(name), text)

    def write_json(self, name: str, obj) -> None:
        self._atomic_write(
            self.path(name),
            json.dumps(obj, ensure_ascii=False, indent=2),
        )

    def append_jsonl(self, name: str, obj) -> None:
        with self.path(name).open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def feed(self, text: str, tag: str) -> None:
        """Ред в лентата с категорийен таг (конвенция от LLM Wiki:
        консистентен префикс → `grep "| gate |" feed.md` стига).

        Без таг → ValueError: мълчаливо счупен ред би убил grep-а.
        """
        if not isinstance(tag, str) or not _TAG_OK.match(tag):
            raise ValueError(
                f"непозволен feed таг: {tag!r} — очаквано [a-z][a-z0-9_-]*"
            )
        line = f"- {_now()} | {tag} | {text}"
        with self.path("feed.md").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"[feed] {text}")

    def append_memory(self, text: str) -> None:
        with self.path("memory.md").open("a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n")

    def update_index(self) -> str:
        """index.md — съдържателен каталог на паметта (модел: LLM Wiki).

        Само наличните файлове + реални броеве от данните (никакви числа,
        написани на ръка — по духа на SUITE_TESTS_PASSED гарда). Връща
        текста; презаписва атомарно .ai-brain/index.md.
        """
        rows: list[str] = []
        for name in sorted(INDEX_CATALOG):
            p = self.path(name)
            if name != "index.md" and not p.exists():
                continue  # липсващ файл не се измисля
            if p.exists():
                when = (
                    datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ")
                )
            else:
                when = "сега"  # index.md се пише точно сега
            rows.append(f"| {name} | {INDEX_CATALOG[name]} | {when} |")

        lines = [
            "# .ai-brain/ — индекс (генериран автоматично; не се редактира)",
            "",
            "| файл | какво е | обновен (UTC) |",
            "|---|---|---|",
        ]
        lines += rows
        if len(rows) == 1:  # само index.md = мозъкът е празен
            lines.append(
                "| (празно) | няма още нищо — мозъкът е празен | - |"
            )

        jp = self.path("journal.tsv")
        if jp.exists():
            counts = {"keep": 0, "discard": 0, "crash": 0}
            total = 0
            for ln in jp.read_text(encoding="utf-8").splitlines()[1:]:
                parts = ln.split("\t")
                if len(parts) >= 4 and parts[3] in counts:
                    counts[parts[3]] += 1
                    total += 1
            lines.append(
                f"journal.tsv: {total} опита — keep {counts['keep']} / "
                f"discard {counts['discard']} / crash {counts['crash']}"
            )
        fp = self.path("feed.md")
        if fp.exists():
            n = sum(
                1 for ln in fp.read_text(encoding="utf-8").splitlines() if ln
            )
            lines.append(f"feed.md: {n} реда")

        text = "\n".join(lines) + "\n"
        self.write_text("index.md", text)
        return text
