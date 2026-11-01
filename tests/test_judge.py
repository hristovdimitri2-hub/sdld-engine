from pathlib import Path

from engine.judge import feedback, structural_issues
from engine.schemas import Task, Verdict


def _task(tmp_path: Path) -> Task:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "vat.py").write_text(
        "def withVAT(a, r):\n    return round(a * (1 + r), 2)\n", encoding="utf-8"
    )
    return Task(id="T1", title="x", files=["src/vat.py"])


def test_structural_issues_empty_when_file_good(tmp_path: Path):
    assert structural_issues(_task(tmp_path), tmp_path) == []


def test_structural_issues_flags_missing_file(tmp_path: Path):
    task = Task(id="T1", title="x", files=["src/missing.py"])
    issues = structural_issues(task, tmp_path)
    assert any("липсва" in i for i in issues)


def test_structural_issues_flags_todo(tmp_path: Path):
    (tmp_path / "a.py").write_text("TODO: после", encoding="utf-8")
    task = Task(id="T1", title="x", files=["a.py"])
    issues = structural_issues(task, tmp_path)
    assert any("TODO" in i for i in issues)


def test_structural_issues_does_not_flag_placeholder(tmp_path: Path):
    """одит №6: „placeholder“ е легален код (HTML/Django/наши полета) —
    НЕ е фалшива тревога като TODO/FIXME."""
    (tmp_path / "a.py").write_text(
        'x = {"placeholder": "1"}\nself.placeholder = None\n', encoding="utf-8"
    )
    task = Task(id="T1", title="x", files=["a.py"])
    issues = structural_issues(task, tmp_path)
    assert not any("placeholder" in i for i in issues)


def test_feedback_fail_blocks(tmp_path: Path):
    task = Task(id="T1", title="x", files=["src/vat.py"])
    fb = feedback(task, gate_ok=False, gate_output="boom", round_no=1,
                  project=tmp_path)
    assert fb.verdict == Verdict.FAIL
    assert "gate_fail" in fb.blocking_issues
    assert "boom" in fb.human_readable


def test_feedback_pass(tmp_path: Path):
    task = _task(tmp_path)
    fb = feedback(task, gate_ok=True, gate_output="", round_no=1,
                  project=tmp_path)
    assert fb.verdict == Verdict.PASS
    assert fb.blocking_issues == []
