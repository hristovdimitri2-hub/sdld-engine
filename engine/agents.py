"""Слой към агентите (intake, architect, engineer, auditor, escalation).

Dry режим (policy.mode == "dry"): НЯМА HTTP, НЯМА пари — отговорите идват
от examples/dryrun/. Гейтът въпреки това е реален.

Жив режим (Phase 2): OpenAI-съвместим POST до OpenRouter — изисква
OPENROUTER_API_KEY в средата + попълнен models.default в policy.json.
Нетестиран без ключ (честно: оставаща работа, не се твърди, че работи).
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


class ToolError(Exception):
    """Грешка от инструмент — НЕ се поглъща мълчаливо (урок от TeamBox #1)."""


def call(policy, role: str, messages: list[dict], *, dry_dir=None,
         code_dir=None, debug: bool = False, cost_box: dict | None = None):
    """dry → локален отговор (0 $); live → реален API.

    cost_box: по желание се пълни с реалната цена (USD) на отговора —
    леджърът записва реалната цена, не оценка (одит №2).
    """
    if policy.is_dry:
        if cost_box is not None:
            cost_box["usd"] = 0.0
        reply = dry_reply(policy, role, dry_dir=dry_dir, code_dir=code_dir)
        if debug:
            preview = json.dumps(reply, ensure_ascii=False)[:400]
            print(f"[dry:{role}] {preview}")
        return reply
    return live_call(policy, role, messages, cost_box=cost_box)


def _extract_cost(data) -> float | None:
    """Реалната цена (USD) от отговора на OpenRouter — одит №2.

    Толериране на двете известни полета: response.cost / usage.cost.
    Ако липсва или не е число → None (извикващият ползва оценка).
    """
    try:
        resp = data.get("response") if isinstance(data, dict) else None
        if isinstance(resp, dict) and resp.get("cost") is not None:
            return float(resp["cost"])
        usage = data.get("usage") if isinstance(data, dict) else None
        if isinstance(usage, dict) and usage.get("cost") is not None:
            return float(usage["cost"])
    except (TypeError, ValueError):
        return None
    return None


# ---------------------------------------------------------------- dry режим

def _load(path: Path, *, required: bool = True):
    if not path.exists():
        if required:
            raise ToolError(f"липсва dry-run файл: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ToolError(f"счупен JSON в {path}: {e}") from e


def dry_reply(policy, role: str, *, dry_dir=None, code_dir=None):
    d = Path(dry_dir) if dry_dir else Path(policy.dryrun_dir)

    if role == "intake":
        return _load(d / "spec.json")

    if role == "architect":
        return _load(d / "plan.json")

    if role == "engineer":
        # Инженерът отговаря с tool_calls, които оркестраторът изпълнява наистина.
        summary = _load(d / "engineer.json", required=False) or {}
        cdir = Path(code_dir) if code_dir else (d / "code")
        calls = []
        if cdir.exists():
            for f in sorted(cdir.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(cdir).as_posix()
                    calls.append(
                        {
                            "tool": "write_file",
                            "args": {
                                "path": rel,
                                "content": f.read_text(encoding="utf-8"),
                            },
                        }
                    )
        return {"summary": summary.get("summary", ""), "tool_calls": calls}

    if role == "auditor":
        return _load(d / "audit.json")

    if role == "escalation":
        return _load(d / "escalate.json")

    raise ToolError(f"непозната роля за dry режим: {role}")


# ------------------------------------------------------------ жив режим (P2)

def live_call(policy, role: str, messages: list[dict],
              cost_box: dict | None = None):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ToolError(
            "Липсва OPENROUTER_API_KEY — живият режим не може да стартира. "
            "Пусни с --dry-run или задай ключа."
        )
    model = policy.models.get(role) or policy.models.get("default") or ""
    if not model:
        raise ToolError(
            "Попълни models.default в config/policy.json (какъв модел ползваме)."
        )
    payload = json.dumps(
        {"model": model, "messages": messages}, ensure_ascii=False
    ).encode("utf-8")
    req = urllib.request.Request(
        policy.base_url + "/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=policy.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # URLError/HTTPError — ясно нагоре, без маскиране
        raise ToolError(f"OpenRouter заявка провалена ({role}): {e}") from e
    if cost_box is not None:
        cost = _extract_cost(data)
        if cost is not None:
            cost_box["usd"] = cost
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"summary": content}
