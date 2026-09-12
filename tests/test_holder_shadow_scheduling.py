"""A lane must be scheduled by the branch this deployment actually runs.

The holder-concentration shadow was registered, sampled and working, and then went silent for nine
days: it was created only in the legacy task list, which a chain-meme-only process returns before
reaching (`run_forever` returns inside the `if self.chain_meme_trader_only:` branch). Nothing
raised, no error case was written, and `holders` stayed NULL in every snapshot row while the
data-layer request asked for holder concentration.

These tests are structural on purpose: the defect is *placement*, so the guard has to assert
placement rather than behaviour.
"""
import inspect
import re

from memetrader.runtime import Runtime


RUN_BRANCH = re.compile(r'if self\.chain_meme_trader_only:\s*\n\s*tasks = \[')
BRANCH_END = 'await asyncio.gather(*tasks, return_exceptions=True)'


def _run_forever_source() -> str:
    return inspect.getsource(Runtime.run_forever)


def _chain_meme_branch() -> str:
    """The task list the chain-meme-only process actually starts (it returns at its end)."""
    source = _run_forever_source()
    start = RUN_BRANCH.search(source).start()
    return source[start:source.index(BRANCH_END, start)]


def _legacy_branch() -> str:
    """The task list a chain-meme-only process never reaches."""
    source = _run_forever_source()
    return source[source.index('tasks = [', source.index(BRANCH_END)):]


def test_holder_shadow_is_scheduled_in_the_branch_that_runs():
    branch = _chain_meme_branch()
    assert "name=\"solana_holder_shadow\"" in branch
    assert 'self.solana_holder_shadow_once' in branch


def test_each_task_list_schedules_the_lane_at_most_once():
    """Keeping it in the legacy list too is fine - only one list runs per process - but a
    copy-paste double schedule inside one list would double the RPC load silently."""
    assert _chain_meme_branch().count('name="solana_holder_shadow"') == 1
    assert _legacy_branch().count('name="solana_holder_shadow"') <= 1


def test_the_two_branches_are_actually_distinct_task_lists():
    """If this ever collapses, the placement assertions above would be vacuous."""
    run_branch, legacy = _chain_meme_branch(), _legacy_branch()
    assert re.search(r'name="chain_meme_pattern_observer"', run_branch)
    assert re.search(r'name="external_sources"', legacy)
    assert 'name="chain_meme_pattern_observer"' not in legacy
    assert 'name="external_sources"' not in run_branch


def test_holder_lane_keeps_its_registered_shadow_semantics():
    """Reviving the schedule must not turn research data into decision input."""
    from memetrader.store import Store

    assert Store.SOLANA_HOLDER_SHADOW_VERSION == 'solana-holder-breadth-shadow/v1'
    assert Store.SOLANA_HOLDER_SHADOW_SAMPLE_MODULUS == 1000
    assert Store.SOLANA_HOLDER_SHADOW_SAMPLE_BUCKETS == 2
    definition = Store._solana_holder_shadow_definition()
    assert definition['decision_eligible'] is False
    assert definition['affects'] == 'none'
    assert definition['active_strategy'] is False
    assert definition['append_only'] is True
    assert definition['no_historical_backfill'] is True
    assert definition['horizons_minutes'] == [0, 15, 60, 240]
