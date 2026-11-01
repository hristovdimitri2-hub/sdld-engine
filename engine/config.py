"""Зареждане на config/policy.json + env override (ENGINE_MODE)."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class Policy:
    def __init__(self, data: dict):
        self.raw = data
        self.mode: str = data.get("mode", "dry")

        b = data.get("budget", {})
        self.limit_usd = float(b.get("limit_usd", 5.0))
        self.soft_pause_usd = float(b.get("soft_pause_usd", 4.5))
        self.allowance_per_task_usd = float(b.get("allowance_per_task_usd", 0.5))

        g = data.get("gate", {})
        self.gate_command: list[str] = list(g.get("command", []))
        self.gate_max_attempts = int(g.get("max_attempts", 3))

        self.dryrun_dir: Path = REPO_ROOT / data.get("dryrun", {}).get(
            "dir", "examples/dryrun"
        )

        self.models: dict = data.get("models", {})
        live = data.get("live", {})
        self.base_url: str = str(
            live.get("base_url", "https://openrouter.ai/api/v1")
        ).rstrip("/")
        self.timeout_s = int(live.get("timeout_s", 120))

    @property
    def is_dry(self) -> bool:
        return self.mode == "dry"


def load_policy(path: Path | None = None) -> Policy:
    path = path or (REPO_ROOT / "config" / "policy.json")
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"mode": "dry"}
    policy = Policy(data)
    env_mode = os.environ.get("ENGINE_MODE")
    if env_mode:
        policy.mode = env_mode
    return policy
