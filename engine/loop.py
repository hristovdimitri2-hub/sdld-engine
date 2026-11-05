"""Оркестраторът — целият цикъл: intake → plan → budget → build → gate →
audit → done | blocked.

Изходни кодове (exit codes):
  0 = done (одитът е pass)
  1 = blocked / paused_budget (има човешка намеса или бюджетът спря)
  2 = лоша употреба на CLI (няма какво да се възобнови)

Уроци от TeamBox, приложени тук:
  #1 грешка при запис от инженера НЕ се поглъща → опит → ескалация;
  #2 неуспешен край НИКОГА не излиза с exit 0.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from . import agents, gates, judge
from .budget import BudgetPause, Ledger, remaining_need
from .journal import Journal
from .memory import CorruptBrain, Memory
from .program import ensure_program, load_program
from .schemas import (
    AuditorReply,
    Contract,
    EngineerReply,
    EscalationReply,
    ExecutionState as S,
    Plan,
    Task,
    Verdict,
)
from .state import StateMachine


def _as_dict(reply, role: str) -> dict:
    if isinstance(reply, dict):
        return reply
    if isinstance(reply, str):
        try:
            return json.loads(reply)
        except json.JSONDecodeError as e:
            raise agents.ToolError(f"{role} върна невалиден JSON: {e}") from e
    raise agents.ToolError(f"{role} върна {type(reply).__name__} вместо обект")


def _call_record(policy, role, messages, ledger, note, **kw) -> tuple[dict, float]:
    """Извикване на агент + запис на РЕАЛНАТА цена в леджъра (одит №2).

    Цената идва от отговора на API (cost_box); ако API не я върне —
    честна оценка от policy. В dry режим цената е $0.
    Връща (отговор, цена) — цената влиза и в журнала на опитите.
    """
    box: dict = {}
    reply = agents.call(policy, role, messages, cost_box=box, **kw)
    usd = box.get("usd")
    if usd is None:
        usd = 0.0 if policy.is_dry else policy.allowance_per_task_usd
    ledger.record(float(usd), note)
    return reply, float(usd)


# Пазени пътища: инженерът НЕ може да пише тук (одит №1, 01.11.2026).
# tests/    — иначе може да пренапише тестите и да мине гейта фалшиво;
# .ai-brain/— иначе може да занули състоянието/бюджета си;
# config/   — иначе може да смекчи политиката.
# conftest.py/pytest.ini — контролират колекцията/изпълнението на тестовете.
PROTECTED_TOP = frozenset({"tests", ".ai-brain", "config"})
PROTECTED_FILES = frozenset(
    {"conftest.py", "pytest.ini", "setup.cfg", "tox.ini", "program.md"}
)
# program.md е на ЧОВЕКА (модел autoresearch: human edits program.md) —
# инженерът не пренаписва собствените си инструкции.


def _write_file(project: Path, rel: str, content: str) -> Path:
    """Изпълнение на write_file от инженера.

    Пази се от излизане навън И от пазените пътища (одит №1).
    """
    root = project.resolve()
    target = (project / rel).resolve()
    if target != root and root not in target.parents:
        raise agents.ToolError(f"write_file извън проекта: {rel}")
    parts = PurePosixPath(target.relative_to(root).as_posix()).parts
    if parts and parts[0] in PROTECTED_TOP:
        raise agents.ToolError(
            f"запис в {parts[0]}/ е забранен за инженера: {rel} — "
            f"тестовете и досието дава човек/планът"
        )
    if len(parts) == 1 and parts[0] in PROTECTED_FILES:
        raise agents.ToolError(
            f"запис в {parts[0]} е забранен за инженера: той управлява "
            f"колекцията на тестовете"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")  # при EPERM/грешка → хвърля
    return target


def _with_program(program: str, msgs: list[dict]) -> list[dict]:
    """Program.md като контекст ПРЕДИ конкретното съобщение (модел
    autoresearch: агентът чете програмата при всяко извикване)."""
    if not program:
        return msgs
    return [{
        "role": "user",
        "content": "## program.md — програмата на екипа (редактира човек)\n"
                   + program,
    }] + msgs


def _escalate(policy, sm: StateMachine, brain: Memory, ledger, *, dry_dir,
              debug: bool, reason: str, program: str = "") -> int:
    if sm.state != S.ESCALATED:
        sm.transition(S.ESCALATED, "G3")
    brain.feed(f"ЕСКАЛАЦИЯ: {reason}")
    action = "stop_human"
    try:
        reply, _ = _call_record(
            policy,
            "escalation",
            _with_program(program,
                          [{"role": "user", "content": reason}]),
            ledger, "ескалация",
            dry_dir=dry_dir,
            debug=debug,
        )
        action = EscalationReply.model_validate(
            _as_dict(reply, "escalation")
        ).action
    except Exception as e:
        brain.feed(f"ескалация без отговор от агент: {e}")
    if action != "stop_human":
        brain.feed(
            f"action={action} не се поддържа в сглобката — третира се като "
            f"stop_human (оставаща работа: човешки цикъл за корекция)"
        )
    sm.transition(S.BLOCKED, "G5")
    print(f"⛔ БЛОКИРАНА: {reason} — нужна е човешка намеса (action={action})")
    return 1


def _finalize_memory(brain: Memory, sm: StateMachine, plan: Plan | None,
                     instruction: str) -> None:
    n = len(plan.tasks) if plan else 0
    done = sum(1 for t in plan.tasks if t.state == "passed") if plan else 0
    brain.append_memory(
        f"## run | state={sm.state.value} | задачи {done}/{n} | "
        f"gate={sm.last_gate} | {instruction[:80]}"
    )


def run(
    instruction: str,
    project_dir: str,
    *,
    policy,
    dry_dir: str | None = None,
    dry_code: str | None = None,
    debug: bool = False,
    resume: bool = False,
    budget_limit: float | None = None,
) -> int:
    if budget_limit is not None:
        policy.limit_usd = float(budget_limit)
    project = Path(project_dir).resolve()
    project.mkdir(parents=True, exist_ok=True)

    brain = Memory(project / ".ai-brain")
    ledger = Ledger(policy, brain)
    journal = Journal(brain)

    # program.md: създава се веднъж от шаблона, после човекът го редактира;
    # агентите го получават във всяко извикване (модел autoresearch).
    ensure_program(project)
    program_text = load_program(project)

    if resume:
        try:
            sm = StateMachine.load(brain)
        except CorruptBrain as e:
            # одит №4: счупен state.json спира ЯСНО — не се прави на draft
            print(
                f"❌ СЧУПЕН .ai-brain/state.json: {e}\n"
                f"   Поправи го ръчно — tasks.jsonl/feed.md са четими, "
                f"нищо не се е загубило."
            )
            return 1
        if sm.state not in (S.PAUSED_BUDGET, S.BLOCKED, S.ESCALATED):
            print(f"Няма какво да се възобнови — state={sm.state.value}")
            return 2
        if not brain.exists("plan.json"):
            brain.feed("resume без запазен plan.json — нищо за продължаване")
            return 2
    else:
        sm = StateMachine(brain=brain)
        sm.save(brain)

    plan: Plan | None = None
    contract: Contract | None = None

    try:
        # ------------------------------------------------ G0/G1 или resume
        if resume:
            contract = Contract.model_validate(brain.read_json_strict("contract.json"))
            plan = Plan.model_validate(brain.read_json_strict("plan.json"))
            for t in plan.tasks:
                if t.state != "passed":
                    t.attempts = 0
                    t.state = "planned"
            if sm.state == S.PAUSED_BUDGET:
                need = remaining_need(plan, policy.allowance_per_task_usd)
                try:
                    ledger.precheck(need)
                except BudgetPause as e:
                    print(f"⏸ БЮДЖЕТ (отново): {e} — увеличи лимита или изчакай.")
                    return 1
                sm.transition(S.ACTIVE, "G2-resume")
                brain.feed(f"resume: бюджетът стига → active (лимит {policy.limit_usd} $)")
            else:  # BLOCKED / ESCALATED
                sm.transition(S.ACTIVE, "G-resume")
                brain.feed(f"resume от {sm.history[-1]['from']} → продължаваме")
        else:
            # G0 intake → валиден Contract
            reply, _ = _call_record(
                policy, "intake",
                _with_program(program_text,
                              [{"role": "user", "content": instruction}]),
                ledger, "intake",
                dry_dir=dry_dir, debug=debug,
            )
            contract = Contract.model_validate(_as_dict(reply, "intake"))
            sm.transition(S.INTAKE, "G0")
            brain.write_json("contract.json", contract.model_dump())
            brain.feed(
                f"G0 intake: „{contract.name}“ — "
                f"{len(contract.acceptance_criteria)} критерии"
            )

            # G1 plan → валиден Plan
            reply, _ = _call_record(
                policy, "architect",
                _with_program(program_text, [
                    {"role": "user", "content": instruction},
                    {"role": "assistant",
                     "content": json.dumps(contract.model_dump(), ensure_ascii=False)},
                ]),
                ledger, "architect",
                dry_dir=dry_dir, debug=debug,
            )
            plan = Plan.model_validate(_as_dict(reply, "architect"))
            if plan.contract_id and plan.contract_id != contract.id:
                brain.feed(
                    f"внимание: plan.contract_id={plan.contract_id} ≠ "
                    f"contract.id={contract.id}"
                )
            sm.transition(S.PLANNED, "G1")
            brain.write_json("plan.json", plan.model_dump())
            brain.feed(f"G1 plan: {len(plan.tasks)} задачи")

            # G2 бюджетен pre-check (спираме ПРЕДИ скъпо действие)
            need = len(plan.tasks) * policy.allowance_per_task_usd
            warning = ledger.precheck(need)
            if warning:
                brain.feed(warning)
            sm.transition(S.ACTIVE, "G2")
            brain.feed(
                f"G2 бюджет ок: нужно {need:.2f} $ / лимит {policy.limit_usd:.2f} $"
            )

        # -------------------------------------------------- изпълнение
        assert plan is not None
        max_attempts = policy.gate_max_attempts

        for task in plan.tasks:
            if task.state == "passed":
                continue
            last_feedback: str = ""
            attempt = 0
            while attempt < max_attempts:
                # одит №2: спираме ПРЕДИ поредния (платен) опит, не след
                # като сме го платили. BudgetPause излиза ИЗВЪН вътрешния
                # try (той е по-долу) и стига до глобалния handler.
                ledger.precheck(policy.allowance_per_task_usd)
                attempt += 1
                task.attempts += 1
                prev_loc = journal.last_loc(task.id)  # база за простотата
                attempt_usd = 0.0
                # --- build (инженерът → tool_calls → реален запис)
                try:
                    reply, attempt_usd = _call_record(
                        policy, "engineer",
                        _with_program(program_text, [
                            {"role": "user",
                             "content": json.dumps(
                                 {"task": task.model_dump(),
                                  "feedback": last_feedback},
                                 ensure_ascii=False,
                             )},
                        ]),
                        ledger, f"{task.id} опит {attempt}",
                        dry_dir=dry_dir, code_dir=dry_code, debug=debug,
                    )
                    reply = _as_dict(reply, "engineer")
                    eng = EngineerReply.model_validate(reply)  # одит №5
                    calls = [tc.model_dump() for tc in eng.tool_calls]
                    if not calls:
                        raise agents.ToolError(
                            f"инженерът не върна tool_calls (опит {attempt})"
                        )
                    for c in calls:
                        if c.get("tool") != "write_file":
                            raise agents.ToolError(
                                f"непознат tool: {c.get('tool')}"
                            )
                        args = c.get("args") or {}
                        if "path" not in args:
                            raise agents.ToolError("write_file без path")
                        _write_file(project, args["path"], args.get("content", ""))
                    # записът на цената вече стана при самото извикване
                    # (_call_record) — преди write-ите, защото моделът е
                    # платен дори ако write-ът се провали (одит №2)
                except Exception as e:
                    task.last_error = str(e)
                    brain.feed(f"{task.id} опит {attempt}: грешка при запис — {e}")
                    # журнал: опитът гръмна ПРЕДИ гейта → crash (не мълчание)
                    journal.record(
                        task=task.id, round_no=attempt, status="crash",
                        loc=judge.count_loc(project), usd=attempt_usd,
                        description=f"грешка при запис: {e}",
                    )
                    brain.write_json("plan.json", plan.model_dump())
                    continue  # механичен ретрай

                # --- gate (реални тестове, винаги) + kill-rule (таймаут)
                ok, out, dur = gates.run_gate(
                    policy.gate_command, project, timeout=policy.gate_timeout_s
                )
                loc = judge.count_loc(project)
                fb = judge.feedback(task, ok, out, attempt, project,
                                    loc=loc, prev_loc=prev_loc)
                journal.record(
                    task=task.id, round_no=attempt,
                    status="keep" if fb.verdict == Verdict.PASS else "discard",
                    gate_s=dur, loc=loc, usd=attempt_usd,
                    description=fb.human_readable.split("\n")[0][:300],
                )
                brain.append_jsonl("tasks.jsonl", json.loads(fb.model_dump_json()))
                brain.write_json("plan.json", plan.model_dump())
                last_feedback = fb.human_readable

                if fb.verdict == Verdict.PASS:
                    task.state = "passed"
                    task.last_error = ""
                    brain.feed(f"ГЕЙТ PASS {task.id} (опит {attempt}, {dur:.1f}s)")
                    break
                brain.feed(f"ГЕЙТ FAIL {task.id} (опит {attempt}/{max_attempts})")
                if debug and out:
                    print(out[-1200:])
            else:
                # ретраите свършиха → ескалация (не излизаме с 0!)
                return _escalate(
                    policy, sm, brain, ledger, dry_dir=dry_dir, debug=debug,
                    reason=f"гейтът на {task.id} провали {max_attempts} пъти "
                           f"подред",
                    program=program_text,
                )

            brain.write_json("plan.json", plan.model_dump())

        # -------------------------------------------------- G4 одит
        done_n = sum(1 for t in plan.tasks if t.state == "passed")
        ledger.precheck(policy.allowance_per_task_usd)  # одит №2
        reply, _ = _call_record(
            policy, "auditor",
            _with_program(program_text, [
                {"role": "user",
                 "content": json.dumps(
                     {"contract": contract.model_dump() if contract else None,
                      "tasks": [t.model_dump() for t in plan.tasks],
                      "passed": done_n, "total": len(plan.tasks)},
                     ensure_ascii=False,
                 )},
            ]),
            ledger, "одит",
            dry_dir=dry_dir, debug=debug,
        )
        try:
            av = AuditorReply.model_validate(_as_dict(reply, "auditor"))
        except ValidationError as e:
            # одит №5: обект без валиден verdict НЕ става празен verdict
            return _escalate(
                policy, sm, brain, ledger, dry_dir=dry_dir, debug=debug,
                reason=f"одитът върна невалиден отговор: {e.errors()}",
                program=program_text,
            )
        verdict = av.verdict.value

        if verdict == "pass" and done_n == len(plan.tasks):
            sm.transition(S.DONE, "G4")
            brain.feed(f"G4 одит pass — екипът завърши {done_n}/{len(plan.tasks)}")
            _finalize_memory(brain, sm, plan, instruction)
            print(f"✅ Екипът завърши: {done_n}/{len(plan.tasks)} задачи")
            return 0

        return _escalate(
            policy, sm, brain, ledger, dry_dir=dry_dir, debug=debug,
            reason=f"одитът върна verdict={verdict} ({done_n}/{len(plan.tasks)} "
                   f"готови)",
            program=program_text,
        )

    except BudgetPause as e:
        if sm.can(S.PAUSED_BUDGET):
            sm.transition(S.PAUSED_BUDGET, "G2")
        brain.feed(f"БЮДЖЕТ СПИРА: {e}")
        print(f"⏸ БЮДЖЕТ СПИРА: {e}\n   Пусни: resume --budget-limit <сума>")
        return 1
    except CorruptBrain as e:
        # одит №4: счупен .ai-brain/ спира ясно; нищо не се презаписва
        print(
            f"❌ СЧУПЕН ФАЙЛ В .ai-brain: {e}\n"
            f"   Поправи ръчно — tasks.jsonl/feed.md са четими, "
            f"нищо не е загубено."
        )
        return 1
    except Exception as e:
        brain.feed(f"ВЪТРЕШНА ГРЕШКА: {type(e).__name__}: {e}")
        if debug:
            traceback.print_exc()
        else:
            print(f"❌ Вътрешна грешка: {e} (пусни с --debug за детайли)")
        if sm.can(S.BLOCKED):
            sm.transition(S.BLOCKED, "G5")
        _finalize_memory(brain, sm, plan, instruction)
        return 1
