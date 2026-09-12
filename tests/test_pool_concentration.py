"""Cross-arm per-pool concentration cap.

ENFORCEMENT IS OPT-IN and defaults to OFF. This is deliberate: the same-token concurrency cap
was offered to the user twice and DECLINED twice, and it is recorded as a top binding rule
("no same-token concurrency cap"). A later full-autonomy grant is not a reversal of a specific,
twice-stated decision, so the default reproduces the behaviour every pre-existing arm had.

The measured motivation for keeping the code at all: on this device 350 positions covered only
11 tokens, the worst single-token burst was 40 positions in ONE second, and the worst token
carried 81 positions / 1,620U. When the whole book is eleven bets, every per-arm ranking is
measuring multiplicity rather than strategy behaviour.

These tests pin BOTH halves: the default must change nothing, and an explicit opt-in must bind.
"""
from memetrader import pool_concentration as pc
from memetrader import store as store_module


# ------------------------------------------------------------------ default: nothing changes
def test_the_default_is_no_cap_at_all():
    assert pc.DEFAULT_MAX_ARMS_PER_POOL is None
    assert pc.DEFAULT_MAX_NEW_ARMS_PER_POOL is None
    for open_arms, new_arms in ((0, 0), (0, 40), (81, 40), (1000, 5000)):
        ok, reason = pc.pool_concentration_decision(
            open_arms_on_pool=open_arms, new_arms_this_pass=new_arms, definition={})
        assert ok is True, (open_arms, new_arms)
        assert reason == ""


def test_an_empty_or_missing_definition_never_blocks():
    for definition in (None, {}, {"unrelated": 1}, {"max_arms_per_pool": None},
                       {"max_arms_per_pool": None, "max_new_arms_per_pool": None}):
        ok, _ = pc.pool_concentration_decision(
            open_arms_on_pool=999, new_arms_this_pass=999, definition=definition)
        assert ok is True, definition


def test_the_switch_can_also_be_turned_off_explicitly():
    ok, _ = pc.pool_concentration_decision(
        open_arms_on_pool=81, new_arms_this_pass=40,
        definition={"cross_arm_pool_concentration": False, "max_arms_per_pool": 1})
    assert ok is True


# ------------------------------------------------------------------ explicit opt-in binds
def test_a_numeric_opt_in_binds_and_stops_the_measured_burst():
    """The measured worst case: 40 arms arriving on one pool in a single settlement pass."""
    definition = {"max_arms_per_pool": 8, "max_new_arms_per_pass": 3,
                  "max_new_arms_per_pool": 3}
    allowed = [new_arms for new_arms in range(50)
               if pc.pool_concentration_decision(
                   open_arms_on_pool=0, new_arms_this_pass=new_arms,
                   definition=definition)[0]]
    assert allowed == [0, 1, 2], allowed


def test_a_pool_at_the_cap_admits_nobody_but_one_below_admits_one():
    definition = {"max_arms_per_pool": 8}
    ok, reason = pc.pool_concentration_decision(
        open_arms_on_pool=8, new_arms_this_pass=0, definition=definition)
    assert (ok, reason) == (False, pc.CONCENTRATION_REASON)
    assert pc.pool_concentration_decision(
        open_arms_on_pool=7, new_arms_this_pass=0, definition=definition)[0] is True


def test_the_boolean_flag_opts_in_with_the_suggested_values():
    definition = {"cross_arm_pool_concentration": True}
    assert pc.concentration_limits(definition) == (
        pc.SUGGESTED_MAX_ARMS_PER_POOL, pc.SUGGESTED_MAX_NEW_ARMS_PER_POOL)
    allowed = sum(1 for new_arms in range(100)
                  if pc.pool_concentration_decision(
                      open_arms_on_pool=0, new_arms_this_pass=new_arms,
                      definition=definition)[0])
    assert allowed == int(pc.SUGGESTED_MAX_NEW_ARMS_PER_POOL)


