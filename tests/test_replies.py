"""Дефект №5 от външния одит (01.11.2026): само Contract/Plan минаваха
през Pydantic; отговорите на инженера, одитора и ескалацията минаваха
през .get(). Объркан отговор на одитора ставаше ПРАЗЕН verdict →
безсмислена ескалация „verdict=“.

Правило: всеки отговор на модела се валидира със схема; невалиден →
ясна ескалация „невалиден отговор“, не мълчаливо default-поле.
"""
import pytest
from pydantic import ValidationError

from engine.schemas import (
    AuditorReply,
    EngineerReply,
    EscalationReply,
    Verdict,
)


def test_auditor_missing_or_garbage_verdict_rejected():
    with pytest.raises(ValidationError):
        AuditorReply.model_validate({"message": "без verdict"})
    with pytest.raises(ValidationError):
        AuditorReply.model_validate({"verdict": 42})
    with pytest.raises(ValidationError):
        AuditorReply.model_validate({"verdict": "може би"})


def test_auditor_valid_reply_passes():
    r = AuditorReply.model_validate(
        {"verdict": "pass", "confidence": 0.9, "blocking_issues": []}
    )
    assert r.verdict is Verdict.PASS


def test_engineer_reply_tool_calls_typed():
    r = EngineerReply.model_validate(
        {"summary": "х",
         "tool_calls": [{"tool": "write_file",
                         "args": {"path": "a.py", "content": "x = 1"}}]}
    )
    assert r.tool_calls[0].tool == "write_file"
    assert r.tool_calls[0].args["path"] == "a.py"

    empty = EngineerReply.model_validate({"summary": "без инструменти"})
    assert empty.tool_calls == []

    with pytest.raises(ValidationError):
        EngineerReply.model_validate({"tool_calls": "не списък"})


def test_escalation_reply_validated():
    r = EscalationReply.model_validate({"action": "stop_human"})
    assert r.action == "stop_human"
    with pytest.raises(ValidationError):
        EscalationReply.model_validate({"action": ["не низ"]})


def test_loop_reports_invalid_auditor_verdict(tmp_path, make_project,
                                              fake_agents):
    """Пълният цикъл: обект БЕЗ verdict → ескалация „невалиден отговор“.
    Старото: verdict="" → feed „verdict=“ и същият объркан отговор се
    третираше като отказ на съдията."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=True)
    fake_agents(auditor={"message": "реших без verdict"})
    policy = load_policy()

    code = loop.run("инструкция", str(proj), policy=policy)

    assert code == 1
    feed = (proj / ".ai-brain" / "feed.md").read_text(encoding="utf-8")
    assert "невалиден отговор" in feed
    assert "verdict=" not in feed


def test_escalation_garbage_reply_falls_back_to_stop_human(
        tmp_path, make_project, fake_agents):
    """№5 (ескалация): отговор БЕЗ валидно action (число вместо низ) не
    се превръща в произволно действие на агента — безопасният fallback е
    stop_human, с бележка в лентата, и цикълът пак излиза с exit 1.

    Старото: reply.get(...) → action=7 мина без проверка (свободна
    речник, одит №5); схемата сега отхвърля и _escalate записва защо.
    """
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=False)  # гейтът провали 3 пъти → ескалация
    fake_agents(escalation={"action": 7, "reason": "боклук"})
    policy = load_policy()

    code = loop.run("инструкция", str(proj), policy=policy)

    assert code == 1
    feed = (proj / ".ai-brain" / "feed.md").read_text(encoding="utf-8")
    assert "ЕСКАЛАЦИЯ" in feed
    assert "ескалация без отговор" in feed  # схемата отхвърли → бележка
    state = (proj / ".ai-brain" / "state.json").read_text(encoding="utf-8")
    assert '"blocked"' in state  # не е тръгнало по action=7
