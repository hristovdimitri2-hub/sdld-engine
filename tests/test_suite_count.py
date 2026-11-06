"""The suite count is a measurement taken in one place, not a number typed twice.

This is the one part of the "stale number" defence that can be stated without
guessing, and it is deliberately the whole of it.

**Why this file is small — read this before extending it.** It was first written
to scrape every test count out of README.md, SPEC.md and ARCHITECTURE.md and
compare them all against the suite. That plan rested on a finding that turned out
to be false. The documents state 51, 82 and 88 — and all three are CORRECT,
because each sits inside a dated, version-specific section:

  * ``51 passed`` under "одит → поправки (v0.1.1, 01.11.2026)"  — true then
  * ``82 passed`` under "Ново в v0.2.0 (05.11.2026)"            — true then
  * ``88``        in the quick start, the structure tree, SPEC — true now

A scraper would have flagged two historically accurate records as defects, and a
guard that cries wolf is worse than no guard: people learn to ignore it. So the
scraper was removed rather than tuned. **A dated historical count is not a stale
count**, exactly as a dated audit report keeps the number it was written with.

What remains is the invariant that cannot be argued with: the number published
by the code must be the number pytest actually collected. Counting `def test_`
in the files is NOT a valid way to find it — parametrized tests make definitions
and collected items differ (80 definitions collect as 91 items today), which is
precisely how a hand-maintained number goes wrong.
"""

import datetime

import pytest

from engine import SUITE_LAST_RUN, SUITE_TESTS_PASSED


def test_the_published_count_is_what_pytest_actually_collected(request):
    """The one source of truth must equal the real measurement."""
    collected = request.session.testscollected
    assert SUITE_TESTS_PASSED == collected, (
        f"engine.SUITE_TESTS_PASSED says {SUITE_TESTS_PASSED} but pytest "
        f"collected {collected}. This value is a measurement, not an "
        f"aspiration: run the suite, then update it and SUITE_LAST_RUN "
        f"together."
    )


def test_the_measurement_is_dated():
    """An undated count cannot be judged stale or current; a dated one can."""
    try:
        datetime.date.fromisoformat(SUITE_LAST_RUN)
    except ValueError:
        pytest.fail(
            f"engine.SUITE_LAST_RUN is {SUITE_LAST_RUN!r}, which is not an ISO "
            f"date. Say when the measurement was taken."
        )


def test_the_count_is_reachable_by_a_machine_not_only_by_a_reader():
    """CI can only compare what the tool reports.

    The point of putting the number in code is that something other than a human
    can check it. This asserts the value is a plain int on the package, which is
    what a CI step, a badge or `--json` would read.
    """
    assert isinstance(SUITE_TESTS_PASSED, int) and SUITE_TESTS_PASSED > 0
    assert not isinstance(SUITE_TESTS_PASSED, bool)
