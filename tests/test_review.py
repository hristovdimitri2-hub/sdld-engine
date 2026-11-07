"""Review-фаза — преди ВСЕКИ инженерски опит агентът получава последните
редове от journal.tsv + git log -10 на проекта (модел: Phase 1 Review от
autoresearch). Първо червено (модулът не съществува), после зелено.
"""
import shutil

import pytest

from engine.review import build, git_log, journal_tail  # червено: ImportError


def _brain(proj):
    from engine.memory import Memory

    return Memory(proj / ".ai-brain")


def _journal(proj):
    from engine.journal import Journal

    return Journal(_brain(proj))


GIT = shutil.which("git")


# --- journal_tail: последните N реда от журнала -----------------------------

def test_journal_tail_returns_last_rows_with_header(tmp_path):
    j = _journal(tmp_path)
    for i in range(1, 6):
        j.record(task=f"T{i}", round_no=1, status="keep", loc=10 + i)
    tail = journal_tail(j, n=2)
    lines = tail.splitlines()
    assert lines[0].split("\t") == [
        "at", "task", "round", "status", "gate_s", "loc", "usd",
        "description",
    ]
    assert len(lines) == 3  # глава + последните 2 реда
    assert "T4" in lines[-2] and "T5" in lines[-1]  # по ред, най-новият последен
    # старите редове не се товарят (клетката task, не substring от времето)
    assert all("\tT1\t" not in line for line in lines)


def test_journal_tail_empty_journal_is_honest(tmp_path):
    """Първият опит няма история — казваме го, вместо празен блок."""
    assert "първият опит" in journal_tail(_journal(tmp_path), n=8)


# --- git_log: последните 10 комита, без комити = ясна бележка ---------------

@pytest.mark.skipif(not GIT, reason="git не е наличен")
def test_git_log_shows_recent_commits(tmp_path):
    import subprocess

    proj = tmp_path / "repo"
    proj.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=proj,
                   check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=proj, check=True)
    for name in ("a.txt", "b.txt"):
        (proj / name).write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", name], cwd=proj, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"add {name}"],
                       cwd=proj, check=True)
    out = git_log(proj, n=10)
    assert "add b.txt" in out  # последният комит е най-отгоре
    assert "add a.txt" in out


def test_git_log_without_repo_returns_note_not_crash(tmp_path):
    plain = tmp_path / "без-репо"
    plain.mkdir()
    out = git_log(plain, n=10)
    assert isinstance(out, str) and out  # ясна бележка, не изключение
    assert "git" in out


# --- интеграция: инженерът получава Review-блок ПРЕДИ задачата --------------

def _capture(fake_agents, monkeypatch):
    """Слой върху fake_agents: запазва messages на всяко извикване."""
    from engine import agents as ag

    real = ag.call
    captured: dict[str, list] = {}

    def wrapper(policy, role, messages, **kw):
        captured.setdefault(role, []).append(messages)
        return real(policy, role, messages, **kw)

    monkeypatch.setattr(ag, "call", wrapper)
    return captured


def test_engineer_message_contains_review_before_task(tmp_path, make_project,
                                                      fake_agents,
                                                      monkeypatch):
    """Преди опита инженерът вижда journal + git log; редът е
    program → review → задача."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    # предистория: ред от по-раншен опит
    _journal(proj).record(task="T0", round_no=1, status="discard", loc=77,
                          description="стар провал")
    captured = _capture(fake_agents, monkeypatch)
    code = loop.run("инструкция", str(proj), policy=load_policy())
    assert code == 0

    msgs = captured["engineer"][0]
    contents = [m["content"] for m in msgs if m["role"] == "user"]
    review_i = next(i for i, c in enumerate(contents) if "## Review" in c)
    task_i = next(i for i, c in enumerate(contents) if '"task"' in c)
    assert review_i < task_i  # Review-ът е ПРЕДИ задачата
    review = contents[review_i]
    assert "journal.tsv" in review and "T0" in review  # ред от журнала
    assert "git log" in review
    # програмата остава най-отгоре
    assert "program.md" in contents[0]


def test_review_is_not_sent_to_other_roles(tmp_path, make_project,
                                           fake_agents, monkeypatch):
    """Review-фазата е само за инженера — одитор/ескалация не товарят
    историята (и не я виждат като свои редове)."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    captured = _capture(fake_agents, monkeypatch)
    code = loop.run("инструкция", str(proj), policy=load_policy())
    assert code == 0
    assert captured["auditor"]
    aud = captured["auditor"][0]
    assert not any("## Review" in m.get("content", "") for m in aud)
