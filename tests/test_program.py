"""program.md — адаптация на „рограмния файл“ от autoresearch:
човекът програмира екипа чрез program.md, агентът го ЧЕТЕ и не го пипа
(както в autoresearch: human edits program.md, agent edits train.py).
"""
import pytest

from engine import loop
from engine.agents import ToolError
from engine.program import PROGRAM_MD, ensure_program, load_program


def test_template_covers_core_sections():
    for key in ("ЖУРНАЛ", "ГЕЙТ", "БЮДЖЕТ", "простота", "keep", "discard"):
        assert key in PROGRAM_MD, f"шаблонът не съдържа „{key}“"


def test_ensure_program_creates_file(tmp_path):
    p = ensure_program(tmp_path)
    assert p.name == "program.md"
    assert p.read_text(encoding="utf-8") == PROGRAM_MD


def test_ensure_program_does_not_overwrite_human_edits(tmp_path):
    """Ключовата разлика спрямо код: човекът редактира program.md и
    редакцията му оцелява при следващ старт."""
    mine = "# МОЯТА ВЕРСИЯ — специфичните правила на клиента\n"
    (tmp_path / "program.md").write_text(mine, encoding="utf-8")
    p = ensure_program(tmp_path)
    assert p.read_text(encoding="utf-8") == mine


def test_load_program_missing_is_empty(tmp_path):
    assert load_program(tmp_path) == ""


def test_engineer_cannot_rewrite_program(tmp_path):
    """Програмата на екипа е на човека — инженерът не пренаписва
    собствените си инструкции (самомодифициращ се промпт = одитен риск)."""
    with pytest.raises(ToolError):
        loop._write_file(tmp_path, "program.md", "нови правила за мен")


def test_run_creates_program_and_feeds_it_to_agents(tmp_path, make_project,
                                                    monkeypatch):
    """Целият цикъл получава program.md като контекст (сух режим, реален
    гейт) — агентът вижда правилата, програмирани от човека."""
    from engine import agents as ag
    from engine.config import load_policy

    captured: dict[str, list] = {}
    real = ag.call

    def spy(policy, role, messages, **kw):
        captured.setdefault(role, []).append(list(messages))
        return real(policy, role, messages, **kw)

    monkeypatch.setattr(ag, "call", spy)
    proj = make_project(passing=True)
    code = loop.run("инструкция", str(proj), policy=load_policy())
    assert code == 0
    assert (proj / "program.md").exists()
    # инженерът и аудиторът получават програмата в съобщенията си
    for role in ("engineer", "auditor"):
        msgs = captured[role][0]
        assert any("ЖУРНАЛ" in m.get("content", "") for m in msgs), \
            f"{role} не получи program.md"
