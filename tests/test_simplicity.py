"""Критерий за простота — адаптация от program.md на autoresearch:

  „По-добро с по-малко редове = вземи го (simplification win).
   По-добро с много нов грозен код = претегли.
   Минат гейт, но кодът расте = огледай дали може по-кратко.
   Кодът расте, а гейтът не минава = търси по-просто, не повече код.“
"""
import pytest

from engine.judge import count_loc, feedback, simplicity_note
from engine.schemas import Task, Verdict


def test_count_loc_counts_code_and_skips_protected(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("\n".join(f"x={i}" for i in range(10)),
                                            encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("x = 1\n" * 5, encoding="utf-8")
    (tmp_path / ".ai-brain").mkdir()
    (tmp_path / ".ai-brain" / "state.json").write_text("{}\n" * 50,
                                                       encoding="utf-8")
    (tmp_path / "program.md").write_text("# инструкции\n" * 40, encoding="utf-8")
    # брои се КОДЪТ на инженера: src/, НЕ тестовете/досието/документацията
    assert count_loc(tmp_path) == 10


def test_count_loc_with_explicit_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a\nb\nc\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("d\ne\n", encoding="utf-8")
    assert count_loc(tmp_path, ["src/a.py", "src/b.py"]) == 5
    assert count_loc(tmp_path, ["src/липсва.py"]) == 0


def test_note_simplification_win_on_pass():
    note = simplicity_note(True, loc=10, prev_loc=25)
    assert note is not None
    assert "simplification win" in note
    assert "15" in note  # минус редовете


def test_note_growth_on_fail():
    note = simplicity_note(False, loc=30, prev_loc=10)
    assert note is not None
    assert "порасна" in note
    assert "по-просто" in note


def test_note_growth_warning_on_pass_when_too_much():
    note = simplicity_note(True, loc=10 + 60, prev_loc=10)
    assert note is not None
    assert "по-кратко" in note


def test_no_note_without_previous_measure():
    assert simplicity_note(True, loc=10, prev_loc=None) is None


def test_no_note_when_loc_unchanged():
    assert simplicity_note(True, loc=10, prev_loc=10) is None
    assert simplicity_note(False, loc=10, prev_loc=10) is None


def test_no_growth_note_when_fail_but_shrunk():
    """Провалът вече си има съобщение от съдията — простотата мълчи,
    когато кодът не расте."""
    assert simplicity_note(False, loc=5, prev_loc=20) is None


def test_feedback_carries_simplicity_note(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    task = Task(id="T1", title="x", files=["src/a.py"])
    fb = feedback(task, gate_ok=True, gate_output="", round_no=1,
                  project=tmp_path, loc=5, prev_loc=50)
    assert fb.verdict == Verdict.PASS
    assert "simplification win" in fb.human_readable
    assert any(m.startswith("simplicity=") for m in fb.machine_readable)


def test_feedback_without_loc_is_unchanged(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    task = Task(id="T1", title="x", files=["src/a.py"])
    fb = feedback(task, gate_ok=True, gate_output="", round_no=1,
                  project=tmp_path)
    assert not any(m.startswith("simplicity=") for m in fb.machine_readable)
    assert "simplification" not in fb.human_readable


@pytest.mark.parametrize("status,ok,loc,prev", [
    (True, True, 10, 20),    # win
    (True, True, 80, 10),    # warn
    (False, False, 30, 10),  # growth on fail
])
def test_notes_have_machine_codes(status, ok, loc, prev):
    note = simplicity_note(ok, loc=loc, prev_loc=prev)
    assert note  # всеки trắng случай носи код за машината
