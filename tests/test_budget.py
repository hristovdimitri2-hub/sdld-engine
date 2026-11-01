import pytest

from engine.budget import BudgetPause, Ledger
from engine.config import Policy


def _policy(limit=5.0, soft=4.5):
    return Policy(
        {
            "mode": "dry",
            "budget": {
                "limit_usd": limit,
                "soft_pause_usd": soft,
                "allowance_per_task_usd": 0.5,
            },
        }
    )


def test_precheck_passes_when_under_limit():
    ledger = Ledger(_policy(limit=5.0))
    assert ledger.precheck(0.5) is None


def test_precheck_raises_budget_pause():
    ledger = Ledger(_policy(limit=0.1))
    with pytest.raises(BudgetPause):
        ledger.precheck(0.5)  # 0.5 > 0.1 → спираме ПРЕДИ плащане


def test_soft_limit_warning_only():
    ledger = Ledger(_policy(limit=5.0, soft=0.3))
    warning = ledger.precheck(0.5)  # над soft, под hard
    assert warning is not None


def test_record_accumulates_and_dry_is_zero():
    ledger = Ledger(_policy())
    ledger.record(0.0, "dry-run")
    ledger.record(0.0, "dry-run")
    assert ledger.spent_usd == 0.0
    assert len(ledger.entries) == 2


# --- одит №2: бюджетът се пази ПО ВРЕМЕ на цикъла, не само преди старта ---

def _brain_state(proj):
    from engine.memory import Memory

    return Memory(proj / ".ai-brain")


def test_midloop_budget_precheck_stops_before_overpay(tmp_path, make_project,
                                                       fake_agents):
    """Старото: 3 опита × 0.5 $ записани МИМО лимита → escalate → blocked.
    Новото: precheck преди всеки опит → paused_budget, опитите спират навреме."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=False)
    fake_agents()  # жив режим БЕЗ връщана цена → fallback 0.5 $/извикване
    policy = load_policy()
    policy.mode = "live"

    code = loop.run("инструкция", str(proj), policy=policy, budget_limit=1.5)

    assert code == 1
    brain = _brain_state(proj)
    assert brain.read_json("state.json")["state"] == "paused_budget"  # старо: blocked
    assert brain.read_json("budget.json")["spent"] <= 1.5
    plan = brain.read_json("plan.json")
    assert plan["tasks"][0]["attempts"] < 3  # старо: 3, харчени над лимита


def test_real_api_cost_is_recorded(tmp_path, make_project, fake_agents):
    """Ако API върне реална цена (0.7 $), тя се записва — не фиксирана оценка."""
    from engine import loop
    from engine.config import load_policy

    proj = make_project(passing=False)
    fake_agents(cost=0.7)
    policy = load_policy()
    policy.mode = "live"

    code = loop.run("инструкция", str(proj), policy=policy, budget_limit=1.0)

    brain = _brain_state(proj)
    assert code == 1
    assert brain.read_json("state.json")["state"] == "paused_budget"
    # intake 0.7 + architect 0.7 → G2 precheck (1.4 + 0.5 > 1.0) → pause
    assert brain.read_json("budget.json")["spent"] == pytest.approx(1.4)


# --- одит №6: resume брои само ОСТАВАЩИТЕ задачи, не всички ---

def test_remaining_need_counts_only_unpassed():
    from engine.budget import remaining_need
    from engine.schemas import Plan, Task

    plan = Plan(tasks=[
        Task(id="T1", title="готова", state="passed"),
        Task(id="T2", title="остава"),
    ])
    # старото: len(plan.tasks) * 0.5 = 1.0 → resume спираше излишно
    assert remaining_need(plan, 0.5) == 0.5


def test_remaining_need_zero_when_all_passed():
    from engine.budget import remaining_need
    from engine.schemas import Plan, Task

    plan = Plan(tasks=[Task(id="T1", title="а", state="passed")])
    assert remaining_need(plan, 0.5) == 0.0
