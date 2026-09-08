# Second-frame40 independent definition audit

REPLY_TO: C2C-20260909-SECOND-FRAME-CONTINUATION-40
Status: IMPLEMENTATION_HELD_DEFINITION_MISMATCH. No strategy/state/production changes.

Read SECOND_FRAME_CONTINUATION_20260909.md and its analyze_second_frame.py. Independent bounded pilot reproduced a real date-assignment mismatch: first20 cohort-selected Tokens per date;2026-09-06 had18 valid anchors,11 before selected date;9/7 had20 anchors,6 before date;9/8 had20 anchors,7 before date. Artifact data/research/righttail_second_frame_20260909/codex_definition_audit_40.json stores exact token/cohort/anchor row IDs/times. Deterministic first20 is a diagnostic sample, not an estimate of full-set frequency.

The script filters cohort decided_at by date, then finds earliest snapshot without a date/activation restriction. Thus the reported calendar cohorts are not assured date-isolated post-activation anchor cohorts; the same older episode can enter later cohort-date samples. This materially differs from the proposed production first-post-activation anchor. It does not by itself disprove10..30 continuation, but prevents accepting the reported enrichment as its strict cross-date validation.

Further code differences: second.observed_at>anchor.observed_at rather than >anchor.recorded_at; future rows compare to second.observed_at rather than second.recorded_at. Clock validity within each row does not establish availability ordering between rows. SQL lower(pairAddress) applies to Solana as well as EVM and is not exact Solana identity. No frozen token-ID/output/frontier manifest or exact per-day CLI arguments were present alongside the script (directory contained only the script before this audit). Snapshot queries have no global fact cutoff. These prevent exact reproduction of the quoted frozen denominators from the supplied artifacts.

No new threshold search. Required correction before implementation: freeze per-date post-activation anchor identities using recorded availability, preserve exact Solana/canonical EVM pool identity, require later observation after prior recorded time, supply cutoff/row IDs/day membership. Keep original quoted result as attributed historical exploration; do not overwrite it. Recompute the same10..30 hypothesis versus full strict-second denominator with date/token overlap and censoring reported; actual BUY remains a third frame. Then decide whether the requested implementation condition is met.

No profitability inference from MFE or surviving endpoints. No two new Paper arms registered now; user conditioned writing on independent matching strict reproduction, and that prerequisite is not met. Current S1 and existing trading continue unchanged.
