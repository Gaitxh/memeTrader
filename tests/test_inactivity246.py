from scripts.review_policy_lifecycle233 import inactivity

BASE=dict(arm_id='example',forward_started_at='2026-09-13T00:00:00Z')
AVAILABLE={'state':'ELIGIBLE_SUBJECT_TO_RUNTIME_CHECKS'}
END='2026-09-19T00:00:00Z'

def check(p=None,rows=None,at=END,parents=None,available=None):
    return inactivity(p or BASE,rows or [],as_of=at,
        by_policy=parents or {},availability=available or AVAILABLE)

def test_old_never_entered_flag_and_recent_no_entry_are_distinct():
    assert check()['state']=='NEVER_ENTERED_24H'
    assert check()['hours_without_entry']==144
    p={**BASE,'forward_started_at':'2026-09-18T23:00:00Z'}
    assert check(p)['state']=='NO_ENTRY_YET_UNDER_24H'

def test_paused_and_disabled_are_not_called_unexplained_zero_trades():
    assert check({**BASE,'entry_paused':True})['state']=='EXPECTED_PAUSE'
    assert check(available={'state':'FORWARD_DISABLED'})['review_required'] is False

def test_explicit_cutoff_future_epoch_and_unknown_clock():
    assert check(at=None)['state']=='CUTOFF_UNKNOWN'
    assert check({**BASE,'forward_started_at':'2026-09-20T00:00:00Z'})['state']=='NOT_ACTIVATED_AT_CUTOFF'
    assert check({**BASE,'forward_started_at':'2026-09-18'})['state']=='CLOCK_UNKNOWN'
