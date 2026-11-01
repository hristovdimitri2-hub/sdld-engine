"""Дефект №4 от външния одит (01.11.2026):
  - счупен state.json се поглъщаше тихо → изглеждаше като чист draft
    и resume казваше „няма какво да се възобнови";
  - записите бяха direct write_text — при прекъсване остава наполовина
    написан файл (corrupted JSON).

Правило: счупен файл спира с ЯСНА грешка (CorruptBrain), не се прави на
fresh state; записите минават през .tmp + os.replace.
"""
import json

import pytest

from engine.memory import CorruptBrain, Memory
from engine.schemas import ExecutionState as S
from engine.state import StateMachine


def test_corrupt_state_raises_instead_of_draft(tmp_path):
    brain = Memory(tmp_path / ".ai-brain")
    brain.path("state.json").parent.mkdir(parents=True, exist_ok=True)
    brain.path("state.json").write_text("{ това е счупен JSON", encoding="utf-8")
    with pytest.raises(CorruptBrain):
        StateMachine.load(brain)


def test_missing_state_is_still_fresh_draft(tmp_path):
    brain = Memory(tmp_path / ".ai-brain")
    sm = StateMachine.load(brain)
    assert sm.state == S.DRAFT


def test_strict_read_reports_corrupt_plan(tmp_path):
    brain = Memory(tmp_path / ".ai-brain")
    brain.write_text("plan.json", "не е JSON изобщо")
    with pytest.raises(CorruptBrain):
        brain.read_json_strict("plan.json")


def test_strict_read_reports_missing_file(tmp_path):
    brain = Memory(tmp_path / ".ai-brain")
    with pytest.raises(CorruptBrain):
        brain.read_json_strict("plan.json")


def test_write_json_is_atomic_and_leaves_no_tmp(tmp_path, monkeypatch):
    import engine.memory as mem

    brain = Memory(tmp_path / ".ai-brain")
    replaced = []
    real_replace = mem.os.replace

    def spy(src, dst):
        replaced.append((src, dst))
        real_replace(src, dst)

    monkeypatch.setattr(mem.os, "replace", spy)
    brain.write_json("state.json", {"state": "active"})
    assert replaced, "write_json трябва да минава през os.replace (атомарност)"
    p = brain.path("state.json")
    assert json.loads(p.read_text(encoding="utf-8")) == {"state": "active"}
    assert not list(p.parent.glob("*.tmp")), "не бива да остава .tmp боклук"


def test_write_text_is_atomic_and_leaves_no_tmp(tmp_path):
    brain = Memory(tmp_path / ".ai-brain")
    brain.write_text("feed.md", "ред 1\n")
    p = brain.path("feed.md")
    assert p.read_text(encoding="utf-8") == "ред 1\n"
    assert not list(p.parent.glob("*.tmp"))
