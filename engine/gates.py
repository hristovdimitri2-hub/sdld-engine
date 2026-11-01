"""Гейтът — винаги изпълнява РЕАЛНИ тестове (и в dry режим).

Никога не се твърди "тестовете минават" — гейтът връща истинския exit code
и изхода от тестовете. Командата идва от config/policy.json.
{python} се заменя с текущия интерпретатор (питаме се: кой python? — този, който ни пусна).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

MUTATED_MSG = "\n⚠ ТЕСТОВЕТЕ СА ПРОМЕНЕНИ ПО ВРЕМЕ НА ГЕЙТА — резултатът е невалиден"

# Байткод кешовете НЕ са тестове: unittest ги създава сам при първото
# изпълнение (иначе лъжливa „мутация“ на първия опит). Забраната за
# запис в tests/ (loop._write_file) пази от тайно подменяне на .pyc.
IGNORED_PARTS = frozenset({"__pycache__"})
IGNORED_SUFFIXES = (".pyc", ".pyo")

# одит №3: гейтът изпълнява кода на проекта (писан/пипан от модела),
# затова НЕ наследява цялата среда. Само минималният набор, нужен за
# стартиране на процеса — никакви ключове (OPENROUTER_API_KEY и пр.).
ENV_ALLOWLIST = (
    "PATH",
    "SystemRoot",
    "WINDIR",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "PYTHONIOENCODING",
    "PYTHONHASHSEED",
)


def gate_env() -> dict[str, str]:
    """Чиста среда за гейта: само allowlist-а, нищо друго."""
    return {k: os.environ[k] for k in ENV_ALLOWLIST if k in os.environ}


def tree_hash(root: Path) -> str | None:
    """SHA-256 на всички файлове под root (вкл. имена). None ако липсва."""
    if not root.is_dir():
        return None
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in IGNORED_PARTS for part in rel.parts):
            continue
        if rel.name.endswith(IGNORED_SUFFIXES):
            continue
        h.update(rel.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def run_gate(
    command: list[str], cwd: Path, timeout: int = 120
) -> tuple[bool, str, float]:
    """Връща (ok, output, duration_s). output е последните 4000 символа."""
    if not command:
        return True, "няма gate команда в policy — гейтът е пропуснат", 0.0
    cmd = [sys.executable if part == "{python}" else part for part in command]
    # одит №1, слой 2: хеш на тестовете ПРЕДИ и СЛЕД изпълнението —
    # ако кодът (или самият тест) ги промени по време на гейта, не вярваме на резултата.
    before = tree_hash(cwd / "tests")
    t0 = time.time()
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=gate_env(),  # одит №3: никакви ключове към кода на проекта
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, f"gate команда не е намерена: {' '.join(cmd)}", time.time() - t0
    except subprocess.TimeoutExpired:
        return False, f"gate timeout след {timeout}s", time.time() - t0
    out = (cp.stdout or "") + (cp.stderr or "")
    if before is not None and tree_hash(cwd / "tests") != before:
        out = (out + MUTATED_MSG)[-4000:]
        return False, out, time.time() - t0
    return cp.returncode == 0, out[-4000:], time.time() - t0
