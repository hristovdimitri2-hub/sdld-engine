# SDLD Engine — спецификационен лист (v0.2.0, 05.11.2026)

Една страница: **какво може, как се вика, какво липсва.** Всеки ред е
проверен с команда + реален изход: **88 pytest**, **3 E2E от чисти копия**,
CLI `--json` парсен от PowerShell (`ConvertFrom-Json`).

## 1. Какво е

Автономен инженерен двигател (Python): приема инструкция на български →
договор → план → инженерът пише код → **реален тестов гейт** → одит →
`done` или `blocked`. Няма големи предположения: всеки преход носи номер
(G0–G5), всеки опит оставя ред в журнал, неуспехът **никога** не излиза с
exit 0.

## 2. Изисквания

- Python **3.10+** (тествано 3.12) · `pip install -r requirements.txt`
- **Няма нужда от API ключ** в dry режим (по подразбиране)
- Работи на Windows/PowerShell (там е тествано)

## 3. Команди и exit кодове

| Команда | Какво прави |
|---|---|
| `python -m engine.cli run "инструкция" --project <папка> --dry-run` | целият цикъл веднъж |
| `python -m engine.cli resume --project <папка> --dry-run` | продължава paused/blocked |
| `python -m engine.cli status --project <папка>` | човешки отчет (state/задачи/преходи) |

Флагове: `--json` (машиночитаем изход, §4) · `--dry-code <папка>` (кодът,
който инженерът „връща") · `--dry-dir <папка>` (готови отговори) ·
`--budget-limit <$>` · `--debug`.

Exit: **0** = done (одитът е pass) · **1** = blocked / paused_budget /
счупен state · **2** = лоша употреба (няма какво да се възобнови).

## 4. `--json` — изходът за външен агент (VisiCode/Cline)

`stdout` съдържа **един валиден JSON обект и нищо друго**; човешките
съобщения (`✅ Екипът завърши...`) отиват на **stderr**. Същото се записва
в `<project>/.ai-brain/last_run.json`.

Реален изход (щастлив път, съкратен):

```json
{"tool":"sdld-engine","version":"0.2.0","command":"run","ok":true,
 "exit_code":0,"mode":"dry","state":"done","last_gate":"G4",
 "tasks":[{"id":"T1","title":"Създай src/vat.py","state":"passed","attempts":1}],
 "counts":{"total":1,"passed":1},
 "budget":{"limit_usd":5.0,"spent_usd":0.0},
 "journal_tail":[{"task":"T1","round":"1","status":"keep","gate_s":"0.20", ...}],
 "errors":[]}
```

| Поле | Значение |
|---|---|
| `ok` / `exit_code` | единственото, което трябва да четеш за вердикт |
| `state`, `last_gate` | къде спря цикълът (done / blocked / paused_budget / escalated) |
| `tasks`, `counts` | по-подробно: коя задача, колко опита |
| `budget.spent_usd` | реални разходи (в dry = 0.00) |
| `journal_tail` | последните 5 опита keep/discard/crash |
| `errors` | счупени файлове/аномалии; винаги е списък (празен = всичко чисто) |

При вътрешна грешка пак излиза JSON (`ok:false`, `errors:[...]`), не stack
trace. Тест: `tests/test_cli_json.py` (6 теста).

## 5. Какво МОЖЕ (доказано с изход)

- Целият цикъл G0→G4 в dry режим с **реални** unittest тестове като гейт.
- Щастлив път → `exit 0, state=done`; провал 3 пъти → `exit 1, blocked`;
  бюджет → `paused_budget` → `resume` → `done` (3-те E2E, `E2E_OK`).
- Пази инженера от пренаписване на `tests/`, `.ai-brain/`, `config/`,
  `program.md`; чиста среда за гейта (без ключове); бюджетен precheck
  преди всеки платен опит; атомарни записи; Pydantic схеми на всеки отговор.
- Журнал на опитите (`.ai-brain/journal.tsv`), kill-rule таймаут,
  критерий за простота (LOC растеж), `program.md` като постоянен контекст.

## 6. Какво НЕ може / липсва (честно)

- **Жив режимът не е пускан с реален ключ** — кодът е написан и четен, но
  няма живо доказателство. Dry = **локални отговори от примери**, не реален
  AI модел.
- **Няма MCP сървър** — закачането във VisiCode днес става само през
  терминал (път A, §7). Път B (подзадача) и C (MCP) не са правени.
- Няма SQLite store, git worktrees/паралелизъм, Tool Gateway, риск-политики,
  дашборд (по ARCHITECTURE.md — бъдещи версии).
- Съдията е механичен (структура + реални тестове), не жив LLM-експерт.
- Отделен продукт е **TeamBox** (Node.js екип агенти) — интеграция
  SDLD ↔ TeamBox не съществува (по изрично решение).

## 7. Закачане във VisiCode — път A (терминал, работи днес)

1. Отвори терминал в папката на `sdld-engine/`:
   ```powershell
   python -m engine.cli run "НАПРАВИ ..." --project C:\път\проект --dry-run --json
   ```
2. Парсни `stdout` като JSON и съди по `ok`/`exit` (или прочети
   `<project>/.ai-brain/last_run.json`).
3. За външен агент: инструкцията към VisiCode/Cline е
   *„Изпълни тази команда в терминала и парсни stdout като JSON; при
   `ok:false` покажи `state` и `journal_tail`."*

## 8. Къде са файловете

`hristovdimitri2-hub/sdld-engine` (GitHub) · `engine/cli.py` (--json) ·
`tests/test_cli_json.py` · този лист се обновява при всяка промяна по §3–§6.
