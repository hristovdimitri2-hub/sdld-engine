"""Индекс на паметта + префикс-конвенция в feed.md (модел: LLM Wiki,
Karpathy gist 442a6, 12.11.2026).

Две неща:
  1. `.ai-brain/index.md` — съдържателен каталог: файл → какво е → обновен
     кога + броеве (журнал/фийд). Генерира се автоматично; човекът и
     външен агент (VisiCode) виждат цялата памет от един файл.
  2. feed.md редове с категорийен таг: `- <ts> | <tag> | <текст>` —
     `grep "| gate |" feed.md` връща само събитията на гейта.

Първо червено (index.md не се записва; feed няма таг), после зелено.
"""
import re

from engine.memory import Memory  # червено: update_index не съществува


def _brain(proj):
    return Memory(proj / ".ai-brain")


FEED_LINE = re.compile(r"^- \d{4}-\d{2}-\d{2}T[\d:]+Z \| [a-z][a-z0-9_-]* \| .")


# --- 1. index.md -----------------------------------------------------------

def test_run_writes_index_with_catalog_rows(tmp_path, make_project,
                                            fake_agents):
    """След цикъл индексът съществува и изброява реално наличните файлове."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    fake_agents()
    code = loop.run("инструкция", str(proj), policy=load_policy())
    assert code == 0

    text = (proj / ".ai-brain" / "index.md").read_text(encoding="utf-8")
    assert ".ai-brain" in text and "индекс" in text
    # всеки съществуващ файл има ред с обяснение
    for name in ("state.json", "contract.json", "plan.json",
                 "journal.tsv", "feed.md", "budget.json"):
        assert name in text, f"липсва ред за {name} в index.md"
    # щастливият път генерира memory.md (_finalize_memory) → редът е тук
    assert "memory.md" in text
    assert "|---" in text  # има таблица


def test_index_counts_journal_rows(tmp_path):
    """Броевете в индекса са от данните, не числа в текста (по духа на
    SUITE_TESTS_PASSED гарда)."""
    brain = _brain(tmp_path)
    from engine.journal import Journal

    j = Journal(brain)
    j.record(task="T1", round_no=1, status="keep")
    j.record(task="T1", round_no=2, status="discard")
    j.record(task="T1", round_no=3, status="crash")
    brain.write_text("feed.md", "- ред\n")

    text = brain.update_index()
    assert "journal.tsv: 3" in text
    assert "keep 1" in text and "discard 1" in text and "crash 1" in text
    assert "feed.md: 1" in text


def test_index_on_empty_brain_is_honest(tmp_path):
    """Празен мозък → индексът казва „няма още нищо“, не измисля файлове."""
    brain = _brain(tmp_path)
    text = brain.update_index()
    assert "няма" in text or "(празно)" in text
    assert "state.json" not in text


def test_status_rewrites_missing_index(tmp_path):
    """status подновява индекса — човекът/външен агент винаги може да го
    презареди, ако файлът е изтрит."""
    from engine import cli

    proj = tmp_path / "proj"
    brain = _brain(proj)
    brain.write_json("state.json", {"state": "done"})
    brain.update_index()
    brain.path("index.md").unlink()

    class _A:
        project = str(proj)
        json = False

    cli.cmd_status(_A())
    assert brain.path("index.md").exists()


# --- 2. тагове в feed.md ---------------------------------------------------

def test_feed_lines_carry_category_tag(tmp_path, make_project, fake_agents):
    """Всеки ред в feed.md е `<ts> | <tag> | <текст>` — grep-ваемо."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    fake_agents()
    assert loop.run("инструкция", str(proj), policy=load_policy()) == 0

    lines = [ln for ln in (proj / ".ai-brain" / "feed.md")
             .read_text(encoding="utf-8").splitlines() if ln]
    assert lines, "няма редове в feed.md"
    bad = [ln for ln in lines if not FEED_LINE.match(ln)]
    assert not bad, f"редове без таг: {bad[:3]}"


def test_feed_grep_by_tag_returns_only_that_kind(tmp_path, make_project,
                                                 fake_agents):
    """`grep "| gate |"` = само събития на гейта (конвенцията на LLM Wiki:
    консистентен префикс → unix инструменти стигат)."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    fake_agents()
    assert loop.run("инструкция", str(proj), policy=load_policy()) == 0

    lines = (proj / ".ai-brain" / "feed.md").read_text(
        encoding="utf-8").splitlines()
    gate = [ln for ln in lines if " | gate | " in ln]
    assert len(gate) == 1  # щастлив път: точно един ГЕЙТ PASS
    assert "ГЕЙТ PASS" in gate[0]
    # нито един ред не е извън познатите тагове
    known = {"intake", "plan", "budget", "gate", "attempt", "audit",
             "escalate", "resume", "error", "run"}
    for ln in lines:
        parts = ln.split(" | ")
        assert len(parts) == 3, f"счупен формат: {ln}"
        assert parts[1] in known, f"непознат таг: {ln}"


def test_feed_rejects_tag_that_would_break_the_line(tmp_path):
    """Таг с интервал/тръбичка/нов ред би счупил grep-конвенцията → ясна
    грешка, не мълчаливо счупен ред."""
    brain = _brain(tmp_path)
    for bad in ("Bad Tag", "a|b", "x\ny", ""):
        try:
            brain.feed("текст", tag=bad)
        except ValueError:
            continue
        raise AssertionError(f"tag={bad!r} трябваше да е отхвърлен")
