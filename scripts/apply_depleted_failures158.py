"""Preview/apply Paper-loss depletion entry pauses without changing history.

The default is a read-only, all-effective-arm preview.  ``--apply`` is an
operator action: it rechecks the same bounded aggregates in one short write
transaction, then may update only ``kv`` (the convergence control and a
unique operation receipt).  It never constructs ``Store``.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from memetrader.store import Store  # noqa: E402  (classmethod only)


LIMIT_USD = 20.0
CONTROL_PREFIX = "chain-meme-account-convergence/v1:"
RECEIPT_PREFIX = "chain-meme-depleted-failures158/receipt/v1:"
BLOCKING_TABLES = (
    "chain_meme_trader_capital_credits",
    "chain_meme_trader_position_voids",
    "chain_meme_trader_accounting_contaminations",
    "chain_meme_trader_accounting_contamination_resolutions",
    "chain_meme_trader_market_fill_corrections",
    "chain_meme_trader_paper_funding_activations",
    "chain_meme_trader_fixed_funding_restorations",
)
WRITE_DEADLINE_SECONDS = 3.0


def utcstamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_object(value: Any) -> dict[str, Any]:
    try:
        result = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}


def tables(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}


def active_version(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT definition_version FROM chain_meme_trader_v6_activations "
        "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise RuntimeError("no current entry-enabled Paper strategy version")
    return str(row[0])


def require_clean_replay(connection: sqlite3.Connection, version: str) -> None:
    present = tables(connection)
    missing = [name for name in BLOCKING_TABLES if name not in present]
    if missing:
        raise RuntimeError("manual effective replay required; missing guard tables: " + ", ".join(missing))
    dirty = []
    for name in BLOCKING_TABLES:
        count = int(connection.execute(
            f"SELECT COUNT(*) FROM {name} WHERE definition_version=?", (version,)
        ).fetchone()[0])
        if count:
            dirty.append(f"{name}={count}")
    if dirty:
        raise RuntimeError("manual effective replay required; current version has " + ", ".join(dirty))
    fee_rows = connection.execute(
        "SELECT value_json FROM kv WHERE key LIKE 'chain-paper-execution:activation:%'"
    ).fetchall()
    if len(fee_rows) != 1:
        raise RuntimeError("manual effective replay required; execution fee activation is ambiguous")
    fields = json_object(fee_rows[0][0]).get("definition_fields", {})
    fee = _finite(fields.get("additional_fee_usd_each_fill") if isinstance(fields, dict) else None)
    if fee is None or fee != 0.0:
        raise RuntimeError("manual effective replay required; execution fee activation changes cash accounting")


def effective_policies(connection: sqlite3.Connection, version: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row = connection.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations WHERE definition_version=?",
        (version,),
    ).fetchone()
    if row is None:
        raise RuntimeError("current version registration is missing")
    # Deliberately call the classmethod against this connection; no Store is made.
    definition = Store.chain_meme_trader_effective_definition_from_connection(connection, version, row[0])
    policies = [dict(policy) for policy in definition.get("policies", [])]
    if not policies:
        raise RuntimeError("current effective definition has no policies")
    return definition, policies


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def aggregate_metrics(connection: sqlite3.Connection, version: str) -> dict[str, dict[str, Any]]:
    """One indexed per-version aggregate; partial exits count as realized PnL."""
    # The portable UNION stays bounded by the per-version indexes and avoids a
    # dependency on the desktop SQLite build's FULL OUTER JOIN support.
    sql = """
    WITH trade_totals AS (
      SELECT arm_id,
        SUM(net_cash_flow_usd) AS settled_net_cash,
        SUM(CASE WHEN side IN ('SELL','WRITEOFF') THEN realized_pnl_usd END) AS realized_pnl,
        COUNT(CASE WHEN side IN ('SELL','WRITEOFF') THEN 1 END) AS realized_trade_count,
        SUM(CASE WHEN net_cash_flow_usd IS NULL OR abs(net_cash_flow_usd)>=1.0e308 THEN 1 ELSE 0 END) AS bad_cash_count,
        SUM(CASE WHEN side IN ('SELL','WRITEOFF')
                  AND (realized_pnl_usd IS NULL OR abs(realized_pnl_usd)>=1.0e308)
                 THEN 1 ELSE 0 END) AS bad_realized_pnl_count
      FROM chain_meme_trader_trades WHERE definition_version=? GROUP BY arm_id
    ), terminal_totals AS (
      SELECT arm_id, COUNT(*) AS terminal_positions
      FROM chain_meme_trader_positions
      WHERE definition_version=? AND status IN ('closed','written_off') GROUP BY arm_id
    )
    SELECT t.arm_id, t.settled_net_cash, t.realized_pnl, t.realized_trade_count,
           t.bad_cash_count, t.bad_realized_pnl_count, p.terminal_positions
      FROM trade_totals t LEFT JOIN terminal_totals p ON p.arm_id=t.arm_id
    UNION ALL
    SELECT p.arm_id, t.settled_net_cash, t.realized_pnl, t.realized_trade_count,
           t.bad_cash_count, t.bad_realized_pnl_count, p.terminal_positions
      FROM terminal_totals p LEFT JOIN trade_totals t ON t.arm_id=p.arm_id
      WHERE t.arm_id IS NULL
    """
    output: dict[str, dict[str, Any]] = {}
    for row in connection.execute(sql, (version, version)).fetchall():
        output[str(row[0])] = {
            "settled_net_cash": _finite(row[1]),
            "realized_pnl": _finite(row[2]),
            "realized_trade_count": int(row[3] or 0),
            "bad_cash_count": int(row[4] or 0),
            "bad_realized_pnl_count": int(row[5] or 0),
            "terminal_positions": int(row[6] or 0),
        }
    return output


def select_depleted_failures(
    policies: Iterable[dict[str, Any]], metrics: dict[str, dict[str, Any]], initial_cash: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return selected active arms and a complete explanatory preview."""
    initial = _finite(initial_cash)
    if initial is None or initial <= 0:
        raise RuntimeError("effective initial Paper cash is not a valid positive monetary value")
    selected, preview = [], []
    for policy in policies:
        arm = str(policy.get("arm_id") or "")
        metric = metrics.get(arm, {})
        settled_net = metric.get("settled_net_cash")
        realized = metric.get("realized_pnl")
        terminal = int(metric.get("terminal_positions") or 0)
        realized_trades = int(metric.get("realized_trade_count") or 0)
        bad_cash = int(metric.get("bad_cash_count") or 0)
        bad_realized = int(metric.get("bad_realized_pnl_count") or 0)
        settled_cash = initial + settled_net if settled_net is not None else None
        realized_equity = initial + realized if realized is not None else None
        active = not bool(policy.get("entry_paused") or policy.get("account_lifecycle"))
        valid = (settled_cash is not None and realized_equity is not None
                 and bad_cash == 0 and bad_realized == 0)
        eligible = bool(valid and terminal >= 1 and realized_trades >= 1
                        and settled_cash < LIMIT_USD and realized_equity < LIMIT_USD)
        disposition = "SELECT" if active and eligible else (
            "PRESERVE_EXISTING_LIFECYCLE" if not active else "NOT_DEPLETED_BY_SETTLED_REALIZED_LOSS"
        )
        item = {"arm_id": arm, "disposition": disposition, "terminal_positions": terminal,
                "realized_trade_count": realized_trades,
                "bad_cash_count": bad_cash, "bad_realized_pnl_count": bad_realized,
                "settled_cash_usd": settled_cash, "realized_equity_usd": realized_equity,
                "account_lifecycle": policy.get("account_lifecycle"), "entry_paused": bool(policy.get("entry_paused")),
                "valid_monetary_values": valid}
        preview.append(item)
        if disposition == "SELECT":
            selected.append(item)
    return selected, preview


