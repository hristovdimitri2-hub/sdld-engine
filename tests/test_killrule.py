"""Kill-rule — тайм-бюджет на опит по модела на autoresearch
(5 мин фиксиран budget, 10 мин = убий и отхвърли).

Тук: гейтът има конфигурируем таймаут от policy.json; прекалено бавен
опит се убива и се третира като провал (не виси до безкрайност).
"""
from engine.config import Policy


def test_policy_gate_timeout_default_120():
    p = Policy({})
    assert p.gate_timeout_s == 120


def test_policy_gate_timeout_from_config():
    p = Policy({"gate": {"timeout_s": 7}})
    assert p.gate_timeout_s == 7


def test_run_gate_kills_overrun_and_marks_failure(tmp_path):
    from engine.gates import run_gate

    ok, out, dur = run_gate(
        ["{python}", "-c", "import time; time.sleep(30)"], tmp_path, timeout=1
    )
    assert ok is False
    assert "gate timeout" in out
    assert dur < 10  # убит НАИСТИНА след ~1s, не след 30s


def test_loop_passes_policy_timeout_to_gate(tmp_path, make_project,
                                            fake_agents, monkeypatch):
    """Таймаутът идва от policy.json — оркестраторът го предава на гейта."""
    from engine import gates, loop
    from engine.config import load_policy

    seen: dict = {}
    real = gates.run_gate

    def spy(command, cwd, timeout=120):
        seen["timeout"] = timeout
        return real(command, cwd, timeout=timeout)

    monkeypatch.setattr(gates, "run_gate", spy)
    proj = make_project(passing=True)
    fake_agents()
    policy = load_policy()
    policy.gate_timeout_s = 7
    code = loop.run("инструкция", str(proj), policy=policy)
    assert code == 0
    assert seen["timeout"] == 7
