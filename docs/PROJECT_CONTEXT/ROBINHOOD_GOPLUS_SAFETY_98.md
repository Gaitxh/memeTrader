# Robinhood GoPlus common Paper safety — 98

REPLY_TO: C2C-20260909-ROBINHOOD-GOPLUS-SAFETY-98

Implemented/pushed/deployed code 4b6ae31, 2026-09-09 ~12:01:21Z. Existing enrichment and bounded preentry worker now support chain 4663. No new scheduler/source credentials, TTL or request budget; Honeypot.is stays BSC-only. Canonical pool/token/protocol checks remain mandatory. Canonical identity alone no longer supplies a Robinhood security usable fact. Missing/empty/irrelevant reports wait UNKNOWN; explicit known safe risk/tax facts permit UNKNOWN authorization under existing91 minimal-evidence semantics, not a safety guarantee. Explicit dangerous flags or tax above existing limit reject. Closed-source alone is audited as soft_hazard=closed_source_unverified and UNKNOWN, not a hard veto; it also cannot authorize an otherwise empty report. Existing non-Paper execution-contract unsupported-chain restriction is unchanged.

Official evidence: [GoPlus changelog](https://docs.gopluslabs.io/changelog/token-security-api) V1.5.6 lists 4663; [mainstream tokens](https://docs.gopluslabs.io/reference/supported-main-token) lists Robinhood; [response semantics](https://docs.gopluslabs.io/reference/response-details) distinguishes closed source and unavailable fields.

Validation: tests/test_preentry_safety.py 32 passed, git diff --check passed. Tests cover partial usable report, dangerous flag, empty/irrelevant report, closed-source soft audit, extreme tax, identity mismatch, and exact existing /token_security/4663 request/60s cache without Honeypot request.

Runtime snapshot pre98 12:00:59Z -> post98 12:01:51Z: health running; Paper=true/Live locked. Seven-table funding/registration/activation digest unchanged: 5abffced88f8b8e3228071a123dd8bb79f9d0effca00b1e9a85a5d17194c71a3. Held fetch p95 2.266->1.813s; apply .1044->.0803s; pattern 6.622->3.027s. This is startup-only smoke, not comparable sustained performance proof. Passive drops0. Natural post-start safety rows0 at this cutoff; Robinhood natural acceptance INSUFFICIENT_NATURAL_EVIDENCE, no fabricated test BUY. Current6 open positions/2held continue ordinary exits. No registration/funding/history/reset changes.

Evidence: data/research/admission88/{pre98,post98,natural98}.json. Separate existing admission Shadow generation had900 dropped audit records pre-restart; its new process generation0 so far does not repair prior discontinuity or prove sustained sink acceptance. No live-watch changes were made here.
