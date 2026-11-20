"""Дефект №1 от външния одит (01.11.2026): инженерът можеше да пренапише
тестовете и да си занули досието/бюджета → фалшив успех.

Тези тестове ПЪРВО възпроизвеждат дефекта (червени), после доказват
поправката (зелени):
  1. write_file в tests/, .ai-brain/, config/ и системните конфиги е забранен;
  2. тестовете, променени ДО РЕАЛНО изпълнение на гейта, се хващат (хеш).
"""
from pathlib import Path

import pytest

from conftest import FAILING_TESTS, PASSING_TESTS
from engine import loop
from engine.agents import ToolError
from engine.gates import run_gate


@pytest.mark.parametrize(
    "rel",
    [
        "tests/test_evil.py",       # класическият запис: презапис на тестове
        "tests/sub/test_more.py",    # същото през подпапка
        ".ai-brain/state.json",      # зануляване на състоянието
        ".ai-brain/budget.json",     # зануляване на бюджета
        "config/policy.json",        # пипане на политиката
        "conftest.py",               # контролира колекцията на pytest
        "pytest.ini",
    ],
)
def test_engineer_cannot_write_protected_paths(tmp_path: Path, rel: str):
    with pytest.raises(ToolError):
        loop._write_file(tmp_path, rel, "evil = True")


def test_engineer_can_still_write_implementation(tmp_path: Path):
    p = loop._write_file(tmp_path, "src/vat.py", "def withVAT(x):\n    return x\n")
    assert p.exists()
    p2 = loop._write_file(tmp_path, "src/pkg/__init__.py", "")
    assert p2.exists()


def test_engineer_cannot_escape_project(tmp_path: Path):
    with pytest.raises(ToolError):
        loop._write_file(tmp_path, "../outside.py", "evil = True")


def _mk_tests(project: Path, text: str = "x = 1\n") -> Path:
    (project / "tests").mkdir(exist_ok=True)
    f = project / "tests" / "t.py"
    f.write_text(text, encoding="utf-8")
    return f


def test_gate_fails_when_tests_mutate_during_run(tmp_path: Path):
    """Гейтът смени тестовете, докато ги изпълняваше → резултатът невалиден."""
    _mk_tests(tmp_path)
    ok, out, _ = run_gate(
        ["{python}", "-c",
         "from pathlib import Path; Path('tests/t.py').write_text('x = 2')"],
        tmp_path,
    )
    assert ok is False
    assert "ПРОМЕНЕНИ" in out


def test_gate_fails_when_tests_deleted_during_run(tmp_path: Path):
    _mk_tests(tmp_path)
    ok, out, _ = run_gate(
        ["{python}", "-c", "from pathlib import Path; Path('tests/t.py').unlink()"],
        tmp_path,
    )
    assert ok is False
    assert "ПРОМЕНЕНИ" in out


def test_gate_passes_when_tests_untouched(tmp_path: Path):
    _mk_tests(tmp_path)
    ok, out, _ = run_gate(["{python}", "-c", "print('ran')"], tmp_path)
    assert ok is True
    assert "ПРОМЕНЕНИ" not in out


# --- одит №3: секретите не се наследяват от гейта (и от кода на модела) ---

def test_gate_never_sees_secret_env(tmp_path: Path, monkeypatch):
    """Кодът на гейта (писан/пипан от модела) не вижда OPENROUTER_API_KEY."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-SECRET-XYZ")
    ok, out, _ = run_gate(
        ["{python}", "-c",
         "import os; print('key=', os.environ.get('OPENROUTER_API_KEY'))"],
        tmp_path,
    )
    assert ok is True           # гейтът все още се изпълнява (чиста среда е жизнеспособна)
    assert "sk-SECRET-XYZ" not in out
    assert "key= None" in out


def test_gate_env_has_no_arbitrary_passthrough(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MY_SOMETHING_PRIVATE", "do-not-leak")
    ok, out, _ = run_gate(
        ["{python}", "-c",
         "import os; print('v=', os.environ.get('MY_SOMETHING_PRIVATE'))"],
        tmp_path,
    )
    assert ok is True
    assert "do-not-leak" not in out


# --- възпроизвеждане на одит №1 (07.11.2026, v0.1.0) през ЦЕЛИЯ цикъл ---

def test_loop_reproduces_audit1_engineer_cannot_fake_the_gate(
        tmp_path: Path, make_project, fake_agents):
    """Външният одит на v0.1.0: инженерът подаде код с `return None` и тест
    `assertTrue(True)` → резултат PASS, done, exit 0.

    Сега: write_file в tests/ се отхвърля още на опита (crash в журнала),
    истинските тестовете остават непроменени, ретраите свършват и цикълът
    ескалира → exit 1. Този тест минаваше САМО ако №1 е поправен.
    """
    from engine.config import load_policy

    proj = make_project(passing=False)  # истинските тестове се проваляват
    roles = fake_agents(engineer={
        "summary": "пренаписвам тестовете, за да минат",
        "tool_calls": [{
            "tool": "write_file",
            "args": {"path": "tests/test_gate.py", "content": PASSING_TESTS},
        }],
    })
    policy = load_policy()

    code = loop.run("направи го да минава", str(proj), policy=policy)

    assert code == 1  # старото (v0.1.0): 0 — фалшив „done“
    # тестовете са недокоснати — гейтът вижда истинските (провалени)
    assert (proj / "tests" / "test_gate.py").read_text(
        encoding="utf-8") == FAILING_TESTS
    # инженерът е извикан пълните max_attempts (3) пъти, но нищо не е записано
    assert roles.count("engineer") == 3
    plan = (proj / ".ai-brain" / "plan.json")
    assert plan.exists() and \
        __import__("json").loads(plan.read_text(encoding="utf-8"))[
            "tasks"][0]["attempts"] == 3


def test_gate_ignores_bytecode_caches(tmp_path: Path):
    """__pycache__, създаден от самия гейт, НЕ е „мутация“ на тестовете."""
    _mk_tests(tmp_path)
    ok, out, _ = run_gate(
        ["{python}", "-c",
         "import pathlib; d = pathlib.Path('tests/__pycache__'); "
         "d.mkdir(exist_ok=True); "
         "(d / 't.cpython-312.pyc').write_bytes(b'PYC'); print('ok')"],
        tmp_path,
    )
    assert ok is True, out
