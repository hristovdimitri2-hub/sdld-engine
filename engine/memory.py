"""Памет на екипа — цялата се съхранява в .ai-brain/ в папката на проекта.

Файлове:
  state.json   — текущо състояние + история на преходите
  plan.json    — последният план (за pause/resume)
  contract.json— договорът от intake
  tasks.jsonl  — FeedbackPacket на всеки кръг (append-only)
  budget.json  — бюджетен леджър
  feed.md      — хронологична лента за човека (G-ленти)
  memory.md    — обобщена памет (компактиране >400 реда = оставаща работа)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


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

    def feed(self, text: str) -> None:
        line = f"- {_now()} | {text}"
        with self.path("feed.md").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"[feed] {text}")

    def append_memory(self, text: str) -> None:
        with self.path("memory.md").open("a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n")
