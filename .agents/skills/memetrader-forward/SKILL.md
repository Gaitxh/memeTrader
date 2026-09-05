---
name: memetrader-forward
description: Fix and extend E:/memeTrader runtime, accounting, strategy experiments and local Web UI while preserving strict forward history and backend latency. Use for this repository's operating work, not generic investment advice.
---

# memeTrader operating workflow

Read the repository AGENTS.md and current objective's leading state section. Resolve the active period, database and deployed process before claiming runtime facts. Do not reload all historical chat or repeat completed audits.

## Choose the relevant path

- **Accounting/data defect:** Follow one concrete record from source through identity, timestamp, quantity, costs, position, fill and account/API. Check chain + token + pool, synthetic versus real token units, remaining cost after partial fills, and whether cash/PNL use the same ledger frontier. Fix the common input/ledger path, not only the displayed number. Preserve invalid records and use existing correction/contamination mechanisms; do not invent a historical fill with today's price.
- **Latency defect:** Use existing timing telemetry, data age and bounded query plans. Separate request queue, upstream response, write, evaluation and publication delay. Keep held-token and pending-exit work ahead of discovery, research and UI. Reuse batching, deduplication and indexes; do not fake faster observations by replaying cache or create a new monitoring stack.
- **Web change:** Reuse chain_web.py and chain_web_static. Show real account equity (cash plus remaining marked value), realized/unrealized PNL, provenance time and unavailable values honestly. Full-period curves may be display-downsampled, never tail-truncated; drawdown is calculated from full eligible history, not drawing points. Avoid full historical scans on each browser poll.
- **New strategy:** A testable hypothesis is sufficient for a bounded new Paper experiment; proven profitability is not a prerequisite. Require usable as-of features, an economically meaningful behavior difference and explicit costs/risks. Separate design evidence from natural forward performance. Add a new ID via the existing append API and true deployment frontier; preserve parent contracts and all old positions. Engineering fixes are not new strategies. No parameter spray, hindsight entry or automatic promotion to Live.

## Execution and handoff

Use independent subagents for useful bounded investigations, with one owner per edited file and one runtime writer. Do not wait for a reviewer to perform unrelated authorized work. ChatGPT discussion follows CHATGPT_CONTACT.md; existing native/MCP tools take priority over installing duplicates.

Paper currently has independent 1000 USDC accounts and ordinary 20 USDC entries subject to available cash and strategy risk rules. The authorized reset has been consumed. Existing open positions continue exiting in their own period; restarting or adding a strategy must not initialize old accounts. Live remains locked and must use actual balances/fees if explicitly enabled later.

Run the narrow regression check that exercises the change, then confirm affected runtime/API progress at deployment. Report implemented, tested, deployed and naturally observed as separate facts. Record problem, cause, change, rationale and validation in the existing system update history. Commit/push the completed stage as authorized, excluding ignored runtime data and secrets. Stop rechecking a passed component and move to remaining requested work.
