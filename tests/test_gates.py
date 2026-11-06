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


def test_gate_missing_command_is_not_verified_and_not_a_pass(tmp_path: Path):
    """Липсата на проверка не е успех.

    Този тест преди твърдеше ``ok is True`` и с това ЗАКОВАВАШЕ дефекта:
    harness, който показва успех, без нито една проверка да е минала. Всяка
    harness прави обратното — показва успех само когато проверките са минали.
    Затова сега се иска третото състояние ``None``: „не е проверен".
    """
    ok, out, dur = run_gate([], tmp_path)
    assert ok is None, (
        "гейт без команда трябва да е 'не е проверен' (None), не True — "
        "иначе проект без никакви проверки се отчита като успешен"
    )
    assert ok is not True
    assert dur == 0.0
    assert "НЕ е проверен" in out
