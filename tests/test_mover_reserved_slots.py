"""Reserved mover-watch admission (user decision 2026-09-12: 8 of the 30 pattern-watch slots)."""
from memetrader import runtime as rt


class _Registry:
    def __init__(self, active):
        self._active = set(active)

    def active(self, now):
        return set(self._active)


def test_admits_a_flagged_token_when_the_reservation_is_not_full():
    watch = {'x1': {}, 'x2': {}}
    assert rt.mover_reserved_admit(watch, 'flagged', _Registry(['flagged'])) is True


def test_refuses_once_the_reservation_is_full():
    active = ['m%d' % i for i in range(rt.MOVER_RESERVED_SLOTS)]
    watch = {key: {} for key in active}
    # the watch already holds exactly MOVER_RESERVED_SLOTS flagged tokens
    assert rt.mover_reserved_admit(watch, 'late', _Registry(active + ['late'])) is False
    # one fewer and it admits again
    watch.pop(active[0])
    assert rt.mover_reserved_admit(watch, 'late', _Registry(active + ['late'])) is True


def test_only_counts_watch_keys_that_are_actually_flagged():
    active = ['m%d' % i for i in range(3)]
    watch = {key: {} for key in active} | {('u%d' % i): {} for i in range(20)}
    assert rt.mover_reserved_admit(watch, 'new', _Registry(active + ['new'])) is True


def test_never_admits_an_unflagged_token_or_without_a_registry():
    assert rt.mover_reserved_admit({}, 'plain', _Registry(['other'])) is False
    assert rt.mover_reserved_admit({}, 'plain', None) is False
    assert rt.mover_reserved_admit({}, '', _Registry([''])) is False


def test_registry_errors_never_admit_and_never_raise():
    class Broken:
        def active(self, now):
            raise RuntimeError('boom')

    assert rt.mover_reserved_admit({}, 'x', Broken()) is False


def test_the_reserved_share_is_a_quarter_of_the_pattern_watch():
    # the watch is 30 slots (3 chains x {early 3, growth 4, mature 3}); the approved share is 25%
    assert rt.MOVER_RESERVED_SLOTS == 8
    assert rt.MOVER_FRAME_TARGET == 30