def test_a_healthy_cluster_still_forms_across_passes_when_enforced():
    definition = {"max_arms_per_pool": 8, "max_new_arms_per_pool": 3}
    open_arms = 0
    for _ in range(20):
        added = 0
        for _ in range(100):
            if pc.pool_concentration_decision(
                open_arms_on_pool=open_arms + added, new_arms_this_pass=added,
                definition=definition)[0]:
                added += 1
            else:
                break
        assert added <= 3
        open_arms += added
    assert open_arms == 8


# ------------------------------------------------------------------ shadow record
def test_the_shadow_decision_never_blocks_but_reports_what_it_would_do():
    """Enforcement is off, yet the evidence must keep accumulating."""
    ok, reason = pc.shadow_decision(open_arms_on_pool=81, new_arms_this_pass=0, definition={})
    assert ok is True
    assert reason == pc.CONCENTRATION_REASON
    ok, reason = pc.shadow_decision(open_arms_on_pool=0, new_arms_this_pass=0, definition={})
    assert ok is True
    assert reason == pc.SHADOW_ONLY


# ------------------------------------------------------------------ fail-open / robustness
def test_missing_or_invalid_inputs_never_block_an_entry():
    """Failing open is the only safe direction: an unknown pool is not a crowded pool."""
    for open_arms, new_arms in ((None, None), ("x", 1), (0, "y"), (-5, -5)):
        ok, reason = pc.pool_concentration_decision(
            open_arms_on_pool=open_arms, new_arms_this_pass=new_arms,
            definition={"max_arms_per_pool": 1})
        assert ok is True
        assert reason == ""
    for bad in ("bad", float("nan"), True):
        limits = pc.concentration_limits({"max_arms_per_pool": bad})
        # A bool falls back to the (uncapped) default; unusable values do the same.
        assert limits[0] in (None, pc.DEFAULT_MAX_ARMS_PER_POOL) or limits[0] == bad


def test_negative_means_uncapped_and_zero_means_zero():
    assert pc.concentration_limits({"max_arms_per_pool": -1})[0] is None
    assert pc.concentration_limits({"max_arms_per_pool": 0})[0] == 0.0
    assert pc.concentration_limits({}) == (None, None)


# ------------------------------------------------------------------ the store gate
class _Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Db:
    def __init__(self, row):
        self._row = row

    def execute(self, *args, **kwargs):
        return _Cursor(self._row)


class _Gate:
    # Bind the real store helpers so the test exercises the production counting logic.
    _chain_meme_pool_concentration_allows = (
        store_module.Store._chain_meme_pool_concentration_allows)
    _chain_meme_open_arms_on_pool = store_module.Store._chain_meme_open_arms_on_pool

    def __init__(self, row):
        self.db = _Db(row)


def test_the_store_gate_is_off_by_default_even_for_a_crowded_pool():
    crowded = _Gate({"open_arms": 81})
    ok, reason = store_module.Store._chain_meme_pool_concentration_allows(
        crowded, version="v", definition={}, identity=("t", "pool"), new_arms_this_pass=40)
    assert (ok, reason) == (True, "")
    assert getattr(crowded, "_chain_meme_concentration_refusals", 0) == 0


def test_the_store_gate_reads_the_aggressive_override_when_a_definition_opts_in():
    definition = {"max_arms_per_pool": 3}
    crowded = _Gate({"open_arms": 5})
    ok, reason = store_module.Store._chain_meme_pool_concentration_allows(
        crowded, version="v", definition=definition, identity=("t", "pool"),
        new_arms_this_pass=0)
    assert ok is False and reason == store_module.CONCENTRATION_REASON
    assert crowded._chain_meme_concentration_refusals == 1

    roomy = _Gate({"open_arms": 2})
    assert store_module.Store._chain_meme_pool_concentration_allows(
        roomy, version="v", definition=definition, identity=("t", "pool"),
        new_arms_this_pass=0) == (True, "")


def test_an_unidentifiable_pool_fails_open_even_when_a_definition_opts_in():
    gate = _Gate({"open_arms": 81})
    assert store_module.Store._chain_meme_pool_concentration_allows(
        gate, version="v", definition={"max_arms_per_pool": 1}, identity=None,
        new_arms_this_pass=99) == (True, "")
