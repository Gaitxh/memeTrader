# Paired orphan cleanup63

REPLY_TO: C2C-20260909-PAIRED-ORPHAN-CLEANUP-63
Result: APPLIED_NEW_ENTRY_ONLY

Current effective definition was loaded with Store's static read-only connection helper, including registered policy additions and both convergence/retirement controls. All paired groups were inspected. Exactly one mixed group: resource_profit_structure_v1, declared size2, isolated_pattern_observer. Candidate already paused; control remained unpaused. Control36 terminals/36 tokens, realized -23.344125100392812U. No new strategy or contract change.

Semantics: store.py26900 excludes paused arms from isolated active policies. At27349–27358 the remaining members must equal paired_entry_size and all be admitted; singleton cannot enroll. Previous pending signal is still evaluated through that gate, not independent permission. Primary queued decisions additionally exclude paused arms at28159 and call group eligibility guard; exits remain on existing position paths. This is a required pair, not a control permitted to enroll independently.

Applied existing convergence KV only at2026-09-09T04:32:07.553998+00:00: resource_profit_structure_control_v1 PAUSED_NEW_ENTRY. No other mixed groups found and no other arm changed. Existing candidate pause retained. No restart/reset/backfill/Live. Same-transaction hashes of funding/capital/registrations/activations/additions and selected positions/trades unchanged: 0b213590705f9b1d491726b4db000726e9c2430e7955f48df3e066330fc5afd8.

Acceptance04:32:31.828960Z:248 subsequent system evaluations,0 selected-arm outcomes,0 new positions. Short natural window only. No production-code test required: code unchanged; preview, transaction assertions and post-control actual evaluation check passed. Utility fails closed if a newly detected mixed group/lane requires fresh semantics review.

Artifacts: data/research/convergence63/preview.json,applied.json,postcheck.json. Utility scripts/apply_convergence63.py. Earlier retirement left this member unpaused; paired admission prevented BUY but active filtering still spent signal evaluation. This closes that orphan without loosening the pair contract.
