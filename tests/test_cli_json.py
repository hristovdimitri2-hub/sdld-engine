"""--json изход на CLI (точка 1 от плана, 05.11.2026).

Външният агент (VisiCode/Cline) чете РЕЗУЛТАТА, не човешки текст:
  - stdout съдържа ЕДИН валиден JSON обект (и нищо друго);
  - човешките съобщения отиват на stderr;
  - резултатът се записва и в .ai-brain/last_run.json (файлова следа).
"""
import json

from engine.cli import main


def _invoke(argv) -> int:
    """Пуска CLI в процеса и връща exit кода (main ползва sys.exit)."""
    try:
        return int(main(argv) or 0)
    except SystemExit as e:
        return int(e.code or 0)


def _stdout_json(capsys) -> dict:
    out = capsys.readouterr().out
    return json.loads(out)  # ако има нещо освен JSON → гърми тук


def test_status_json_empty_project(capsys, tmp_path):
    code = _invoke(["status", "--project", str(tmp_path / "nope"), "--json"])
    assert code == 0
    data = _stdout_json(capsys)
    assert data["state"] in ("draft", "no_state")
    assert data["tasks"] == []
    assert data["counts"] == {"total": 0, "passed": 0}


def test_run_json_single_object_with_verdict(capsys, make_project,
                                             fake_agents):
    proj = make_project(passing=True)
    fake_agents()
    code = _invoke(["run", "напиши src/x.py", "--project", str(proj),
                    "--dry-run", "--json"])
    assert code == 0
    data = _stdout_json(capsys)
    assert data["ok"] is True
    assert data["exit_code"] == 0
    assert data["state"] == "done"
    assert data["last_gate"] == "G4"
    assert data["counts"] == {"total": 1, "passed": 1}
    assert data["tasks"][0]["state"] == "passed"
    assert data["mode"] == "dry"
    assert data["version"]  # версията е част от отговора


def test_run_json_human_output_not_on_stdout(capsys, make_project,
                                             fake_agents):
    """Ключово за потребителя: stdout е само JSON — „✅ Екипът завърши“
    и другите човешки редове са на stderr."""
    proj = make_project(passing=True)
    fake_agents()
    _invoke(["run", "инструкция", "--project", str(proj), "--dry-run",
             "--json"])
    captured = capsys.readouterr()
    json.loads(captured.out)  # stdout = чист JSON
    assert "Екипът завърши" in captured.err


def test_run_json_writes_last_run_file(capsys, make_project, fake_agents):
    proj = make_project(passing=True)
    fake_agents()
    _invoke(["run", "инструкция", "--project", str(proj), "--dry-run",
             "--json"])
    out = capsys.readouterr().out
    saved = (proj / ".ai-brain" / "last_run.json").read_text(
        encoding="utf-8")
    assert json.loads(saved) == json.loads(out)  # файлът = stdout


def test_run_json_blocked_reports_failure(capsys, make_project,
                                          fake_agents):
    """Неуспехът също е JSON с ok=false и exit_code=1 (не stack trace)."""
    proj = make_project(passing=False)
    fake_agents()
    code = _invoke(["run", "инструкция", "--project", str(proj),
                    "--dry-run", "--json"])
    assert code == 1
    data = _stdout_json(capsys)
    assert data["ok"] is False
    assert data["exit_code"] == 1
    assert data["state"] == "blocked"
    assert data["counts"]["passed"] == 0


def test_status_json_after_run_lists_tasks(capsys, make_project,
                                           fake_agents):
    proj = make_project(passing=True)
    fake_agents()
    _invoke(["run", "инструкция", "--project", str(proj), "--dry-run",
             "--json"])
    capsys.readouterr()  # изчистване
    code = _invoke(["status", "--project", str(proj), "--json"])
    assert code == 0
    data = _stdout_json(capsys)
    assert data["state"] == "done"
    assert data["counts"] == {"total": 1, "passed": 1}
    assert data["tasks"][0]["id"] == "T1"
    # бюджет и журнал са частеж от машиночитаемия отчет
    assert "budget" in data and "journal_tail" in data
