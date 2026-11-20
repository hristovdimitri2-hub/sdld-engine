"""Автономен инженерен двигател (SDLD Engine) — сглобка v0.2.0.

Спецификация: ARCHITECTURE.md
Философия: dry-run преди жив режим, gate винаги е реален тест, $0 в dry.

v0.1.1 = v0.1.0 + външен одит (01.11.2026): 6/6 дефекта поправени,
 всеки с възпроизвеждащ (червен → зелен) тест; + още 1 бъг, хванат от
 новите тестове (__pycache__ лъжлива „мутация“ на гейта).

v0.2.0 = адаптации от karpathy/autoresearch (05.11.2026): журнал на
 опитите (keep|discard|crash), kill-rule (gate.timeout_s), критерий за
 простота (растеж на редовете между опитите), program.md програма на
 екипа (човекът я редактира, агентът я чете и не я пипа).

Review-фаза (07.11.2026): преди всеки инженерски опит — последните
 редове от journal.tsv + git log -10 като контекст преди задачата
 (engine/review.py); три-валентен гейт (ok=None = „не е проверено“,
 никога pass) и SUITE_TESTS_PASSED като измерение — идват от
 паралелните комити 06.11.

Памет с индекс (12.11.2026, модел LLM Wiki / Karpathy gist 442a6bf):
 .ai-brain/index.md — автоматичен каталог (файл → какво е → обновен +
 броеве от данните); feed.md редове с категорийен таг
 „<ts> | <tag> | <текст>“ (grep по събитие); таг без валидация = грешка.
"""

__version__ = "0.2.0"

#: How many tests this suite collects, as a DATED MEASUREMENT and not an
#: aspiration — the same discipline Kristo Intelligence applies to its public
#: validation page. It lives here, in one place, so that the number this tool
#: reports is the number pytest actually collected.
#:
#: tests/test_suite_count.py asserts that equality. It deliberately does NOT
#: scrape the documents: README.md, SPEC.md and ARCHITECTURE.md carry dated,
#: version-specific numbers (51, 82, 88 ...) as historical records. A scraper
#: would flag accurate history as defects, and a guard that cries wolf is
#: worse than no guard.
#:
#: Update this and SUITE_LAST_RUN together, after actually running the suite.
#: Do not count `def test_` by hand: parametrized tests make definitions and
#: collected items differ, which is precisely how a number goes stale.
SUITE_TESTS_PASSED = 106
SUITE_LAST_RUN = "2026-11-12"
