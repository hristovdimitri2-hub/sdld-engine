from pathlib import Path

from engine.gates import run_gate


def test_gate_pass(tmp_path: Path):
    ok, out, dur = run_gate(["{python}", "-c", "print('ok')"], tmp_path)
    assert ok is True
    assert "ok" in out
    assert dur >= 0


def test_gate_fail_reports_real_output(tmp_path: Path):
    ok, out, _ = run_gate(
        ["{python}", "-c", "import sys; print('FAIL: 1 не мина'); sys.exit(1)"],
        tmp_path,
    )
    assert ok is False
    assert "FAIL" in out  # истинският изход стига до обратната връзка


def test_gate_missing_command_is_skipped(tmp_path: Path):
    ok, _, _ = run_gate([], tmp_path)
    assert ok is True
