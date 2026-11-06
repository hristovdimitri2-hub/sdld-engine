"""CLI: python -m engine.cli {run|resume|status} ...

Exit codes: 0 = done, 1 = blocked/paused, 2 = лоша употреба.

--json (05.11.2026, точка 1): stdout е ЕДИН валиден JSON обект за
външен агент (VisiCode/Cline); човешките съобщения отиват на stderr.
Копие на отговора се записва в .ai-brain/last_run.json.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _add_run_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--project", default="examples/todo-vat/project",
                   help="папката на целевия проект")
    p.add_argument("--dry-run", action="store_true",
                   help="принудителен dry режим (без HTTP, без пари)")
    p.add_argument("--dry-dir", help="папка с dry-run отговори")
    p.add_argument("--dry-code", help="папка с кода, който инженерът пише")
    p.add_argument("--budget-limit", type=float,
                   help="надстрой лимита от policy.json (за тест на pause/resume)")
    p.add_argument("--json", action="store_true",
                   help="stdout = само JSON (за VisiCode/външен агент)")
    p.add_argument("--debug", action="store_true")


# ---------------------------------------------------------------- отчет


def _safe_json(path: Path):
    """Прочитай JSON, без да гръмваш: счупен/липсващ → None."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _journal_tail(brain: Path, n: int = 5) -> list[dict]:
    """Последните n реда от journal.tsv (append-only история на опитите)."""
    p = brain / "journal.tsv"
    if not p.exists():
        return []
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln]
    if not lines:
        return []
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) != len(header):
            continue
        rows.append(dict(zip(header, parts)))
    return rows[-n:]


def build_report(project: Path, *, command: str, exit_code: int,
                 mode: str, instruction: str = "",
                 limit_usd: float | None = None) -> dict:
    """Машиночитаем отчет от файловете в .ai-brain (никога не гръмва)."""
    from . import SUITE_LAST_RUN, SUITE_TESTS_PASSED, __version__

    brain = project / ".ai-brain"
    state = _safe_json(brain / "state.json")
    plan = _safe_json(brain / "plan.json")
    budget = _safe_json(brain / "budget.json") or {}
    errors: list[str] = []
    for name, data in (("state.json", state), ("plan.json", plan)):
        if (brain / name).exists() and data is None:
            errors.append(f"{name} не се чете (счупен JSON)")
    state = state or {}
    plan = plan or {}
    tasks = [
        {"id": t.get("id", "?"), "title": t.get("title", ""),
         "state": t.get("state", "?"), "attempts": t.get("attempts", 0)}
        for t in plan.get("tasks", [])
    ]
    report = {
        "tool": "sdld-engine",
        "version": __version__,
        "command": command,
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "mode": mode,
        "project": str(project),
        "instruction": instruction,
        "state": state.get("state", "no_state"),
        "last_gate": state.get("last_gate", ""),
        "tasks": tasks,
        "counts": {"total": len(tasks),
                   "passed": sum(1 for t in tasks if t["state"] == "passed")},
        "budget": {"limit_usd": limit_usd,
                   "spent_usd": float(budget.get("spent", 0.0) or 0.0)},
        "journal_tail": _journal_tail(brain),
        "errors": errors,
        # The suite size as a dated measurement, so a CI step can compare the
        # number this tool reports against what pytest actually collected
        # without scraping a document. See tests/test_suite_count.py.
        "suite": {"tests_passed": SUITE_TESTS_PASSED,
                  "measured_at": SUITE_LAST_RUN},
    }
    return report


def _emit_report(report: dict, project: Path) -> None:
    """Един JSON ред на stdout + копие в .ai-brain/last_run.json."""
    text = json.dumps(report, ensure_ascii=False)
    print(text)
    try:
        brain = project / ".ai-brain"
        brain.mkdir(parents=True, exist_ok=True)
        (brain / "last_run.json").write_text(text, encoding="utf-8")
    except Exception as e:
        print(f"last_run.json не е записан: {e}", file=sys.stderr)


# ---------------------------------------------------------------- команди


def cmd_status(args) -> int:
    project = Path(args.project).resolve()
    if getattr(args, "json", False):
        report = build_report(project, command="status", exit_code=0,
                              mode="")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    brain = project / ".ai-brain"
    state = {}
    if (brain / "state.json").exists():
        state = json.loads((brain / "state.json").read_text(encoding="utf-8"))
    plan = {}
    if (brain / "plan.json").exists():
        plan = json.loads((brain / "plan.json").read_text(encoding="utf-8"))
    print(f"проект:  {project}")
    print(f"state:   {state.get('state', '(няма записано състояние)')}")
    print(f"gate:    {state.get('last_gate', '-')}")
    tasks = plan.get("tasks", [])
    passed = sum(1 for t in tasks if t.get("state") == "passed")
    print(f"задачи:  {passed}/{len(tasks)} минали гейта")
    for t in tasks:
        print(f"  - [{t.get('state')}] {t.get('id')} {t.get('title')} "
              f"(опити: {t.get('attempts', 0)})")
    hist = state.get("history", [])
    if hist:
        print("последни преходи:")
        for h in hist[-5:]:
            print(f"  {h['at']} {h['from']} -> {h['to']} ({h['gate']})")
    return 0


def main(argv=None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(
        prog="engine",
        description="Автономен инженерен двигател — сглобка v0.2.0",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="пусни задача през целия цикъл")
    p_run.add_argument("instruction", help="инструкцията на човека")
    _add_run_flags(p_run)

    p_res = sub.add_parser("resume", help="възобнови paused/blocked изпълнение")
    _add_run_flags(p_res)

    p_st = sub.add_parser("status", help="покажи състоянието на проект")
    p_st.add_argument("--project", default="examples/todo-vat/project")
    p_st.add_argument("--json", action="store_true",
                      help="stdout = само JSON (за VisiCode/външен агент)")

    args = ap.parse_args(argv)

    from .config import load_policy

    if args.cmd == "status":
        return cmd_status(args)

    policy = load_policy()
    if args.dry_run:
        policy.mode = "dry"

    from . import loop

    json_out = bool(getattr(args, "json", False))
    instruction = args.instruction if args.cmd == "run" else ""

    def _call() -> int:
        return loop.run(
            instruction,
            args.project,
            policy=policy,
            dry_dir=args.dry_dir,
            dry_code=args.dry_code,
            debug=args.debug,
            resume=(args.cmd == "resume"),
            budget_limit=args.budget_limit,
        )

    if json_out:
        # човешкият поток → stderr; stdout остава само за JSON
        try:
            with contextlib.redirect_stdout(sys.stderr):
                code = int(_call() or 0)
        except Exception as e:  # никога stack trace без JSON
            print(f"CLI: {type(e).__name__}: {e}", file=sys.stderr)
            code = 1
        project = Path(args.project).resolve()
        report = build_report(project, command=args.cmd, exit_code=code,
                              mode=policy.mode, instruction=instruction,
                              limit_usd=policy.limit_usd)
        if code not in (0, 1):
            report["errors"].append(f"неочакван exit код {code}")
        _emit_report(report, project)
        sys.exit(code)

    sys.exit(_call())


if __name__ == "__main__":
    main()
