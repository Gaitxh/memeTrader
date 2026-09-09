"""Persistent ownership of one cohort opportunity, including security waits."""
import json

ANNOTATION_KEY='duplicate-opportunity-contamination/v1:'


def annotations(db,version):
    row=db.execute('SELECT value_json FROM kv WHERE key=?',(ANNOTATION_KEY+version,)).fetchone()
    return json.loads(row[0]).get('positions',{}) if row else {}


def annotation_id(arm,cohort_id):
    return arm+':'+str(cohort_id)


def owner(db, version, arm, decision_key, token_id):
    row=db.execute('SELECT cohort_id FROM chain_meme_cohort_enrollment_claims WHERE definition_version=? AND arm_id=? AND decision_key=?',
                   (version,arm,decision_key)).fetchone()
    if row:return int(row[0])
    # Older admitted intents (including security waits/rejects) predate claims.
    # Token/cohort and decision/cohort indexes bound this compatibility lookup.
    row=db.execute('SELECT c.id FROM chain_meme_trader_v6_cohorts c CROSS JOIN chain_meme_trader_entry_decisions d '
        'ON d.definition_version=c.definition_version AND d.shadow_cohort_id=c.id '
        'WHERE c.definition_version=? AND c.token_id=? AND d.arm_id=? AND d.status=\'admitted\' '
        'AND json_extract(c.feature_json,?)=? AND json_extract(c.feature_json,?) IS NOT NULL ORDER BY c.id LIMIT 1',
        (version,token_id,arm,'$.event_keys."'+arm+'"',decision_key,'$.cohort_signals."'+arm+'"')).fetchone()
    return int(row[0]) if row else None


def claim_decisions(db, version, cohort_id, token_id, at):
    """Called in the projection transaction BEFORE safety; resume keeps owner."""
    row=db.execute('SELECT feature_json FROM chain_meme_trader_v6_cohorts WHERE definition_version=? AND id=?',
                   (version,cohort_id)).fetchone()
    features=json.loads(row[0]) if row else {}
    decisions=db.execute("SELECT * FROM chain_meme_trader_entry_decisions WHERE definition_version=? AND shadow_cohort_id=? AND status='admitted' ORDER BY arm_id",
                         (version,cohort_id)).fetchall()
    allowed=[]
    for d in decisions:
        arm=d['arm_id'];key=features.get('event_keys',{}).get(arm)
        if key and arm in features.get('cohort_signals',{}):
            prior=owner(db,version,arm,str(key),token_id)
            db.execute('INSERT OR IGNORE INTO chain_meme_cohort_enrollment_claims(definition_version,arm_id,decision_key,cohort_id,recorded_at) VALUES(?,?,?,?,?)',
                       (version,arm,str(key),prior if prior is not None else cohort_id,at))
            claimed=db.execute('SELECT cohort_id,terminal_reason FROM chain_meme_cohort_enrollment_claims WHERE definition_version=? AND arm_id=? AND decision_key=?',
                               (version,arm,str(key))).fetchone()
            if int(claimed[0])!=cohort_id or claimed[1]:continue
        if not db.execute('SELECT 1 FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?',
                          (version,arm,cohort_id)).fetchone():allowed.append(d)
    return allowed
