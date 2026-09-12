"""Cross-arm per-pool concentration cap.

Measured 2026-09-12 over one fresh Paper epoch (87 minutes): 350 positions across only 11
tokens, worst single-token burst 40 positions opened in ONE second, worst token carried 81
positions / 1,620U. Four BSC pools whose `liquidity_control` was `unknown` produced 169 of
those positions and the whole -3,380U written-off loss.

These tests pin the separation: a definition that does not opt out keeps a bounded number of
arms per pool, and an explicit null reproduces the previous uncapped behaviour exactly.
"""
from memetrader import pool_concentration as pc


def test_the_measured_worst_case_is_refused():
    """40 arms arriving on one pool in a single pass must not all open."""
    allowed = 0
    for new_arms in range(100):
        ok, reason = pc.pool_concentration_decision(
            open_arms_on_pool=0, new_arms_this_pass=new_arms, definition={})
        if ok:
            allowed += 1
        else:
            assert reason == pc.CONCENTRATION_REASON
    assert allowed == int(pc.DEFAULT_MAX_NEW_ARMS_PER_POOL)


def test_a_pool_already_holding_the_cap_admits_nobody():
    ok, reason = pc.pool_concentration_decision(
        open_arms_on_pool=int(pc.DEFAULT_MAX_ARMS_PER_POOL), new_arms_this_pass=0,
        definition={})
    assert ok is False
    assert reason == pc.CONCENTRATION_REASON
    # one below the cap still admits exactly one more arm
    ok, _ = pc.pool_concentration_decision(
        open_arms_on_pool=int(pc.DEFAULT_MAX_ARMS_PER_POOL) - 1, new_arms_this_pass=0,
        definition={})
    assert ok is True


def test_a_healthy_cluster_still_forms_across_passes():
    """A 6-arm consensus is reachable: it just spreads over successive settlement passes.

    The measured healthy alpha149 cluster on one pool was 6 arms. The per-pass cap bounds a
    single frame's fan-out (worst measured: 40 arms in one second); it must not make the
    cluster itself unreachable.
    """
    open_arms = 0
    passes = 0
    while open_arms < 6 and passes < 20:
        added = 0
        for new_arms in range(100):
            if pc.pool_concentration_decision(
                open_arms_on_pool=open_arms + added, new_arms_this_pass=added,
                definition={},
            )[0]:
                added += 1
            else:
                break
        assert added <= int(pc.DEFAULT_MAX_NEW_ARMS_PER_POOL)
        open_arms += added
        passes += 1
    assert open_arms >= 6, (open_arms, passes)


def test_the_total_cap_is_reached_and_then_holds():
    open_arms = 0
    for _ in range(50):
        if pc.pool_concentration_decision(
            open_arms_on_pool=open_arms, new_arms_this_pass=0, definition={})[0]:
            open_arms += 1
        else:
            break
    assert open_arms == int(pc.DEFAULT_MAX_ARMS_PER_POOL)


def test_an_explicit_null_reproduces_the_previous_uncapped_behaviour():
    definition = {"max_arms_per_pool": None}
    for new_arms in (0, 50, 5000):
        ok, reason = pc.pool_concentration_decision(
            open_arms_on_pool=1000, new_arms_this_pass=new_arms, definition=definition)
        assert ok is True
        assert reason == ""


def test_the_switch_can_be_turned_off_by_field_or_flag():
    for definition in ({"cross_arm_pool_concentration": False},
                       {"max_arms_per_pool": None, "max_new_arms_per_pool": None}):
        ok, _ = pc.pool_concentration_decision(
            open_arms_on_pool=999, new_arms_this_pass=999, definition=definition)
        assert ok is True