def merged_control(old: dict[str, Any], selected: Iterable[dict[str, Any]], now: str) -> dict[str, Any]:
    new = copy.deepcopy(old)
    arms = new.setdefault("arms", {})
    for item in selected:
        arm = item["arm_id"]
        if arm in arms:  # effective policy already said paused; protect against stale selection.
            continue
        arms[arm] = {
            "state": "PAUSED_NEW_ENTRY", "assessment_status": "FAILED",
            "assessment_note": "Paper capital depleted by settled realized losses; stop new entry and preserve original exits.",
            "assessment_evidence": "depleted_failures158 operation receipt",
            "reason": "paper realized loss depletion; immutable contracts/history and existing positions/exits preserved",
        }
    new.update({"activated_at": now, "operation": "pause_new_entry_preserve_natural_exit"})
    return new


def current_plan(connection: sqlite3.Connection) -> dict[str, Any]:
    version = active_version(connection)
    require_clean_replay(connection, version)
    definition, policies = effective_policies(connection, version)
    metrics = aggregate_metrics(connection, version)
    selected, preview = select_depleted_failures(
        policies, metrics, definition.get("starting_cash_usd_each_arm"),
    )
    return {"version": version, "initial_cash_usd": definition.get("starting_cash_usd_each_arm"),
            "selected": selected, "effective_arms": preview}


def readonly_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    deadline = time.monotonic() + 5.0
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
    return connection


def guard_config(path: Path) -> Path:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled", False):
        raise RuntimeError("refuse: config must be Paper and Live disabled")
    configured = Path(config["database"])
    return path if path else (configured if configured.is_absolute() else ROOT / configured)


def kv_only_authorizer(action: int, arg1: str | None, _arg2: str | None, _db: str | None, _source: str | None) -> int:
    if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE):
        return sqlite3.SQLITE_OK if arg1 == "kv" else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def apply(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.5)
    connection.row_factory = sqlite3.Row
    try:
        deadline = time.monotonic() + WRITE_DEADLINE_SECONDS
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1_000)
        connection.execute("BEGIN IMMEDIATE")
        plan = current_plan(connection)
        version, now = plan["version"], utcstamp()
        key = CONTROL_PREFIX + version
        row = connection.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        old = json_object(row[0]) if row else {"arms": {}}
        new = merged_control(old, plan["selected"], now)
        receipt_key = RECEIPT_PREFIX + version + ":" + now.replace(":", "")
        connection.set_authorizer(kv_only_authorizer)
        connection.execute(
            "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(new, ensure_ascii=False, sort_keys=True), now),
        )
        receipt = {"operation": "depleted_failures158", "version": version, "at": now,
                   "selected": plan["selected"], "previous_control": old, "control_key": key}
        connection.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)",
                           (receipt_key, json.dumps(receipt, ensure_ascii=False, sort_keys=True), now))
        connection.commit()
        return {**plan, "status": "applied", "receipt_key": receipt_key, "previous_control": old}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.set_progress_handler(None, 0)
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    path = guard_config(args.database)
    if args.apply:
        result = apply(path)
        archive = ROOT / "data" / "research" / "depleted_failures158" / (utcstamp().replace(":", "") + ".json")
        archive.parent.mkdir(parents=True, exist_ok=True)
        # A receipt is rollback evidence, never a replaceable status file.
        with archive.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
    else:
        with readonly_connection(path) as connection:
            result = {**current_plan(connection), "status": "preview"}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
