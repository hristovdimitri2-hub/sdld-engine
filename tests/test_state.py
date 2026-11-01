import pytest

from engine.schemas import ExecutionState as S
from engine.state import InvalidTransition, StateMachine


def test_happy_path_transitions():
    sm = StateMachine()
    assert sm.state == S.DRAFT
    sm.transition(S.INTAKE, "G0")
    sm.transition(S.PLANNED, "G1")
    sm.transition(S.ACTIVE, "G2")
    sm.transition(S.DONE, "G4")
    assert sm.state == S.DONE
    assert [h["gate"] for h in sm.history] == ["G0", "G1", "G2", "G4"]


def test_invalid_transition_raises():
    sm = StateMachine()
    with pytest.raises(InvalidTransition):
        sm.transition(S.DONE, "G4")  # draft -> done е забранено


def test_budget_pause_and_resume_path():
    sm = StateMachine()
    sm.transition(S.INTAKE, "G0")
    sm.transition(S.PLANNED, "G1")
    sm.transition(S.PAUSED_BUDGET, "G2b")
    sm.transition(S.ACTIVE, "G2-resume")
    assert sm.state == S.ACTIVE


def test_blocked_escalation_chain():
    sm = StateMachine()
    sm.transition(S.INTAKE, "G0")
    sm.transition(S.PLANNED, "G1")
    sm.transition(S.ACTIVE, "G2")
    sm.transition(S.ESCALATED, "G3")
    sm.transition(S.BLOCKED, "G5")
    assert sm.state == S.BLOCKED