def test_a_definition_can_raise_or_lower_its_own_cap():
    strict = {"max_arms_per_pool": 2, "max_new_arms_per_pool": 1}
    assert pc.pool_concentration_decision(
        open_arms_on_pool=2, new_arms_this_pass=0, definition=strict)[0] is False
    assert pc.pool_concentration_decision(
        open_arms_on_pool=0, new_arms_this_pass=1, definition=strict)[0] is False
    assert pc.pool_concentration_decision(
        open_arms_on_pool=0, new_arms_this_pass=0, definition=strict)[0] is True

    loose = {"max_arms_per_pool": 40, "max_new_arms_per_pool": 40}
    for new_arms in range(39):
        assert pc.pool_concentration_decision(
            open_arms_on_pool=0, new_arms_this_pass=new_arms, definition=loose)[0] is True


def test_missing_or_invalid_inputs_never_block_an_entry():
    """Failing open is the only safe direction: an unknown pool is not a crowded pool."""
    for open_arms, new_arms in ((None, None), ("x", 1), (0, "y"), (-5, -5)):
        ok, reason = pc.pool_concentration_decision(
            open_arms_on_pool=open_arms, new_arms_this_pass=new_arms, definition={})
        assert ok is True
        assert reason == ""
    for definition in (None, {}, {"max_arms_per_pool": "bad"},
                       {"max_arms_per_pool": float("nan")}):
        ok, _ = pc.pool_concentration_decision(
            open_arms_on_pool=0, new_arms_this_pass=0, definition=definition)
        assert ok is True


def test_zero_means_zero_and_negative_means_uncapped():
    assert pc.concentration_limits({"max_arms_per_pool": 0})[0] == 0.0
    assert pc.concentration_limits({"max_arms_per_pool": -1})[0] is None
    assert pc.concentration_limits({}) == (
        pc.DEFAULT_MAX_ARMS_PER_POOL, pc.DEFAULT_MAX_NEW_ARMS_PER_POOL)


def test_the_store_gate_fails_open_when_the_pool_cannot_be_identified():
    """A cohort without a pool address must never be refused by this gate."""

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

    class Fake:
        def __init__(self, row):
            self.db = _Db(row)

    from memetrader import store as store_module

    fake = Fake(None)
    assert store_module.Store._chain_meme_pool_concentration_allows(
        fake, version="v", definition={}, identity=None, new_arms_this_pass=0,
    ) == (True, "")

    class FakeMissing(Fake):
        def _chain_meme_entry_pool_identity(self, *args, **kwargs):
            return None

    assert store_module.Store._chain_meme_pool_concentration_allows(
        FakeMissing(None), version="v", definition={}, identity=None,
        new_arms_this_pass=99,
    ) == (True, "")


def test_the_store_gate_counts_open_arms_and_records_the_refusal():
    from memetrader import store as store_module

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

    class Fake:
        # Bind the real store helpers so the test exercises the production counting logic
        # rather than a re-implementation of it.
        _chain_meme_pool_concentration_allows = (
            store_module.Store._chain_meme_pool_concentration_allows)
        _chain_meme_open_arms_on_pool = store_module.Store._chain_meme_open_arms_on_pool

        def __init__(self, row):
            self.db = _Db(row)

    crowded = Fake({"open_arms": 5})
    ok, reason = store_module.Store._chain_meme_pool_concentration_allows(
        crowded, version="v", definition={"max_arms_per_pool": 3},
        identity=("t", "pool"), new_arms_this_pass=0)
    assert ok is False and reason == store_module.CONCENTRATION_REASON
    assert crowded._chain_meme_concentration_refusals == 1

    roomy = Fake({"open_arms": 2})
    ok, _ = store_module.Store._chain_meme_pool_concentration_allows(
        roomy, version="v", definition={"max_arms_per_pool": 3},
        identity=("t", "pool"), new_arms_this_pass=0)
    assert ok is True
    assert getattr(roomy, "_chain_meme_concentration_refusals", 0) == 0

    allowed = Fake({"open_arms": 5000})
    assert store_module.Store._chain_meme_pool_concentration_allows(
        allowed, version="v", definition={"max_arms_per_pool": None},
        identity=("t", "pool"), new_arms_this_pass=99) == (True, "")
    assert getattr(allowed, "_chain_meme_concentration_refusals", 0) == 0
