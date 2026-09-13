import sqlite3

from scripts.projection_review161 import projection_diagnostics


def database(receipts=True):
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript('''
      CREATE TABLE chain_meme_trader_v6_cohorts (id,definition_version,token_id,pair_address,decided_at,entry_family);
      CREATE TABLE chain_meme_trader_entry_decisions (definition_version,shadow_cohort_id,arm_id,status,decided_at);
      CREATE TABLE chain_meme_trader_positions (definition_version,shadow_cohort_id,arm_id,opened_at,token_id);
      CREATE TABLE chain_meme_trader_entry_participant_outcomes (definition_version,shadow_cohort_id,arm_id,outcome,recorded_at);
    ''')
    if receipts:
        c.execute('CREATE TABLE chain_meme_trader_entry_gate_refusals '
                  '(definition_version,shadow_cohort_id,arm_id,gate,reason,attempted_at,recorded_at)')
    c.execute("INSERT INTO chain_meme_trader_v6_cohorts VALUES(1,'v','solana:T','CasePool','2026-09-14T00:00:00Z','test')")
    for arm in ('a', 'b', 'c', 'd', 'e'):
        c.execute("INSERT INTO chain_meme_trader_entry_decisions VALUES('v',1,?,'admitted','2026-09-14T00:00:01Z')", (arm,))
    c.execute("INSERT INTO chain_meme_trader_positions VALUES('v',1,'a','2026-09-14T00:00:02Z','solana:T')")
    c.execute("INSERT INTO chain_meme_trader_entry_participant_outcomes VALUES('v',1,'b','skipped_cash_unavailable_at_fill','2026-09-14T00:00:02Z')")
    if receipts:
        for arm, stamp in [('c', '2026-09-14T00:00:02Z'), ('e', '2026-09-14T00:02:00Z')]:
            c.execute("INSERT INTO chain_meme_trader_entry_gate_refusals VALUES('v',1,?,'pool_concentration','cap',?,?)", (arm, stamp, stamp))
    c.commit()
    c.execute('PRAGMA query_only=ON')
    return c


def test_fanout_partition_causal_and_no_inferred_rejections():
    with database() as c:
        result = projection_diagnostics(c, '2026-09-14T00:01:00Z', 2)
        counts = result['counts']
        assert result['distinct_tokens'] == 1 and counts['cohorts'] == 1
        assert counts['admitted_arms'] == 5 and counts['booked_admitted_arms'] == 1
        assert counts['cash_refused_admitted_arms'] == counts['concentration_refused_admitted_arms'] == 1
        assert counts['unresolved_admitted_arms'] == 2  # future receipt is not known yet
        assert result['gate_reasons'][0]['arm_attempts'] == 1


def test_old_schema_missing_receipt_is_unknown_not_zero_rejection():
    with database(False) as c:
        result = projection_diagnostics(c, '2026-09-14T00:01:00Z', 2)
        assert result['gate_receipt_schema_available'] is False
        assert result['counts']['unresolved_admitted_arms'] == 3


def test_later_booking_takes_precedence_without_deleting_receipt():
    with database() as c:
        c.execute('PRAGMA query_only=OFF')
        c.execute("INSERT INTO chain_meme_trader_positions VALUES('v',1,'c','2026-09-14T00:00:03Z','solana:T')")
        c.execute("INSERT INTO chain_meme_trader_v6_cohorts VALUES(2,'v','solana:Z','casepool','2026-09-14T00:00:05+00:00','test')")
        result = projection_diagnostics(c, '2026-09-14T00:01:00Z', 2)
        assert result['counts']['booked_admitted_arms'] == 2
        assert result['counts']['concentration_refused_admitted_arms'] == 0
        assert result['counts']['observed_concentration_refusals'] == 1
        assert result['distinct_chain_pools'] == 2  # case-sensitive Solana addresses
        assert projection_diagnostics(c, '2026-09-14T00:01:00Z', 2, limit=1)['truncated'] is True
