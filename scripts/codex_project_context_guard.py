from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(r"E:\memeTrader")
PROJECT_MIRROR = Path(
    r"C:\Users\51465\.codex\.chatgpt-projects\g-p-6a6ae7ab5ba88191a99ff26a42f446e8"
)
LEAD_STATE = PROJECT / "docs" / "PROJECT_CONTEXT" / "CHATGPT_LEAD_STATE.json"
SYNC_STATE = PROJECT / "docs" / "PROJECT_CONTEXT" / "CHATGPT_CODEX_SYNC_STATE.json"


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _context() -> str:
    lead = _load_json(LEAD_STATE)
    sync = _load_json(SYNC_STATE)
    north = lead.get("north_star") or {}
    active = sync.get("active_cycle") or lead.get("current_cycle_hint") or {}
    open_groups = sync.get("open_groups") or []
    pending_artifact = ""
    if sync.get("attention_required") and open_groups:
        pending_artifact = str((open_groups[0] or {}).get("artifact") or "").strip()
    return "\n".join(
        [
            "[GXH PROJECT GUARD — durable constraint context, NOT a new user task]",
            f"North star: {north.get('business_goal', 'Improve genuine forward, executable, cost-adjusted, risk-adjusted meme-token profitability.')}",
            f"Active cycle: {active.get('priority', 'P0')} / {active.get('cycle_id', 'read current sync pointer')} / {active.get('status', 'read current sync pointer')}.",
            f"Cycle objective: {active.get('objective', 'Read E:/memeTrader/docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json before changing scope.')}",
            "Before changing scope ask: Which currently observed end-to-end profitability bottleneck will this action change? If unclear, preserve the idea and do not displace the active cycle.",
            "Execution: avoid unnecessary defensive/review/audit/test loops; use the narrowest sufficient validation; after two similar correction cycles, reconsider the causal hypothesis.",
            "Tooling: for generic implementation/tool blockers, check official docs + mature open source/upstream issues before building a custom subsystem.",
            "Agent cost: deterministic/local work first; use the cheapest capable development agent for routine tasks; escalate hard causal/architecture/trading/experiment questions to the designated Lead ChatGPT; multi-review only at material gates.",
            "Safety: no future-data/backfilled winners, no Strategy/Paper gate relaxation for sample count, Live locked, one active checkout writer, no secrets, project durable state on E:.",
            *([f"Pending Lead/Codex coordination alert: read E:/memeTrader/{pending_artifact.replace(chr(92), '/')} at the next stable checkpoint; ACK only materially new constraints and do not displace the active cycle merely to service coordination."] if pending_artifact else []),
            "Authority pointers: E:/memeTrader/AGENTS.md; E:/memeTrader/docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md; E:/memeTrader/docs/PROJECT_CONTEXT/REQUIREMENT_LEDGER.md; E:/memeTrader/docs/PROJECT_CONTEXT/CHATGPT_LEAD_STATE.json; E:/memeTrader/docs/PROJECT_CONTEXT/CHATGPT_RECOVERED_USER_REQUIREMENTS_2026-09-02.md; E:/memeTrader/docs/PROJECT_CONTEXT/CHATGPT_CURRENT_CONVERSATION_REQUIREMENTS_2026-09-02.md; E:/memeTrader/docs/PROJECT_CONTEXT/COMMON_SPACE/README.md.",
            "Treat the user's prompt as the task. This guard constrains how you execute it; it does not replace or broaden the prompt.",
        ]
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    cwd_raw = str(payload.get("cwd") or "")
    event = str(payload.get("hook_event_name") or "")
    source = str(payload.get("source") or "")
    try:
        cwd = Path(cwd_raw)
    except Exception:
        cwd = Path()

    applies = bool(cwd_raw) and (_under(cwd, PROJECT) or _under(cwd, PROJECT_MIRROR))
    output: dict = {"continue": True, "suppressOutput": True}
    if not applies:
        print(json.dumps(output, ensure_ascii=False))
        return 0

    should_inject = event == "UserPromptSubmit" or (
        event == "SessionStart" and source in {"resume", "compact"}
    )
    if should_inject:
        output["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": _context(),
        }

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
