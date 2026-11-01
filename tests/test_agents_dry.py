from engine import agents
from engine.config import load_policy


def test_dry_engineer_returns_real_write_calls():
    policy = load_policy()
    policy.mode = "dry"
    reply = agents.call(policy, "engineer", [{"role": "user", "content": "x"}])
    assert reply["tool_calls"], "инженерът трябва да върне поне един tool_call"
    call = reply["tool_calls"][0]
    assert call["tool"] == "write_file"
    assert call["args"]["path"] == "src/vat.py"
    assert "withVAT" in call["args"]["content"]


def test_dry_intake_is_valid_contract():
    from engine.schemas import Contract

    policy = load_policy()
    policy.mode = "dry"
    reply = agents.call(policy, "intake", [])
    contract = Contract.model_validate(reply)
    assert contract.acceptance_criteria, "договорът трябва да има критерии"


def test_dry_makes_no_http(monkeypatch):
    policy = load_policy()
    policy.mode = "dry"

    def boom(*a, **k):
        raise AssertionError("HTTP не бива да се докосва в dry режим")

    monkeypatch.setattr(agents.urllib.request, "urlopen", boom)
    agents.call(policy, "auditor", [])


# --- одит №2: реалната цена от отговора на API ---

def test_extract_cost_from_api_payload():
    assert agents._extract_cost({"response": {"cost": 0.123}}) == 0.123
    assert agents._extract_cost({"usage": {"cost": 0.5}}) == 0.5
    assert agents._extract_cost({"usage": {"prompt_tokens": 1}}) is None
    assert agents._extract_cost({}) is None
    assert agents._extract_cost({"response": {"cost": "bad"}}) is None
