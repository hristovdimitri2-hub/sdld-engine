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
"""

__version__ = "0.2.0"

#: How many tests this suite collects, as a DATED MEASUREMENT and not an
#: aspiration — the same discipline Kristo Intelligence applies to its public
#: validation page. It lives here, in one place, so that the number this tool
#: reports is the number pytest actually collected.
#:
#: tests/test_suite_count.py asserts that equality. It deliberately does NOT
#: scrape the documents: README.md, SPEC.md and ARCHITECTURE.md state 51, 82 and
#: 88, and all three are CORRECT, because each sits inside a dated,
#: version-specific section. A scraper would flag two accurate historical
#: records as defects, and a guard that cries wolf is worse than no guard.
#:
#: Update this and SUITE_LAST_RUN together, after actually running the suite.
#: Do not count `def test_` by hand: parametrized tests make definitions and
#: collected items differ, which is precisely how a number goes stale.
SUITE_TESTS_PASSED = 91
SUITE_LAST_RUN = "2026-11-06"
