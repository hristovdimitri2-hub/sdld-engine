"""CLI: python -m engine.cli {run|status|resume} ...

Exit codes: 0 = done, 1 = blocked/paused, 2 = лоша употреба.
"""
from __future__ import annotations

import argparse
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
    p.add_argument("--debug", action="store_true")


def cmd_status(args) -> int:
    project = Path(args.project).resolve() / ".ai-brain"
    state = {}
    if (project / "state.json").exists():
        state = json.loads((project / "state.json").read_text(encoding="utf-8"))
    plan = {}
    if (project / "plan.json").exists():
        plan = json.loads((project / "plan.json").read_text(encoding="utf-8"))
    print(f"проект:  {Path(args.project).resolve()}")
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
        description="Автономен инженерен двигател — сглобка v0.1.0",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="пусни задача през целия цикъл")
    p_run.add_argument("instruction", help="инструкцията на човека")
    _add_run_flags(p_run)

    p_res = sub.add_parser("resume", help="възобнови paused/blocked изпълнение")
    p_res.add_argument("--project", default="examples/todo-vat/project")
    p_res.add_argument("--dry-run", action="store_true")
    p_res.add_argument("--dry-dir")
    p_res.add_argument("--dry-code")
    p_res.add_argument("--budget-limit", type=float)
    p_res.add_argument("--debug", action="store_true")

    p_st = sub.add_parser("status", help="покажи състоянието на проект")
    p_st.add_argument("--project", default="examples/todo-vat/project")

    args = ap.parse_args(argv)

    from .config import load_policy

    if args.cmd == "status":
        return cmd_status(args)

    policy = load_policy()
    if args.dry_run:
        policy.mode = "dry"

    from . import loop

    if args.cmd == "run":
        code = loop.run(
            args.instruction,
            args.project,
            policy=policy,
            dry_dir=args.dry_dir,
            dry_code=args.dry_code,
            debug=args.debug,
            resume=False,
            budget_limit=args.budget_limit,
        )
    else:  # resume
        code = loop.run(
            "",
            args.project,
            policy=policy,
            dry_dir=args.dry_dir,
            dry_code=args.dry_code,
            debug=args.debug,
            resume=True,
            budget_limit=args.budget_limit,
        )
    sys.exit(code)


if __name__ == "__main__":
    main()
