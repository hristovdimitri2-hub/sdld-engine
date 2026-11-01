# SDLD Engine v0.1.1 — автономен инженерен двигател

Спецификация: [ARCHITECTURE.md](ARCHITECTURE.md). Малък, проверим цикъл:
договор → план → инструменти → реални тестове → одит. Никакви големи
предположения.

**Философия:** dry-run преди жив режим, гейтът винаги е реален тест, $0 в dry.

---

## одит → поправки (v0.1.1, 01.11.2026)

Външен одит на v0.1.0 намери **6 дефекта — поправени са 6/6**, всеки първо с
**възпроизвеждащ (червен) тест**, после със зелен:

| # | Дефект | Поправка | Тест |
|---|---|---|---|
| 1 (критичен) | Инженерът можеше да пренапише `tests/`, `.ai-brain/`, `config/` и да си занули бюджета/досието | Забрана за запис в пазените пътища (`loop._write_file`) + хеш на тестовете преди/след гейта | `tests/test_security.py` |
| 2 (висок) | Бюджетът се проверяваше само преди старта; живите разходи — фиксрана оценка | `precheck` преди **всеки** опит/одит; запис на **реалната цена** от отговора на API (`_extract_cost`) | `tests/test_budget.py` |
| 3 (висок) | Гейтът наследяваше цялата среда → `OPENROUTER_API_KEY` стигаше до кода на проекта | Allowlist среда за гейта (`gates.gate_env`) — никакви ключове | `test_gate_never_sees_secret_env` |
| 4 (среден) | Счупен `state.json` изглеждаше като чист draft; записите не бяха атомарни | `CorruptBrain` спира ясно (exit 1, без презапис); записи през `.tmp` + `os.replace` | `tests/test_memory.py` |
| 5 (среден) | Само Contract/Plan се валидираха — объркан одитор ставаше празен verdict | Pydantic схеми за всеки отговор: `EngineerReply`, `AuditorReply`, `EscalationReply` | `tests/test_replies.py` |
| 6 (нисък) | Мъртъв код; resume брои и приключените задачи; `placeholder` = фалшива тревога | Махнати `judge.merge`/`ExpertVerdict`; `remaining_need()` брои само оставащите; `placeholder` извън BANNED | `tests/test_budget.py`, `tests/test_judge.py` |

Допълнително: новите тестове хванаха **и собствен бъг на поправката** —
`__pycache__`, създаден от самия гейт, се броеше за „мутация“ (лъжлив FAIL на
първия опит). Гардът вече игнорира байткод кешовете.

**Приемане:** `51 passed`; трите E2E минават **от чисти копия** (готовият `src/`
се изтрива преди прогона — методът на одита).

---

## Изисквания

- Python **3.10+** (тествано на 3.12)
- `pip install -r requirements.txt` (pydantic, pytest)
- НЯМА нужда от API ключ за dry-run

## Бърз старт (PowerShell — това, което е тествано)

```powershell
python -m pytest -q            # 51 теста, <2s

# 1) щастлив път — ЧИСТО копие (src изтрит → инженерът го пише)
Copy-Item -Recurse -Force examples\todo-vat\project scratch
Remove-Item -Recurse -Force scratch\src, scratch\.ai-brain -ErrorAction SilentlyContinue
python -m engine.cli run "Направи модул за ДДС" \
    --project scratch --dry-run
# → exit 0, state: done (gate = реални unittest тестове)

# 2) блокиран път — инженерът връща счупен код от примерите
Remove-Item -Recurse -Force scratch -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force examples\todo-vat\project scratch
Remove-Item -Recurse -Force scratch\src, scratch\.ai-brain -ErrorAction SilentlyContinue
python -m engine.cli run "Направи модул за ДДС" \
    --project scratch --dry-run --dry-code examples\dryrun-bad\code
# → exit 1, state: blocked (3 опита → ескалация → G3 → G5)

# 3) бюджетна пауза → продължение
Remove-Item -Recurse -Force scratch -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force examples\todo-vat\project scratch
Remove-Item -Recurse -Force scratch\src, scratch\.ai-brain -ErrorAction SilentlyContinue
python -m engine.cli run "Направи модул за ДДС" \
    --project scratch --dry-run --budget-limit 0.1
# → exit 1, state: paused_budget (G2b; лимит 0.1 < нужните 0.5)
python -m engine.cli resume --project scratch --dry-run --budget-limit 5
# → exit 0, state: done (G2-resume)
```

`status` показва: state, бюджет (spent/limit/entries) и feed (последните 10).

## Гейт и щат

| Задача | Гейт | Задача | Гейт |
|---|---|---|---|
| T1 withVAT | `python -m unittest discover -s tests` | ... | ... |

Exit: `0` = done · `1` = blocked/paused_budget · `2` = лоша употреба/скрито
състояние.

## Сигурност (всичко с тест)

- **Пазени пътища:** инженерът не може да пише в `tests/`, `.ai-brain/`,
  `config/`, `conftest.py`, `pytest.ini` — тестовете дава планът/човекът.
- **Хеш на тестовете** преди/след гейта: промяна по време на изпълнение =
  провал. `__pycache__` се игнорира (не е съдържание).
- **Чиста среда на гейта:** само allowlist (`PATH`, `SystemRoot`, ...) —
  никакви ключове към кода на проекта.
- **Бюджет:** `precheck` ПРЕДИ всеки платен опит (никога „плати после
  оплачи"); реална цена от API, оценка само ако API не я върне.
- **Атомарна памет:** `.tmp` + `os.replace`; счупен `state.json` спира с
  ясно съобщение и exit 1 — не се маскира като draft.
- **Схеми:** всеки отговор на модела минава през Pydantic; невалиден →
  ескалация „невалиден отговор", не мълчаливо default-поле.

## Структура

```text
engine/
  schemas.py    Contract, Plan, Task, FeedbackPacket, + валидни отговори
  config.py     палитри от policy.json (+ ENGINE_MODE=live|dry)
  state.py      G0..G5 преходи
  memory.py     .ai-brain/ — атомарни записи, CorruptBrain
  budget.py     precheck / запис на реална цена / remaining_need()
  gates.py      чиста среда + хеш-пазител на тестовете
  agents.py     dry локално; live едно место към OpenRouter
  judge.py      механичен judge (структурен + реален гейт)
  loop.py       цикълът; exit 0/1/2
  cli.py        python -m engine.cli {run|status|resume}
tests/          51 теста (бюджет, гейтове, съдия, памет, сигурност, отговори)
examples/       dry-run входове + проект с реални тестове (todo-vat)
```

## Режими

- **dry:** `ENGINE_MODE` не е нужно — по подразбиране `dry` в `config/policy.json`.
  Същото дърво на цикъла; тестовете и гейтът са реални; $0 извиквания към API.
- **live:** попълни `config/models`, сложи `OPENROUTER_API_KEY` в средата,
  после мини на `live`. **Демонстрация с ключ все още не е пускана.**

## Какво остава (v0.2 — по ARCHITECTURE.md)

- **SQLite-ish store:** сега паметта е JSON файлове под `.ai-brain/`.
- **Диалектичен/експертен цикъл и жив LLM-съдия:** сега съдията е
  механичен (структурни проверки + реален гейт); ExpertVerdict махнат като
  мъртъв код — да се върне само ако се ползва.
- **Git worktrees/паралелизъм, Tool Gateway, риск-политики:** не са правени.
- **Откриване на проекти и дашборд:** не са правени.

Автор: Dimitri Hristov · лиценз: MIT
