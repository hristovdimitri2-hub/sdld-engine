"""Журнал на опитите — адаптация на results.tsv от karpathy/autoresearch.

Всеки опит оставя траен ред: keep | discard | crash. Историята се ЧЕТЕ,
а не се помни в главата на агента. Първо червено (модулът не съществува),
после зелено.
"""
from engine.journal import Journal  # червено: ImportError тук


def _brain(proj):
    from engine.memory import Memory

    return Memory(proj / ".ai-brain")


def test_record_creates_header_and_row(tmp_path):
    j = Journal(_brain(tmp_path))
    j.record(task="T1", round_no=1, status="keep", gate_s=1.25, loc=42,
             usd=0.0, description="минат гейт")
    text = (tmp_path / ".ai-brain" / "journal.tsv").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].split("\t") == [
        "at", "task", "round", "status", "gate_s", "loc", "usd", "description",
    ]
    row = lines[1].split("\t")
    assert row[1] == "T1"
    assert row[2] == "1"
    assert row[3] == "keep"
    assert row[4] == "1.25"
    assert row[5] == "42"
    assert row[6] == "0.0"


def test_status_keep_discard_crash(tmp_path):
    j = Journal(_brain(tmp_path))
    for status in ("keep", "discard", "crash"):
        j.record(task="T1", round_no=1, status=status)
    rows = j.rows()
    assert [r["status"] for r in rows] == ["keep", "discard", "crash"]


def test_description_with_tabs_and_newlines_is_sanitized(tmp_path):
    """TSV се чупи от таб/нов ред в описанието — заменя се с интервал."""
    j = Journal(_brain(tmp_path))
    j.record(task="T1", round_no=1, status="discard",
             description="ред1\tтаб\nред2")
    rows = j.rows()
    assert rows[0]["description"] == "ред1 таб ред2"
    # редът е един — няма счупен/разделен запис
    assert len((tmp_path / ".ai-brain" / "journal.tsv").read_text(
        encoding="utf-8").splitlines()) == 2


def test_last_loc_returns_latest_row_for_task(tmp_path):
    j = Journal(_brain(tmp_path))
    j.record(task="T1", round_no=1, status="discard", loc=10)
    j.record(task="T2", round_no=1, status="discard", loc=99)
    j.record(task="T1", round_no=2, status="keep", loc=7)
    assert j.last_loc("T1") == 7
    assert j.last_loc("T2") == 99
    assert j.last_loc("никой") is None


def test_last_loc_none_without_journal(tmp_path):
    """Първият опит няма предистория → няма от какво да се мери простотата."""
    j = Journal(_brain(tmp_path))
    assert j.last_loc("T1") is None


# --- интеграция: целият цикъл оставя_journal_редове -------------------------

def _journal_text(proj):
    return (proj / ".ai-brain" / "journal.tsv").read_text(encoding="utf-8")


def test_run_writes_keep_on_pass(tmp_path, make_project, fake_agents):
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    fake_agents()
    code = loop.run("инструкция", str(proj), policy=load_policy())
    assert code == 0
    assert "\tkeep\t" in _journal_text(proj)


def test_run_writes_discard_then_escalate(tmp_path, make_project, fake_agents):
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=False)
    fake_agents()
    policy = load_policy()
    code = loop.run("инструкция", str(proj), policy=policy, budget_limit=10.0)
    assert code == 1  # гейтът провали 3 пъти → ескалация
    rows = Journal(_brain(proj)).rows()
    assert [r["status"] for r in rows] == ["discard", "discard", "discard"]


def test_run_writes_crash_when_engineer_tool_unknown(tmp_path, make_project,
                                                     fake_agents):
    """Инженерът върна непознат инструмент → опитът е crash, не мълчаливо
    продължение (урок от TeamBox #1)."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    fake_agents(engineer={
        "summary": "луд инструмент",
        "tool_calls": [{"tool": "rm", "args": {"path": "/"}}],
    })
    code = loop.run("инструкция", str(proj), policy=load_policy(),
                    budget_limit=10.0)
    assert code == 1
    rows = Journal(_brain(proj)).rows()
    assert rows and all(r["status"] == "crash" for r in rows)
    assert "непознат" in rows[0]["description"]
