import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402  (sys.path е нагоре)

FAILING_TESTS = """import unittest

class T(unittest.TestCase):
    def test_fail(self):
        self.assertTrue(False)
"""

PASSING_TESTS = """import unittest

class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
"""


@pytest.fixture
def make_project(tmp_path):
    """Папка на проект с реални (успешващи/провалващи се) тестове за гейта."""

    def _make(passing: bool) -> pathlib.Path:
        proj = tmp_path / "project"
        (proj / "tests").mkdir(parents=True)
        (proj / "tests" / "test_gate.py").write_text(
            PASSING_TESTS if passing else FAILING_TESTS, encoding="utf-8"
        )
        return proj

    return _make


DEFAULT_REPLIES = {
    "intake": {
        "id": "C-T",
        "name": "тестов договор",
        "objective": "проверка на цикъла",
        "acceptance_criteria": ["един критерий"],
    },
    "architect": {
        "contract_id": "C-T",
        "tasks": [
            {"id": "T1", "title": "напиши src/x.py", "files": ["src/x.py"]}
        ],
    },
    "engineer": {
        "summary": "готово",
        "tool_calls": [
            {"tool": "write_file", "args": {"path": "src/x.py",
                                            "content": "X = 1\n"}}
        ],
    },
    "auditor": {"verdict": "pass"},
    "escalation": {"action": "stop_human"},
}


@pytest.fixture
def fake_agents(monkeypatch):
    """Подменя agents.call: без HTTP/пари, контролиран отговор и цена.

    cost=None → отговорът НЕ връща цена (тества fallback оценката);
    cost=0.7 → сякаш API е върнал реална цена (тества отчитането ѝ).
    """
    from engine import agents as ag

    def install(cost=None, **overrides):
        roles_seen: list[str] = []

        def fake(policy, role, messages, *, dry_dir=None, code_dir=None,
                 debug=False, cost_box=None):
            roles_seen.append(role)
            if cost_box is not None and cost is not None:
                cost_box["usd"] = cost
            if role in overrides:
                return dict(overrides[role])
            return dict(DEFAULT_REPLIES[role])

        monkeypatch.setattr(ag, "call", fake)
        return roles_seen

    return install
