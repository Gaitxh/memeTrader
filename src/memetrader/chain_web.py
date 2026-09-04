from __future__ import annotations

import argparse
import hashlib
import json
import math
import mimetypes
import shutil
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .live_wallets import LiveWalletError, SolanaLiveWalletManager
from .models import iso, parse_time, utcnow
from .runtime import load_config
from .store import Store


class ChainWebData:
    """Data boundary for the independent ChainMemeTrader console."""

    LIVE_SPARKLINE_POINTS = 12
    LIVE_DETAIL_CURVE_POINTS = 300
    LIVE_OPEN_POSITION_LIMIT = 200
    STATE_CACHE_MAX_ENTRIES = 16

    def __init__(self, config_path: str | Path):
        config, root = load_config(config_path)
        self.config = config
        self.root = root
        self.live_enabled = bool((config.get("live") or {}).get("enabled", False))
        database = Path(str(config["database"]))
        self.database = database if database.is_absolute() else root / database
        self.wallets = SolanaLiveWalletManager(root, self.database)
        self._cache_lock = threading.Lock()
        self._state_cache: dict[tuple[bool, str | None], tuple[float, dict[str, Any]]] = {}
        self._universe_cache: tuple[tuple[Any, ...], dict[str, Any]] | None = None
        self._last_web_error_record_at: dict[str, float] = {}
        self.strategy_universe_path = (
            root / "docs" / "PROJECT_CONTEXT" /
            "CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json"
        )

    def wallet_state(self, *, refresh: bool = False) -> dict[str, Any]:
        payload = self.wallets.snapshot(refresh=refresh)
        live = self.state(compact=True)
        strategies = {
            str(item.get("arm_id") or ""): item
            for item in live.get("strategies", [])
        }
        for wallet in payload.get("wallets", []):
            strategy = strategies.get(str(wallet.get("strategy_id") or ""), {})
            account = strategy.get("account") or {}
            wallet["strategy"] = {
                "arm_id": strategy.get("arm_id") or wallet.get("strategy_id"),
                "name": strategy.get("name"),
                "stage": strategy.get("stage"),
                "realized_pnl_usd": account.get("capital_neutral_realized_pnl_usd"),
                "unrealized_pnl_usd": account.get("capital_neutral_unrealized_pnl_usd"),
                "total_pnl_usd": account.get("capital_neutral_total_pnl_usd"),
                "open_position_count": account.get("open_position_count", 0),
                "as_of": account.get("recorded_at"),
                "valuation_status": account.get("valuation_status"),
                "maturity": strategy.get("maturity"),
                "forward_age_seconds": strategy.get("forward_age_seconds"),
            }
        return payload

    def wallet_detail(self, wallet_id: str, *, refresh: bool = False) -> dict[str, Any]:
        payload = self.wallets.detail(wallet_id, refresh=refresh)
        wallet = payload["wallet"]
        arm_id = str(wallet.get("strategy_id") or "")
        definition_version = str(wallet.get("definition_version") or "")
        live = self.state(compact=True, arm_id=arm_id)
        strategy = next(
            (item for item in live.get("strategies", []) if item.get("arm_id") == arm_id),
            None,
        )
        if not definition_version:
            definition_version = str(live.get("version") or "")
        with self._connect() as connection:
            paper_trades = self._rows(
                connection,
                "SELECT id,token_id,side,gross_usd,realized_pnl_usd,reason,created_at "
                "FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=? "
                "ORDER BY id DESC LIMIT 100",
                (definition_version, arm_id),
            )
            terminal_positions = self._rows(
                connection,
                "SELECT shadow_cohort_id,token_id,status,opened_at,closed_at,stake_usd,"
                "realized_pnl_usd FROM chain_meme_trader_positions "
                "WHERE definition_version=? AND arm_id=? AND status<>'open' "
                "ORDER BY COALESCE(closed_at,opened_at) DESC LIMIT 50",
                (definition_version, arm_id),
            )
        payload["strategy"] = strategy
        payload["paper"] = {
            "version": definition_version,
            "open_positions": live.get("open_positions", []),
            "terminal_positions": terminal_positions,
            "trades": paper_trades,
        }
        payload["account"] = (strategy or {}).get("account") or {}
        payload["positions"] = live.get("open_positions", [])
        payload["trades"] = paper_trades
        payload["live_executions"] = payload.get("executions", [])
        wallet["balance"] = payload.get("balance") or {}
        wallet["strategy_pnl_usd"] = payload["account"].get(
            "capital_neutral_total_pnl_usd"
        )
        wallet["open_position_count"] = payload["account"].get(
            "open_position_count", 0
        )
        return payload

    def connect_wallet(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) - {"private_key", "alias", "strategy_id"}:
            raise LiveWalletError("钱包参数无效")
        return self.wallets.connect(
            payload.get("private_key"), payload.get("alias"), payload.get("strategy_id")
        )

    def bind_wallet(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) - {"wallet_id", "strategy_id"}:
            raise LiveWalletError("钱包绑定参数无效")
        return self.wallets.bind(payload.get("wallet_id"), payload.get("strategy_id"))

    def set_wallet_live(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) - {"wallet_id", "enabled"}:
            raise LiveWalletError("实盘状态参数无效")
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            raise LiveWalletError("实盘状态参数无效")
        if enabled and not self.live_enabled:
            raise LiveWalletError("实盘已被全局配置锁定；当前仅允许 Paper 前向运行")
        return self.wallets.set_enabled(payload.get("wallet_id"), enabled)

    @staticmethod
    def _error_summary_from_connection(connection: sqlite3.Connection) -> dict[str, Any]:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_error_cases'"
        ).fetchone()
        if exists is None:
            return {"open": 0, "high": 0, "new": 0, "in_progress": 0, "latest_at": None}
        row = connection.execute(
            "SELECT SUM(status IN ('new','in_progress')) AS open_count,"
            "SUM(status IN ('new','in_progress') AND severity='high') AS high_count,"
            "SUM(status='new') AS new_count,SUM(status='in_progress') AS progress_count,"
            "MAX(last_seen_at) AS latest_at FROM system_error_cases"
        ).fetchone()
        return {
            "open": int(row["open_count"] or 0),
            "high": int(row["high_count"] or 0),
            "new": int(row["new_count"] or 0),
            "in_progress": int(row["progress_count"] or 0),
            "latest_at": row["latest_at"],
        }

    def error_state(self) -> dict[str, Any]:
        with self._connect() as connection:
            summary = self._error_summary_from_connection(connection)
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='system_error_cases'"
            ).fetchone()
            cases = self._rows(
                connection,
                "SELECT id,area,component,error_type,message_safe,severity,status,"
                "first_seen_at,last_seen_at,occurrence_count,resolved_at,resolution_note "
                "FROM system_error_cases ORDER BY "
                "CASE status WHEN 'new' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,"
                "CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,"
                "last_seen_at DESC,id DESC LIMIT 250",
            ) if exists is not None else []
        return {
            "status": "ok", "summary": summary,
            "cases": cases, "errors": cases, "as_of": iso(),
        }

    def error_detail(self, case_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            case = connection.execute(
                "SELECT id,area,component,error_type,message_safe,severity,status,"
                "first_seen_at,last_seen_at,occurrence_count,last_context_json,"
                "resolved_at,resolution_note FROM system_error_cases WHERE id=?",
                (int(case_id),),
            ).fetchone()
            if case is None:
                return {"status": "not_found", "id": int(case_id)}
            item = dict(case)
            item["last_context"] = Store._json_object(item.pop("last_context_json", "{}"))
            occurrences = self._rows(
                connection,
                "SELECT id,observed_at,context_safe_json FROM system_error_occurrences "
                "WHERE case_id=? ORDER BY id DESC LIMIT 100",
                (int(case_id),),
            )
            for occurrence in occurrences:
                occurrence["context"] = Store._json_object(
                    occurrence.pop("context_safe_json", "{}")
                )
                occurrence["component"] = item["component"]
                occurrence["summary"] = ", ".join(
                    f"{key}: {value}"
                    for key, value in occurrence["context"].items()
                ) or item["message_safe"]
            reports = self._rows(
                connection,
                "SELECT id,action,summary,evidence_safe,report_path,actor,recorded_at "
                "FROM system_error_resolution_reports WHERE case_id=? "
                "ORDER BY id DESC LIMIT 100",
                (int(case_id),),
            )
        return {
            "status": "ok", "case": item, "error": item,
            "occurrences": occurrences, "repair_reports": reports,
        }

    def update_error(self, payload: Any) -> dict[str, Any]:
        allowed_keys = {"id", "status", "note", "evidence", "report_path"}
        if not isinstance(payload, dict) or set(payload) - allowed_keys:
            raise ValueError("错误状态参数无效")
        try:
            case_id = int(payload.get("id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("错误编号无效") from exc
        with self._connect_rw() as connection:
            with connection:
                Store.update_system_error_case_from_connection(
                    connection, case_id, status=str(payload.get("status") or ""),
                    note=str(payload.get("note") or ""),
                    evidence_safe=str(payload.get("evidence") or ""),
                    report_path=str(payload.get("report_path") or ""),
                    actor="user",
                )
        return self.error_detail(case_id)

    def record_web_error(self, route: str, exc: BaseException) -> None:
        """Best-effort, sanitized recording for the 07 error ledger."""
        if isinstance(
            exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
        ):
            return
        try:
            component = Store._safe_error_text(route, limit=120) or "web"
            error_type = Store._safe_error_text(type(exc).__name__, limit=120)
            message = Store._safe_error_text(str(exc) or error_type)
            observed_at = iso()
            fingerprint = hashlib.sha256(
                f"web\n{component}\n{error_type}\n{message}".encode("utf-8")
            ).hexdigest()
            now = time.monotonic()
            with self._cache_lock:
                previous = self._last_web_error_record_at.get(fingerprint)
                if previous is not None and now - previous < 60.0:
                    return
                self._last_web_error_record_at[fingerprint] = now
            with self._connect_rw() as connection:
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='system_error_cases'"
                ).fetchone()
                if exists is None:
                    return
                with connection:
                    prior = connection.execute(
                        "SELECT id,status FROM system_error_cases WHERE fingerprint=?",
                        (fingerprint,),
                    ).fetchone()
                    context_json = Store._bounded_json({"route": component}, max_chars=1_000)
                    if prior is None:
                        cursor = connection.execute(
                            "INSERT INTO system_error_cases(fingerprint,area,component,error_type,"
                            "message_safe,severity,status,first_seen_at,last_seen_at,"
                            "occurrence_count,last_context_json) "
                            "VALUES(?,'web',?,?,?,'medium','new',?,?,1,?)",
                            (fingerprint, component, error_type, message,
                             observed_at, observed_at, context_json),
                        )
                        case_id = int(cursor.lastrowid)
                    else:
                        case_id = int(prior["id"])
                        connection.execute(
                            "UPDATE system_error_cases SET last_seen_at=?,"
                            "occurrence_count=occurrence_count+1,last_context_json=?,"
                            "status=CASE WHEN status='fixed' THEN 'new' ELSE status END,"
                            "resolved_at=CASE WHEN status='fixed' THEN NULL ELSE resolved_at END "
                            "WHERE id=?",
                            (observed_at, context_json, case_id),
                        )
                    connection.execute(
                        "INSERT INTO system_error_occurrences(case_id,observed_at,context_safe_json) "
                        "VALUES(?,?,?)", (case_id, observed_at, context_json),
                    )
        except (OSError, sqlite3.Error, ValueError):
            return

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.database.as_posix()}?mode=ro", uri=True, timeout=5
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _connect_rw(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _rows(connection: sqlite3.Connection, sql: str, values: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in connection.execute(sql, values).fetchall()]

    def state(self, *, compact: bool = False, arm_id: str | None = None) -> dict[str, Any]:
        ttl = 1.0 if compact else 10.0
        now = time.monotonic()
        cache_key = (compact, str(arm_id or "").strip() or None)
        with self._cache_lock:
            for key, (created_at, _) in list(self._state_cache.items()):
                key_ttl = 1.0 if key[0] else 10.0
                if now - created_at > key_ttl:
                    del self._state_cache[key]
            cached = self._state_cache.get(cache_key)
            if cached is not None and now - cached[0] <= ttl:
                return cached[1]
        payload = (
            self._compact_state_uncached(arm_id=cache_key[1])
            if compact else self._state_uncached(arm_id=cache_key[1])
        )
        with self._cache_lock:
            self._state_cache[cache_key] = (time.monotonic(), payload)
            while len(self._state_cache) > self.STATE_CACHE_MAX_ENTRIES:
                oldest_key = min(
                    self._state_cache,
                    key=lambda key: self._state_cache[key][0],
                )
                del self._state_cache[oldest_key]
        return payload

    def _compact_state_uncached(self, *, arm_id: str | None = None) -> dict[str, Any]:
        """Return the compact mutable account and open-position surface."""
        current = utcnow()
        current_iso = iso(current)
        locked_by_config = not self.live_enabled
        with self._connect() as connection:
            heartbeat = connection.execute(
                "SELECT last_item_at,last_ok_at FROM source_health "
                "WHERE source='chain-meme-trader'"
            ).fetchone()
            heartbeat_at = (
                heartbeat["last_item_at"] or heartbeat["last_ok_at"]
                if heartbeat is not None else None
            )
            heartbeat_age = (
                (current - parse_time(heartbeat_at)).total_seconds()
                if heartbeat_at else None
            )
            if heartbeat_age is not None and heartbeat_age < 0.0:
                heartbeat_age = None
            active = connection.execute(
                "SELECT definition_version FROM chain_meme_trader_v6_activations "
                "WHERE entry_execution_enabled=1 "
                "ORDER BY activated_at DESC,rowid DESC LIMIT 1"
            ).fetchone()
            active_version = str(
                active["definition_version"]
                if active is not None else Store.CHAIN_MEME_TRADER_VERSION
            )
            registration = connection.execute(
                "SELECT definition_json FROM chain_meme_trader_registrations "
                "WHERE definition_version=?", (active_version,),
            ).fetchone()
            base_system = {
                "runtime_status": (
                    "running"
                    if heartbeat_age is not None and heartbeat_age <= 30.0 else "stale"
                ),
                "heartbeat_at": heartbeat_at,
                "heartbeat_age_seconds": heartbeat_age,
                "refresh_seconds": 5,
                "chain": "Solana / BSC / Robinhood",
                "paper_only": locked_by_config,
                "live_locked": locked_by_config,
                "locked_by_config": locked_by_config,
                "live_adapter_status": (
                    "locked_by_config" if locked_by_config else "ready_per_wallet_opt_in"
                ),
            }
            if registration is None:
                return {
                    "status": "not_enabled",
                    "version": active_version,
                    "generated_at": current_iso,
                    "system": {
                        **base_system,
                        "latest_account_snapshot_at": None,
                        "open_position_count": 0,
                        "unique_held_token_count": 0,
                        "pending_exit_quotes": 0,
                    },
                    "strategies": [],
                    "open_positions": [],
                }

            definition = Store.chain_meme_trader_effective_definition_from_connection(
                connection, active_version, registration["definition_json"],
            )
            policies = list(definition.get("policies") or [])
            corrections = Store._chain_meme_trader_market_fill_corrections_from_connection(
                connection, active_version,
            )
            corrections_by_position = {
                (str(row["arm_id"]), int(row["shadow_cohort_id"])): row
                for row in corrections
            }
            corrections_by_trade = {
                int(row["source_trade_id"]): row for row in corrections
            }
            contaminations = (
                Store._chain_meme_trader_accounting_contaminations_from_connection(
                    connection, active_version,
                )
            )
            contaminated_positions = {
                (str(row["arm_id"]), int(row["shadow_cohort_id"]))
                for row in contaminations
            }
            accounting_effective_after = (
                Store._chain_meme_trader_accounting_effective_after_from_connection(
                    connection, active_version,
                )
            )
            account_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(chain_meme_trader_account_snapshots)"
                ).fetchall()
            }
            account_filters = ["definition_version=?"]
            account_values: list[Any] = [active_version]
            if "ledger_trade_frontier_id" in account_columns:
                account_filters.append("ledger_trade_frontier_id IS NOT NULL")
            if accounting_effective_after:
                account_filters.append("recorded_at>=?")
                account_values.append(accounting_effective_after)
            account_where = " AND ".join(account_filters)
            ledger_projection = (
                "s.ledger_trade_frontier_id"
                if "ledger_trade_frontier_id" in account_columns
                else "NULL AS ledger_trade_frontier_id"
            )
            latest_accounts = {
                str(row["arm_id"]): dict(row)
                for row in connection.execute(
                    "SELECT s.arm_id,s.recorded_at,s.cash_usd,s.realized_pnl_usd,"
                    "s.executable_equity_usd,s.executable_unrealized_pnl_usd,"
                    "s.executable_total_pnl_usd,s.indicative_equity_usd,"
                    "s.indicative_unrealized_pnl_usd,s.indicative_total_pnl_usd,"
                    "s.indicative_position_count,s.indicative_is_complete,"
                    f"s.valuation_status,{ledger_projection} "
                    "FROM chain_meme_trader_account_snapshots s "
                    "JOIN (SELECT arm_id,MAX(id) AS id FROM "
                    f"chain_meme_trader_account_snapshots WHERE {account_where} "
                    "GROUP BY arm_id) latest ON latest.id=s.id",
                    tuple(account_values),
                ).fetchall()
            }
            curve_rows = connection.execute(
                "SELECT recorded_at,arm_id,realized_pnl_usd,"
                "indicative_unrealized_pnl_usd,indicative_total_pnl_usd,"
                "executable_unrealized_pnl_usd,executable_total_pnl_usd "
                "FROM chain_meme_trader_account_snapshots "
                f"WHERE {account_where} ORDER BY id DESC LIMIT ?",
                (
                    *account_values,
                    max(
                        self.LIVE_SPARKLINE_POINTS,
                        len(policies) * self.LIVE_SPARKLINE_POINTS,
                    ),
                ),
            ).fetchall()
            curves_by_arm: dict[str, list[dict[str, Any]]] = {}
            for row in reversed(curve_rows):
                curve = curves_by_arm.setdefault(str(row["arm_id"]), [])
                curve.append({
                    "recorded_at": row["recorded_at"],
                    "realized_pnl_usd": row["realized_pnl_usd"],
                    "unrealized_pnl_usd": row["indicative_unrealized_pnl_usd"],
                    "total_pnl_usd": row["indicative_total_pnl_usd"],
                })
                if len(curve) > self.LIVE_SPARKLINE_POINTS:
                    del curve[:-self.LIVE_SPARKLINE_POINTS]
            if arm_id:
                focused_curve_rows = connection.execute(
                    "SELECT recorded_at,arm_id,realized_pnl_usd,"
                    "indicative_unrealized_pnl_usd,indicative_total_pnl_usd,"
                    "executable_unrealized_pnl_usd,executable_total_pnl_usd "
                    "FROM chain_meme_trader_account_snapshots "
                    f"WHERE {account_where} AND arm_id=? "
                    "ORDER BY id DESC LIMIT ?",
                    (
                        *account_values, arm_id,
                        self.LIVE_DETAIL_CURVE_POINTS,
                    ),
                ).fetchall()
                curves_by_arm[arm_id] = [
                    {
                        "recorded_at": row["recorded_at"],
                        "realized_pnl_usd": row["realized_pnl_usd"],
                        "unrealized_pnl_usd": row["indicative_unrealized_pnl_usd"],
                        "total_pnl_usd": row["indicative_total_pnl_usd"],
                    }
                    for row in reversed(focused_curve_rows)
                ]
            latest_snapshot_at = max(
                (
                    str(item.get("recorded_at") or "")
                    for item in latest_accounts.values()
                ),
                default="",
            ) or None
            position_stats: dict[str, dict[str, int]] = defaultdict(
                lambda: {
                    "position_count": 0, "open_count": 0, "closed_count": 0,
                    "written_off_count": 0, "win_count": 0,
                }
            )
            terminal_rows_by_arm: dict[str, list[tuple[str, float]]] = {}
            effective_realized_by_arm: dict[str, float] = defaultdict(float)
            effective_unrealized_by_arm: dict[str, float] = defaultdict(float)
            priced_open_by_arm: dict[str, int] = defaultdict(int)
            effective_open_token_ids: set[str] = set()
            for row in self._rows(
                connection,
                "SELECT p.arm_id,p.shadow_cohort_id,p.token_id,p.status,p.stake_usd,"
                "p.amount_raw,p.initial_amount_raw,p.paper_quantity_tokens,"
                "p.remaining_quantity_tokens,p.entry_signal_price_usd,"
                "p.entry_execution_price_usd,p.allocated_cost_usd,p.realized_pnl_usd,"
                "p.opened_at,p.closed_at,m.pair_address,m.price_usd,m.liquidity_usd,"
                "m.status AS market_status,m.observed_at AS market_observed_at,"
                "m.recorded_at AS market_recorded_at,m.last_success_at "
                "FROM chain_meme_trader_positions p LEFT JOIN "
                "chain_meme_trader_market_marks m ON m.token_id=p.token_id "
                "WHERE p.definition_version=? AND p.status<>'ineligible'",
                (active_version,),
            ):
                arm = str(row["arm_id"])
                key = (arm, int(row["shadow_cohort_id"]))
                if key in contaminated_positions:
                    continue
                correction = corrections_by_position.get(key)
                effective_status = str(row["status"])
                effective_pnl = float(row["realized_pnl_usd"] or 0.0)
                if correction is not None:
                    replacement = str(correction["replacement_outcome"])
                    effective_status = {
                        "SELL": "closed", "WRITEOFF": "written_off",
                        "UNRESOLVED": "open",
                    }[replacement]
                    effective_pnl += float(
                        correction["realized_adjustment_usd"] or 0.0
                    )
                effective_realized_by_arm[arm] += effective_pnl
                stats = position_stats[arm]
                stats["position_count"] += 1
                if effective_status == "open":
                    stats["open_count"] += 1
                    effective_open_token_ids.add(str(row["token_id"]))
                elif effective_status in {"closed", "written_off"}:
                    stats[f"{effective_status}_count"] += 1
                    stats["win_count"] += int(effective_pnl > 0.0)
                    effective_closed_at = (
                        str(correction.get("replacement_observed_at") or row["closed_at"] or "")
                        if correction is not None else str(row["closed_at"] or "")
                    )
                    terminal_rows_by_arm.setdefault(arm, []).append(
                        (effective_closed_at, effective_pnl)
                    )
                if effective_status == "open":
                    market_at = row.get("last_success_at") or row.get("market_recorded_at")
                    market_age = (
                        (current - parse_time(market_at)).total_seconds()
                        if market_at else None
                    )
                    observed_age = (
                        (current - parse_time(row["market_observed_at"])).total_seconds()
                        if row.get("market_observed_at") else None
                    )
                    fresh_market = bool(
                        row.get("market_status") == "VISIBLE"
                        and row.get("pair_address")
                        and float(row.get("price_usd") or 0.0) > 0.0
                        and market_age is not None and 0.0 <= market_age <= 15.0
                        and observed_age is not None and 0.0 <= observed_age <= 15.0
                    )
                    entry_price = float(
                        row.get("entry_execution_price_usd")
                        or row.get("entry_signal_price_usd") or 0.0
                    )
                    initial_raw = int(
                        row.get("initial_amount_raw") or row.get("amount_raw") or 0
                    )
                    if fresh_market and entry_price > 0.0 and initial_raw > 0:
                        remaining_fraction = max(
                            0.0,
                            min(1.0, int(row.get("amount_raw") or 0) / initial_raw),
                        )
                        remaining_cost = max(
                            0.0,
                            float(row.get("stake_usd") or 0.0)
                            - float(row.get("allocated_cost_usd") or 0.0),
                        )
                        indicative_value = (
                            0.0
                            if row.get("liquidity_usd") is not None
                            and float(row["liquidity_usd"]) < 1.0
                            else max(
                                0.0,
                                float(row.get("stake_usd") or 0.0)
                                * remaining_fraction
                                * float(row.get("price_usd") or 0.0)
                                / entry_price
                                * (1.0 - int(definition.get("slippage_bps") or 400) / 10_000.0),
                            )
                        )
                        effective_unrealized_by_arm[arm] += indicative_value - remaining_cost
                        priced_open_by_arm[arm] += 1
            effective_open_position_count = sum(
                stats["open_count"] for stats in position_stats.values()
            )
            decision_stats = {
                str(row["arm_id"]): dict(row)
                for row in connection.execute(
                    "SELECT arm_id,"
                    "SUM(CASE WHEN status='admitted' THEN 1 ELSE 0 END) AS admitted,"
                    "SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected "
                    "FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
                    "GROUP BY arm_id",
                    (active_version,),
                ).fetchall()
            }
            strategies: list[dict[str, Any]] = []
            capital_model = str(
                definition.get("capital_model") or "legacy_cash_limited"
            )
            compact_policy_keys = {
                "arm_id", "stage", "name", "entry_family", "exit_family", "exit_mode",
                "max_hold_minutes", "fixed_horizon_minutes", "forward_enabled",
                "fidelity_status", "forward_started_at",
                "forward_activation_snapshot_id", "runtime_addition_id",
            }
            for policy in policies:
                policy_arm_id = str(policy.get("arm_id") or "")
                account = latest_accounts.get(policy_arm_id)
                stats = position_stats.get(policy_arm_id, {})
                if account is None:
                    account = {
                        "arm_id": policy_arm_id,
                        "recorded_at": None,
                        "indicative_unrealized_pnl_usd": (
                            None if accounting_effective_after else 0.0
                        ),
                        "indicative_total_pnl_usd": (
                            None if accounting_effective_after else 0.0
                        ),
                        "realized_pnl_usd": (
                            None if accounting_effective_after else 0.0
                        ),
                        "valuation_status": "awaiting_first_snapshot",
                    }
                account.update({
                    "open_position_count": int(stats.get("open_count") or 0),
                    "closed_position_count": int(stats.get("closed_count") or 0),
                    "written_off_position_count": int(stats.get("written_off_count") or 0),
                    "win_count": int(stats.get("win_count") or 0),
                })
                terminal_count = (
                    int(account["closed_position_count"])
                    + int(account["written_off_position_count"])
                )
                realized_pnl = effective_realized_by_arm.get(policy_arm_id, 0.0)
                open_count = int(account["open_position_count"])
                indicative_complete = priced_open_by_arm.get(policy_arm_id, 0) == open_count
                unrealized_pnl = (
                    effective_unrealized_by_arm.get(policy_arm_id, 0.0)
                    if indicative_complete else None
                )
                total_pnl = (
                    realized_pnl + unrealized_pnl
                    if unrealized_pnl is not None else None
                )
                account.update({
                    "realized_pnl_usd": realized_pnl,
                    "indicative_unrealized_pnl_usd": unrealized_pnl,
                    "indicative_total_pnl_usd": total_pnl,
                    "indicative_position_count": priced_open_by_arm.get(policy_arm_id, 0),
                    "indicative_is_complete": indicative_complete,
                    "valuation_status": (
                        "complete_market_mark" if indicative_complete
                        else "partial_market_mark_unknown"
                    ),
                })
                account["capital_model"] = capital_model
                account["capital_neutral_realized_pnl_usd"] = account.get(
                    "realized_pnl_usd"
                )
                account["capital_neutral_unrealized_pnl_usd"] = account.get(
                    "indicative_unrealized_pnl_usd"
                )
                account["capital_neutral_total_pnl_usd"] = total_pnl
                account["terminal_position_count"] = terminal_count
                account["win_rate_fraction"] = (
                    float(account["win_count"]) / terminal_count
                    if terminal_count > 0 else None
                )
                account["account_return_fraction"] = None
                curve = list(curves_by_arm.get(policy_arm_id, []))
                if accounting_effective_after:
                    curve_limit = (
                        self.LIVE_DETAIL_CURVE_POINTS
                        if arm_id == policy_arm_id else self.LIVE_SPARKLINE_POINTS
                    )
                    curve = [
                        *curve[-max(0, curve_limit - 1):],
                        {
                            "recorded_at": current_iso,
                            "realized_pnl_usd": realized_pnl,
                            "unrealized_pnl_usd": unrealized_pnl,
                            "total_pnl_usd": total_pnl,
                            "synthetic_effective_point": True,
                        },
                    ]
                terminal_pnls = [
                    value for _closed_at, value in sorted(
                        terminal_rows_by_arm.get(policy_arm_id, []),
                        key=lambda item: item[0],
                    )
                ]
                winning_pnls = [value for value in terminal_pnls if value > 0.0]
                losing_pnls = [value for value in terminal_pnls if value < 0.0]
                average_win = (
                    sum(winning_pnls) / len(winning_pnls) if winning_pnls else None
                )
                average_loss = (
                    abs(sum(losing_pnls) / len(losing_pnls)) if losing_pnls else None
                )
                profit_factor = (
                    sum(winning_pnls) / abs(sum(losing_pnls))
                    if losing_pnls else None
                )
                # Drawdown is an accounting metric: use every valid terminal
                # realized result, not the clipped display sparkline.
                realized_curve = []
                cumulative_realized = 0.0
                for value in terminal_pnls:
                    if not isinstance(value, (int, float)) or not math.isfinite(value):
                        continue
                    cumulative_realized += float(value)
                    realized_curve.append(cumulative_realized)
                starting_cash = float(
                    definition.get("starting_cash_usd_each_arm") or 0.0
                )
                peak_equity = (
                    starting_cash if capital_model == "legacy_cash_limited" else 0.0
                )
                peak = peak_equity
                max_drawdown = 0.0
                max_drawdown_fraction: float | None = None
                for realized in realized_curve:
                    equity = peak_equity + realized
                    peak = max(peak, equity)
                    drawdown = max(0.0, peak - equity)
                    max_drawdown = max(max_drawdown, drawdown)
                    if capital_model == "legacy_cash_limited" and peak > 0.0:
                        fraction = drawdown / peak
                        max_drawdown_fraction = max(
                            max_drawdown_fraction or 0.0, fraction,
                        )
                tail_count = (
                    max(1, (len(terminal_pnls) + 9) // 10) if terminal_pnls else 0
                )
                account.update({
                    "metric_sample_count": len(terminal_pnls),
                    "metric_sample_status": (
                        "no_closed_results" if not terminal_pnls
                        else "insufficient_sample" if len(terminal_pnls) < 30
                        else "sufficient_sample"
                    ),
                    "profit_loss_ratio": (
                        average_win / average_loss
                        if average_win is not None and average_loss not in {None, 0.0}
                        else None
                    ),
                    "profit_factor": profit_factor,
                    "profit_factor_status": (
                        "no_closed_results" if not terminal_pnls
                        else "no_losses" if not losing_pnls
                        else "available"
                    ),
                    "expectancy_usd": (
                        sum(terminal_pnls) / len(terminal_pnls) if terminal_pnls else None
                    ),
                    "max_drawdown_usd": max_drawdown,
                    "max_drawdown_fraction": max_drawdown_fraction,
                    "max_drawdown_basis": "realized_terminal_pnl",
                    "tail_return_usd": (
                        sum(sorted(terminal_pnls)[:tail_count]) / tail_count
                        if terminal_pnls else None
                    ),
                })
                counts = decision_stats.get(policy_arm_id, {})
                admitted = int(counts.get("admitted") or 0)
                rejected = int(counts.get("rejected") or 0)
                forward_started_at = str(
                    policy.get("forward_started_at") or current_iso
                )
                forward_age_seconds = max(
                    0.0,
                    (current - parse_time(forward_started_at)).total_seconds(),
                )
                maturity = (
                    "mature" if terminal_count >= 30
                    else "provisional" if terminal_count >= 10
                    else "early" if terminal_count > 0 or admitted > 0
                    else "waiting"
                )
                strategies.append({
                    **{
                        key: policy.get(key)
                        for key in compact_policy_keys if key in policy
                    },
                    "arm_id": policy_arm_id,
                    "forward_started_at": forward_started_at,
                    "forward_age_seconds": forward_age_seconds,
                    "eligible_opportunity_count": admitted + rejected,
                    "maturity": maturity,
                    "account": account,
                    "curve": curve,
                })

            open_filter = (
                "p.status<>'ineligible' AND p.arm_id=?"
                if arm_id else "p.status='open'"
            )
            open_values: tuple[Any, ...] = (
                (active_version, arm_id, self.LIVE_OPEN_POSITION_LIMIT)
                if arm_id else (active_version, self.LIVE_OPEN_POSITION_LIMIT)
            )
            open_rows = self._rows(
                connection,
                "SELECT p.arm_id,p.shadow_cohort_id,p.token_id,p.stake_usd,"
                "p.amount_raw,p.initial_amount_raw,p.entry_signal_price_usd,"
                "p.entry_execution_price_usd,"
                "p.allocated_cost_usd,p.realized_pnl_usd,"
                "p.status,p.opened_at,p.closed_at,p.close_reason,p.last_evaluated_at,"
                "m.pair_address,m.provider AS market_provider,m.price_usd,m.liquidity_usd,"
                "m.status AS market_status,m.consecutive_misses,"
                "m.observed_at AS market_observed_at,"
                "m.recorded_at AS market_recorded_at,m.last_success_at "
                "FROM chain_meme_trader_positions p LEFT JOIN "
                "chain_meme_trader_market_marks m ON m.token_id=p.token_id "
                f"WHERE p.definition_version=? AND {open_filter} "
                "ORDER BY p.opened_at DESC LIMIT ?",
                open_values,
            )
            slippage = int(definition.get("slippage_bps") or 400) / 10_000.0
            open_positions: list[dict[str, Any]] = []
            for row in open_rows:
                position_key = (
                    str(row["arm_id"]), int(row["shadow_cohort_id"]),
                )
                if position_key in contaminated_positions:
                    continue
                correction = corrections_by_position.get(position_key)
                if correction is not None:
                    if str(correction["replacement_outcome"]) != "UNRESOLVED":
                        continue
                    row["realized_pnl_usd"] = (
                        float(row.get("realized_pnl_usd") or 0.0)
                        + float(correction["realized_adjustment_usd"] or 0.0)
                    )
                elif str(row.get("status")) != "open":
                    continue
                market_at = row.get("last_success_at") or row.get("market_recorded_at")
                market_age = (
                    (current - parse_time(market_at)).total_seconds()
                    if market_at else None
                )
                observed_age = (
                    (current - parse_time(row["market_observed_at"])).total_seconds()
                    if row.get("market_observed_at") else None
                )
                fresh_market = bool(
                    row.get("market_status") == "VISIBLE"
                    and row.get("pair_address")
                    and float(row.get("price_usd") or 0.0) > 0.0
                    and (
                        row.get("liquidity_usd") is None
                        or float(row["liquidity_usd"]) >= 0.0
                    )
                    and market_age is not None
                    and 0.0 <= market_age <= 15.0
                    and observed_age is not None
                    and 0.0 <= observed_age <= 15.0
                )
                entry_price = float(
                    row.get("entry_execution_price_usd")
                    or row.get("entry_signal_price_usd")
                    or 0.0
                )
                initial_raw = int(row.get("initial_amount_raw") or row.get("amount_raw") or 0)
                remaining_raw = int(row.get("amount_raw") or 0)
                remaining_fraction = (
                    max(0.0, min(1.0, remaining_raw / initial_raw))
                    if initial_raw > 0 else 0.0
                )
                remaining_cost = max(
                    0.0,
                    float(row.get("stake_usd") or 0.0)
                    - float(row.get("allocated_cost_usd") or 0.0),
                )
                indicative_value = None
                if fresh_market and entry_price > 0.0 and initial_raw > 0:
                    liquidity = row.get("liquidity_usd")
                    if liquidity is not None and float(liquidity) < 1.0:
                        indicative_value = 0.0
                    else:
                        candidate_value = max(
                            0.0,
                            float(row.get("stake_usd") or 0.0)
                            * remaining_fraction
                            * float(row.get("price_usd") or 0.0)
                            / entry_price
                            * (1.0 - slippage),
                        )
                        indicative_value = candidate_value
                holding_seconds = (
                    current - parse_time(row["opened_at"])
                ).total_seconds()
                paper_quantity = row.get("paper_quantity_tokens")
                remaining_quantity = row.get("remaining_quantity_tokens")
                if paper_quantity is None:
                    entry_execution_price = float(
                        row.get("entry_execution_price_usd") or 0.0
                    )
                    if entry_execution_price > 0.0:
                        paper_quantity = (
                            float(row.get("stake_usd") or 0.0)
                            / entry_execution_price
                        )
                if remaining_quantity is None and paper_quantity is not None:
                    initial_raw = int(row.get("initial_amount_raw") or 0)
                    if initial_raw > 0:
                        remaining_quantity = (
                            float(paper_quantity)
                            * int(row.get("amount_raw") or 0)
                            / initial_raw
                        )
                open_positions.append({
                    "arm_id": row["arm_id"],
                    "shadow_cohort_id": row["shadow_cohort_id"],
                    "token_id": row["token_id"],
                    "status": "open",
                    "opened_at": row["opened_at"],
                    "holding_seconds": holding_seconds if holding_seconds >= 0.0 else None,
                    "holding_time_status": (
                        "valid" if holding_seconds >= 0.0 else "invalid_future_opened_at"
                    ),
                    "stake_usd": row["stake_usd"],
                    "amount_raw": row["amount_raw"],
                    "paper_quantity_tokens": paper_quantity,
                    "remaining_quantity_tokens": remaining_quantity,
                    "realized_pnl_usd": row["realized_pnl_usd"],
                    "price_usd": row["price_usd"],
                    "liquidity_usd": row["liquidity_usd"],
                    "market_status": row["market_status"],
                    "market_age_seconds": market_age,
                    "market_observed_age_seconds": observed_age,
                    "market_is_fresh": fresh_market,
                    "remaining_cost_usd": remaining_cost,
                    "indicative_value_usd": indicative_value,
                    "indicative_unrealized_pnl_usd": (
                        indicative_value - remaining_cost
                        if indicative_value is not None else None
                    ),
                    "indicative_source": (
                        "dex_pool_below_1_usd_full_loss"
                        if fresh_market and row.get("liquidity_usd") is not None
                        and float(row["liquidity_usd"]) < 1.0
                        else "dex_price_mark_4pct_haircut" if fresh_market else None
                    ),
                    "indicative_price_usd": row["price_usd"],
                    "indicative_liquidity_usd": row["liquidity_usd"],
                    "indicative_market_status": row["market_status"],
                    "indicative_mark_age_seconds": market_age,
                    "indicative_mark_at": market_at,
                    "indicative_sellability": (
                        "DUST_POOL_WRITEOFF"
                        if fresh_market and row.get("liquidity_usd") is not None
                        and float(row["liquidity_usd"]) < 1.0
                        else "MARK_SELLABLE" if fresh_market
                        else "PAIR_MISSING" if row.get("market_status") == "MISSING"
                        else "STALE_MARK" if row.get("market_status") == "VISIBLE"
                        else "AWAITING_MARK"
                    ),
                })
            if arm_id:
                detail = Store.chain_meme_trader_summary_from_connection(
                    connection,
                    trade_limit=100,
                    curve_limit=self.LIVE_DETAIL_CURVE_POINTS,
                    arm_id=arm_id,
                )
                detail_strategy = next(iter(detail.get("strategies") or []), None)
                if detail_strategy is not None:
                    strategies = [
                        ({
                            **strategy,
                            "positions": detail_strategy.get("positions") or [],
                            "trades": detail_strategy.get("trades") or [],
                        }
                         if str(strategy.get("arm_id") or "") == arm_id else strategy)
                        for strategy in strategies
                    ]
            pending_marks = connection.execute(
                "SELECT COUNT(*) FROM chain_meme_trader_marks WHERE definition_version=? "
                "AND status IN ('pending','retry','quoting')", (active_version,),
            ).fetchone()[0]
            held_monitor = connection.execute(
                "SELECT COUNT(*) AS state_count,"
                "SUM(CASE WHEN s.risk_state='HEALTHY' THEN 1 ELSE 0 END) AS healthy_count,"
                "SUM(CASE WHEN s.risk_state='ALERT' THEN 1 ELSE 0 END) AS alert_count,"
                "MAX(s.observed_at) AS latest_observed_at "
                "FROM onchain_held_account_states s "
                "JOIN onchain_held_account_targets t ON t.id=s.target_id "
                "WHERE t.monitor_version=? AND t.position_definition_version=?",
                (Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION, active_version),
            ).fetchone()
            recent_decisions = self._rows(
                connection,
                "SELECT arm_id,shadow_cohort_id,token_id,status,reason,decided_at "
                "FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
                "ORDER BY id DESC LIMIT 30",
                (active_version,),
            )
            recent_intents = self._rows(
                connection,
                "SELECT id,arm_id,shadow_cohort_id,token_id,side,status,reason,"
                "created_at,next_attempt_at,completed_at FROM chain_meme_trader_order_intents "
                "WHERE definition_version=? ORDER BY id DESC LIMIT 30",
                (active_version,),
            )
            recent_attempts = self._rows(
                connection,
                "SELECT a.id,a.side,a.shadow_cohort_id,a.adapter,a.input_amount_raw,"
                "a.intent_ids_json,a.requested_at,r.terminal_status,r.validity_status,"
                "r.completed_at FROM chain_meme_trader_execution_attempts a "
                "LEFT JOIN chain_meme_trader_execution_results r ON r.attempt_id=a.id "
                "WHERE a.definition_version=? ORDER BY a.id DESC LIMIT 30",
                (active_version,),
            )
            recent_fills = self._rows(
                connection,
                "SELECT id,arm_id,shadow_cohort_id,token_id,side,input_amount_raw,"
                "output_amount_raw,gross_usd,adapter,filled_at "
                "FROM chain_meme_trader_fills WHERE definition_version=? "
                "ORDER BY id DESC LIMIT 30",
                (active_version,),
            )
            intent_counts = {
                str(row["status"]): int(row["count"])
                for row in connection.execute(
                    "SELECT status,COUNT(*) AS count FROM chain_meme_trader_order_intents "
                    "WHERE definition_version=? GROUP BY status",
                    (active_version,),
                )
            }
            oldest_ready_buy = connection.execute(
                "SELECT MIN(created_at) AS created_at FROM chain_meme_trader_order_intents "
                "WHERE definition_version=? AND side='BUY' AND status IN ('ready','retry')",
                (active_version,),
            ).fetchone()
            zero_attempt_counts = connection.execute(
                "SELECT "
                "SUM(CASE WHEN i.status IN ('ready','retry') THEN 1 ELSE 0 END) AS waiting,"
                "SUM(CASE WHEN i.status='failed' THEN 1 ELSE 0 END) AS failed "
                "FROM chain_meme_trader_order_intents i "
                "WHERE i.definition_version=? AND i.side='BUY' AND NOT EXISTS ("
                "SELECT 1 FROM chain_meme_trader_execution_attempts a,"
                "json_each(a.intent_ids_json) j WHERE a.definition_version=i.definition_version "
                "AND CAST(j.value AS INTEGER)=i.id)",
                (active_version,),
            ).fetchone()
            execution_capacity = {
                "ready_buy_count": int(intent_counts.get("ready", 0))
                + int(intent_counts.get("retry", 0)),
                "oldest_ready_buy_age_seconds": (
                    max(
                        0.0,
                        (current - parse_time(oldest_ready_buy["created_at"])).total_seconds(),
                    )
                    if oldest_ready_buy and oldest_ready_buy["created_at"] else None
                ),
                "zero_attempt_waiting_buy_count": int(zero_attempt_counts["waiting"] or 0),
                "zero_attempt_failed_buy_count": int(zero_attempt_counts["failed"] or 0),
                "buy_queue_delay_p95_seconds": None,
                "signal_to_execution_sla_seconds": float(
                    definition.get("max_signal_to_execution_start_seconds", 45.0)
                ),
                "emergency_sell_preempts": True,
            }
            health = self._rows(
                connection,
                "SELECT source,last_ok_at,last_item_at,last_error_at,last_error "
                "FROM source_health WHERE source IN ("
                "'chain-meme-trader','pumpportal','dexscreener_discovery',"
                "'multichain_meme_data',"
                "'chain-meme-market-marks') ORDER BY source",
            )
            for item in health:
                health_at = item.get("last_item_at") or item.get("last_ok_at")
                health_age = (
                    (current - parse_time(health_at)).total_seconds()
                    if health_at else None
                )
                item["age_seconds"] = (
                    health_age if health_age is not None and health_age >= 0.0 else None
                )
            recent_activity = self._rows(
                connection,
                "SELECT id,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
                "realized_pnl_usd,reason,created_at FROM chain_meme_trader_trades "
                "WHERE definition_version=? ORDER BY id DESC LIMIT 30",
                (active_version,),
            )
            effective_recent_activity = []
            for item in recent_activity:
                key = (str(item["arm_id"]), int(item["shadow_cohort_id"]))
                if key in contaminated_positions:
                    continue
                correction = corrections_by_trade.get(int(item["id"]))
                if correction is not None:
                    outcome = str(correction["replacement_outcome"])
                    item.update({
                        "side": outcome,
                        "gross_usd": (
                            float(correction["replacement_gross_usd"] or 0.0)
                            if outcome == "SELL" else 0.0
                        ),
                        "realized_pnl_usd": (
                            float(item.get("realized_pnl_usd") or 0.0)
                            + float(correction["realized_adjustment_usd"] or 0.0)
                        ),
                        "reason": str(correction["reason"]),
                    })
                effective_recent_activity.append(item)
            exit_queue = self._rows(
                connection,
                "SELECT m.id,m.arm_id,m.shadow_cohort_id,p.token_id,m.action,m.reason,"
                "m.status,m.recorded_at FROM chain_meme_trader_marks m JOIN "
                "chain_meme_trader_positions p ON p.definition_version=m.definition_version "
                "AND p.arm_id=m.arm_id AND p.shadow_cohort_id=m.shadow_cohort_id "
                "WHERE m.definition_version=? ORDER BY m.id DESC LIMIT 30",
                (active_version,),
            )
            recent_risk = self._rows(
                connection,
                "SELECT shadow_cohort_id,token_id,risk_state,risk_reason,observed_at "
                "FROM onchain_held_account_risk_events WHERE monitor_version=? "
                "AND position_definition_version=? ORDER BY id DESC LIMIT 20",
                (Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION, active_version),
            )
            discoveries = self._rows(
                connection,
                "SELECT e.token_id,t.name,t.symbol,t.source,e.role,e.observed_at,e.recorded_at "
                "FROM token_discovery_exposures e LEFT JOIN tokens t ON t.token_id=e.token_id "
                "WHERE e.chain IN ('solana','bsc','robinhood') "
                "ORDER BY e.id DESC LIMIT 20",
            )
            discovery_rounds = self._rows(
                connection,
                "SELECT provider,surface,status,returned_count,exposed_token_count,error_type,"
                "started_at,completed_at FROM token_discovery_rounds "
                "WHERE chain_scope IN ("
                "'solana','bsc','robinhood','bsc,robinhood,solana') "
                "ORDER BY id DESC LIMIT 12",
            )
            error_summary = self._error_summary_from_connection(connection)
            wal_path = Path(f"{self.database}-wal")
            disk = shutil.disk_usage(self.database.parent)
            storage = {
                "database_bytes": self.database.stat().st_size,
                "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
                "free_bytes": disk.free,
                "total_bytes": disk.total,
            }
        return {
            "status": "running",
            "version": active_version,
            "generated_at": current_iso,
            "system": {
                **base_system,
                "latest_account_snapshot_at": latest_snapshot_at,
                "notional_usd": float(definition.get("policy_notional_usd", 20.0)),
                "slippage_bps": int(definition.get("slippage_bps", 400)),
                "extra_fee_usd": float(
                    definition.get("additional_fee_usd_each_fill", 0.0)
                ),
                "capital_model": capital_model,
                "open_position_count": effective_open_position_count,
                "unique_held_token_count": len(effective_open_token_ids),
                "pending_exit_quotes": int(pending_marks or 0),
                "held_account_states": int(held_monitor["state_count"] or 0),
                "held_account_healthy": int(held_monitor["healthy_count"] or 0),
                "held_account_alerts": int(held_monitor["alert_count"] or 0),
                "held_account_latest_at": held_monitor["latest_observed_at"],
                "storage": storage,
            },
            "strategies": strategies,
            "source_health": health,
            "recent_activity": effective_recent_activity,
            "recent_decisions": recent_decisions,
            "recent_risk": recent_risk,
            "discovery": {
                "rounds": discovery_rounds,
                "tokens": discoveries,
                "latest_at": discoveries[0].get("observed_at") if discoveries else None,
            },
            "trading": {
                "intents": recent_intents,
                "attempts": recent_attempts,
                "fills": recent_fills,
                "intent_counts": intent_counts,
                "execution_capacity": execution_capacity,
                "exit_queue": exit_queue,
            },
            "error_summary": error_summary,
            "open_positions": open_positions,
            **({"requested_arm_id": arm_id} if arm_id else {}),
        }

    def _state_uncached(self, *, arm_id: str | None = None) -> dict[str, Any]:
        current = utcnow()
        with self._connect() as connection:
            summary = Store.chain_meme_trader_summary_from_connection(
                connection,
                trade_limit=200,
                curve_limit=240,
                arm_id=arm_id,
            )
            active_version = str(summary.get("version") or Store.CHAIN_MEME_TRADER_VERSION)
            exit_challenger = (
                Store.chain_meme_trader_executable_decay_summary_from_connection(connection)
            )
            health = self._rows(
                connection,
                "SELECT * FROM source_health WHERE source IN ("
                "'chain-meme-trader','pumpportal','dexscreener_discovery',"
                "'onchain_only_jupiter_quote','solana-held-accounts',"
                "'chain-meme-postbuy-research','chain-meme-market-marks',"
                "'multichain_meme_data') "
                "ORDER BY source",
            )
            if bool(self.config.get("chain_meme_trader_only_enabled", False)):
                disabled_by_mode = {
                    "onchain_only_jupiter_quote", "solana-held-accounts",
                    "chain-meme-postbuy-research",
                }
                for row in health:
                    row["mode_status"] = (
                        "DISABLED_BY_MODE"
                        if str(row.get("source")) in disabled_by_mode else "ENABLED"
                    )
            else:
                for row in health:
                    row["mode_status"] = "ENABLED"
            heartbeat = next(
                (row for row in health if row.get("source") == "chain-meme-trader"),
                None,
            )
            heartbeat_at = (
                heartbeat.get("last_item_at") or heartbeat.get("last_ok_at")
                if heartbeat else None
            )
            age_seconds = (
                (current - parse_time(heartbeat_at)).total_seconds()
                if heartbeat_at else None
            )
            if age_seconds is not None and age_seconds < 0.0:
                age_seconds = None
            recent_activity = self._rows(
                connection,
                "SELECT id,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
                "realized_pnl_usd,reason,created_at FROM chain_meme_trader_trades "
                "WHERE definition_version=? ORDER BY id DESC LIMIT 80",
                (active_version,),
            )
            active_corrections = {
                int(row["source_trade_id"]): row
                for row in (
                    Store._chain_meme_trader_market_fill_corrections_from_connection(
                        connection, active_version,
                    )
                )
            }
            active_contaminations = {
                (str(row["arm_id"]), int(row["shadow_cohort_id"]))
                for row in (
                    Store._chain_meme_trader_accounting_contaminations_from_connection(
                        connection, active_version,
                    )
                )
            }
            effective_recent_activity = []
            for item in recent_activity:
                position_key = (
                    str(item["arm_id"]), int(item["shadow_cohort_id"]),
                )
                if position_key in active_contaminations:
                    continue
                correction = active_corrections.get(int(item["id"]))
                if correction is not None:
                    outcome = str(correction["replacement_outcome"])
                    item.update({
                        "side": outcome,
                        "gross_usd": (
                            float(correction["replacement_gross_usd"] or 0.0)
                            if outcome == "SELL" else 0.0
                        ),
                        "realized_pnl_usd": (
                            float(item.get("realized_pnl_usd") or 0.0)
                            + float(correction["realized_adjustment_usd"] or 0.0)
                        ),
                        "reason": str(correction["reason"]),
                        "created_at": (
                            correction.get("replacement_observed_at")
                            or item["created_at"]
                        ),
                    })
                effective_recent_activity.append(item)
            recent_activity = effective_recent_activity
            recent_decisions = self._rows(
                connection,
                "SELECT arm_id,shadow_cohort_id,token_id,status,reason,decided_at "
                "FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
                "ORDER BY id DESC LIMIT 80",
                (active_version,),
            )
            recent_intents = self._rows(
                connection,
                "SELECT id,arm_id,shadow_cohort_id,token_id,side,status,reason,"
                "created_at,next_attempt_at,completed_at FROM chain_meme_trader_order_intents "
                "WHERE definition_version=? ORDER BY id DESC LIMIT 120",
                (active_version,),
            )
            recent_attempts = self._rows(
                connection,
                "SELECT a.id,a.side,a.shadow_cohort_id,a.adapter,a.input_amount_raw,"
                "a.intent_ids_json,a.requested_at,r.terminal_status,r.validity_status,"
                "r.completed_at FROM chain_meme_trader_execution_attempts a "
                "LEFT JOIN chain_meme_trader_execution_results r ON r.attempt_id=a.id "
                "WHERE a.definition_version=? ORDER BY a.id DESC LIMIT 80",
                (active_version,),
            )
            recent_fills = self._rows(
                connection,
                "SELECT id,arm_id,shadow_cohort_id,token_id,side,input_amount_raw,"
                "output_amount_raw,gross_usd,adapter,filled_at "
                "FROM chain_meme_trader_fills WHERE definition_version=? "
                "ORDER BY id DESC LIMIT 120",
                (active_version,),
            )
            if active_version in {
                Store.CHAIN_MEME_TRADER_V11_VERSION,
                Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            }:
                recent_fills.extend(self._rows(
                    connection,
                    "SELECT f.id,('entry:' || c.entry_family) AS arm_id,"
                    "f.entry_cohort_id AS shadow_cohort_id,f.token_id,'BUY' AS side,"
                    "f.input_usdc_raw AS input_amount_raw,"
                    "f.output_token_raw AS output_amount_raw,20.0 AS gross_usd,"
                    "'jupiter_quote_minimum_output_paper/v1' AS adapter,f.filled_at "
                    "FROM chain_meme_trader_v6_entry_fills f "
                    "JOIN chain_meme_trader_v6_cohorts c ON c.id=f.entry_cohort_id "
                    "WHERE f.definition_version=? ORDER BY f.id DESC LIMIT 120",
                    (active_version,),
                ))
                recent_fills.sort(key=lambda row: str(row.get("filled_at") or ""), reverse=True)
                recent_fills = recent_fills[:120]
            recent_participant_outcomes = (
                self._rows(
                    connection,
                    "SELECT shadow_cohort_id,arm_id,outcome,available_cash_usd,recorded_at "
                    "FROM chain_meme_trader_entry_participant_outcomes "
                    "WHERE definition_version=? ORDER BY id DESC LIMIT 120",
                    (active_version,),
                )
                if "chain_meme_trader_entry_participant_outcomes" in {
                    str(row[0]) for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                else []
            )
            intent_counts = {
                str(row["status"]): int(row["count"])
                for row in connection.execute(
                    "SELECT status,COUNT(*) AS count FROM chain_meme_trader_order_intents "
                    "WHERE definition_version=? GROUP BY status",
                    (active_version,),
                )
            }
            oldest_ready_buy = connection.execute(
                "SELECT MIN(created_at) AS created_at FROM chain_meme_trader_order_intents "
                "WHERE definition_version=? AND side='BUY' AND status IN ('ready','retry')",
                (active_version,),
            ).fetchone()
            zero_attempt_counts = connection.execute(
                "SELECT "
                "SUM(CASE WHEN i.status IN ('ready','retry') THEN 1 ELSE 0 END) AS waiting," 
                "SUM(CASE WHEN i.status='failed' THEN 1 ELSE 0 END) AS failed "
                "FROM chain_meme_trader_order_intents i "
                "WHERE i.definition_version=? AND i.side='BUY' AND NOT EXISTS ("
                "SELECT 1 FROM chain_meme_trader_execution_attempts a,"
                "json_each(a.intent_ids_json) j WHERE a.definition_version=i.definition_version "
                "AND CAST(j.value AS INTEGER)=i.id)",
                (active_version,),
            ).fetchone()
            queue_delays = sorted(
                max(0.0, float(row["queue_delay_seconds"] or 0.0))
                for row in connection.execute(
                    "SELECT a.id,(julianday(a.requested_at)-julianday(MIN(i.created_at)))*86400.0 "
                    "AS queue_delay_seconds FROM chain_meme_trader_execution_attempts a,"
                    "json_each(a.intent_ids_json) j JOIN chain_meme_trader_order_intents i "
                    "ON i.id=CAST(j.value AS INTEGER) WHERE a.definition_version=? "
                    "AND a.side='BUY' GROUP BY a.id ORDER BY a.id DESC LIMIT 500",
                    (active_version,),
                )
            )
            queue_percentile = lambda fraction: (
                queue_delays[round((len(queue_delays) - 1) * fraction)]
                if queue_delays else None
            )
            execution_capacity = {
                "ready_buy_count": int(intent_counts.get("ready", 0))
                + int(intent_counts.get("retry", 0)),
                "oldest_ready_buy_age_seconds": (
                    max(
                        0.0,
                        (current - parse_time(oldest_ready_buy["created_at"])).total_seconds(),
                    )
                    if oldest_ready_buy and oldest_ready_buy["created_at"] else None
                ),
                "zero_attempt_waiting_buy_count": int(zero_attempt_counts["waiting"] or 0),
                "zero_attempt_failed_buy_count": int(zero_attempt_counts["failed"] or 0),
                "buy_queue_delay_p50_seconds": queue_percentile(0.50),
                "buy_queue_delay_p95_seconds": queue_percentile(0.95),
                "signal_to_execution_sla_seconds": float(
                    summary.get("definition", {}).get(
                        "max_signal_to_execution_start_seconds", 45.0
                    )
                ),
                "normal_schedule": "BUY,BUY,VALUATION",
                "emergency_sell_preempts": True,
            }
            exit_queue = self._rows(
                connection,
                "SELECT m.id,m.arm_id,m.shadow_cohort_id,p.token_id,p.status AS position_status,"
                "m.action,m.reason,m.sell_amount_raw,m.attempt_count,m.next_attempt_at,"
                "m.status,m.recorded_at FROM chain_meme_trader_marks m "
                "JOIN chain_meme_trader_positions p ON p.definition_version=m.definition_version "
                "AND p.arm_id=m.arm_id AND p.shadow_cohort_id=m.shadow_cohort_id "
                "WHERE m.definition_version=? ORDER BY m.id DESC LIMIT 200",
                (active_version,),
            )
            recent_risk = self._rows(
                connection,
                "SELECT shadow_cohort_id,token_id,risk_state,risk_reason,observed_at "
                "FROM onchain_held_account_risk_events WHERE monitor_version=? "
                "AND position_definition_version=? ORDER BY id DESC LIMIT 40",
                (Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION, active_version),
            )
            discovery_rounds = self._rows(
                connection,
                "SELECT provider,surface,status,returned_count,exposed_token_count,"
                "first_local_discovery_count,new_token_count,error_type,started_at,completed_at "
                "FROM token_discovery_rounds WHERE chain_scope IN ("
                "'solana','bsc','robinhood','bsc,robinhood,solana') "
                "ORDER BY id DESC LIMIT 30",
            )
            discoveries = self._rows(
                connection,
                "SELECT e.token_id,t.name,t.symbol,t.source,e.role,e.first_local_discovery,"
                "e.new_token,e.snapshot_count,e.no_pair,e.observed_at,e.recorded_at "
                "FROM token_discovery_exposures e LEFT JOIN tokens t ON t.token_id=e.token_id "
                "WHERE e.chain IN ('solana','bsc','robinhood') "
                "ORDER BY e.id DESC LIMIT 40",
            )
            versions = []
            for row in connection.execute(
                "SELECT * FROM chain_meme_trader_registrations ORDER BY registered_at"
            ).fetchall():
                item = dict(row)
                definition_version = str(row["definition_version"])
                decisions = connection.execute(
                    "SELECT COUNT(*) FROM chain_meme_trader_entry_decisions "
                    "WHERE definition_version=?", (definition_version,),
                ).fetchone()[0]
                positions = connection.execute(
                    "SELECT COUNT(*),SUM(status='closed'),SUM(status='written_off') "
                    "FROM chain_meme_trader_positions WHERE definition_version=?",
                    (definition_version,),
                ).fetchone()
                item["definition"] = (
                    Store.chain_meme_trader_effective_definition_from_connection(
                        connection, definition_version, row["definition_json"],
                    )
                    if definition_version == active_version
                    else Store._json_object(row["definition_json"])
                )
                item.pop("definition_json", None)
                item["decision_count"] = int(decisions or 0)
                item["position_count"] = int(positions[0] or 0)
                item["closed_count"] = int(positions[1] or 0)
                item["written_off_count"] = int(positions[2] or 0)
                item["current"] = definition_version == active_version
                versions.append(item)
            correction_by_version: dict[
                str, dict[tuple[str, int], dict[str, Any]]
            ] = {}
            correction_trade_by_version: dict[str, dict[int, dict[str, Any]]] = {}
            contamination_by_version: dict[str, set[tuple[str, int]]] = {}
            for version_item in versions:
                definition_version = str(version_item["definition_version"])
                version_corrections = (
                    Store._chain_meme_trader_market_fill_corrections_from_connection(
                        connection, definition_version,
                    )
                )
                correction_by_version[definition_version] = {
                    (str(row["arm_id"]), int(row["shadow_cohort_id"])): row
                    for row in version_corrections
                }
                correction_trade_by_version[definition_version] = {
                    int(row["source_trade_id"]): row for row in version_corrections
                }
                contamination_by_version[definition_version] = {
                    (str(row["arm_id"]), int(row["shadow_cohort_id"]))
                    for row in (
                        Store._chain_meme_trader_accounting_contaminations_from_connection(
                            connection, definition_version,
                        )
                    )
                }
            position_stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(
                lambda: {
                    "position_count": 0, "open_count": 0, "closed_count": 0,
                    "written_off_count": 0, "realized_pnl_usd": 0.0,
                    "win_count": 0,
                }
            )
            terminal_pnls: dict[tuple[str, str], list[float]] = defaultdict(list)
            terminal_blocks: dict[tuple[str, str], set[str]] = defaultdict(set)
            for row in connection.execute(
                "SELECT definition_version,arm_id,shadow_cohort_id,status,"
                "realized_pnl_usd,closed_at FROM chain_meme_trader_positions "
                "WHERE status<>'ineligible'"
            ).fetchall():
                definition_version = str(row["definition_version"])
                arm = str(row["arm_id"])
                position_key = (arm, int(row["shadow_cohort_id"]))
                if position_key in contamination_by_version.get(definition_version, set()):
                    continue
                key = (definition_version, arm)
                correction = correction_by_version.get(definition_version, {}).get(
                    position_key
                )
                effective_status = str(row["status"])
                effective_pnl = float(row["realized_pnl_usd"] or 0.0)
                effective_closed_at = row["closed_at"]
                if correction is not None:
                    effective_status = {
                        "SELL": "closed", "WRITEOFF": "written_off",
                        "UNRESOLVED": "open",
                    }[str(correction["replacement_outcome"])]
                    effective_pnl += float(
                        correction["realized_adjustment_usd"] or 0.0
                    )
                    effective_closed_at = (
                        correction.get("replacement_observed_at")
                        or effective_closed_at
                    )
                stats = position_stats[key]
                stats["position_count"] += 1
                stats[f"{effective_status}_count"] += 1
                if effective_status in {"closed", "written_off"}:
                    stats["realized_pnl_usd"] += effective_pnl
                    stats["win_count"] += int(effective_pnl > 0.0)
                    terminal_pnls[key].append(effective_pnl)
                    if effective_closed_at:
                        terminal_blocks[key].add(str(effective_closed_at)[:10])
            trade_cash_flow: dict[tuple[str, str], float] = defaultdict(float)
            for row in connection.execute(
                "SELECT id,definition_version,arm_id,shadow_cohort_id,"
                "net_cash_flow_usd FROM chain_meme_trader_trades"
            ).fetchall():
                definition_version = str(row["definition_version"])
                arm = str(row["arm_id"])
                position_key = (arm, int(row["shadow_cohort_id"]))
                if position_key in contamination_by_version.get(definition_version, set()):
                    continue
                correction = correction_trade_by_version.get(definition_version, {}).get(
                    int(row["id"])
                )
                trade_cash_flow[(definition_version, arm)] += (
                    float(row["net_cash_flow_usd"] or 0.0)
                    + (
                        float(correction["cash_adjustment_usd"] or 0.0)
                        if correction is not None else 0.0
                    )
                )
            decision_stats = {
                (str(row["definition_version"]), str(row["arm_id"])): dict(row)
                for row in connection.execute(
                    "SELECT definition_version,arm_id,"
                    "SUM(CASE WHEN status='admitted' THEN 1 ELSE 0 END) AS admitted,"
                    "SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected "
                    "FROM chain_meme_trader_entry_decisions GROUP BY definition_version,arm_id"
                ).fetchall()
            }
            stop_records = {
                str(row["definition_version"]): dict(row)
                for row in connection.execute(
                    "SELECT definition_version,stopped_at,source_frontier,reason "
                    "FROM chain_meme_trader_primary_stops"
                ).fetchall()
            }
            stop_reasons = {
                version: str(row["reason"]) for version, row in stop_records.items()
            }
            strategy_registry: list[dict[str, Any]] = []
            for version_item in versions:
                definition_version = str(version_item["definition_version"])
                definition = version_item.get("definition") or {}
                if definition_version.startswith("chain-meme-trader/v2-"):
                    lineage_role = "BASELINE_12"
                elif definition_version.startswith((
                    "chain-meme-trader/v3-", "chain-meme-trader/v4-",
                    "chain-meme-trader/v5-",
                )):
                    lineage_role = "BASELINE_LINEAGE"
                elif "entry3-exit4" in definition_version:
                    lineage_role = "CHALLENGER"
                else:
                    lineage_role = "SUPERSEDED_PROTOTYPE"
                for policy in definition.get("policies", []):
                    arm_id = str(policy.get("arm_id") or "")
                    key = (definition_version, arm_id)
                    behavior = Store.chain_meme_trader_decision_behavior(
                        policy, definition_version=definition_version,
                    )
                    behavior_hash = Store.chain_meme_trader_behavior_hash(
                        policy, definition_version=definition_version,
                    )
                    family_hash = hashlib.sha256(json.dumps({
                        "entry_family": behavior.get("entry_family"),
                        "exit_family": policy.get("exit_family") or policy.get("exit_mode"),
                    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
                    positions = position_stats.get(key, {})
                    closed_count = int(positions.get("closed_count") or 0)
                    written_off_count = int(positions.get("written_off_count") or 0)
                    terminal_count = closed_count + written_off_count
                    realized_pnl = float(positions.get("realized_pnl_usd") or 0.0)
                    pnl_values = sorted(terminal_pnls.get(key, []))
                    median_pnl = (
                        pnl_values[len(pnl_values) // 2]
                        if len(pnl_values) % 2 else (
                            (pnl_values[len(pnl_values) // 2 - 1] + pnl_values[len(pnl_values) // 2]) / 2
                            if pnl_values else None
                        )
                    )
                    trim = int(len(pnl_values) * 0.10)
                    trimmed_values = (
                        pnl_values[trim:len(pnl_values) - trim]
                        if trim and len(pnl_values) > 2 * trim else pnl_values
                    )
                    trimmed_mean = (
                        sum(trimmed_values) / len(trimmed_values)
                        if trimmed_values else None
                    )
                    positive_total = sum(value for value in pnl_values if value > 0.0)
                    best_win_concentration = (
                        max(pnl_values) / positive_total
                        if positive_total > 0.0 and pnl_values else None
                    )
                    rank_eligible = terminal_count > 0
                    stop_reason = stop_reasons.get(definition_version, "")
                    stop_lower = stop_reason.lower()
                    fidelity_status = str(
                        policy.get("fidelity_status") or "UNCLASSIFIED"
                    )
                    forward_enabled = bool(policy.get("forward_enabled", True))
                    if definition_version == active_version and not forward_enabled:
                        operating_status = "COVERAGE_UNAVAILABLE"
                    elif definition_version == active_version:
                        operating_status = "ACTIVE_FORWARD"
                    elif any(word in stop_lower for word in (
                        "invalid", "contaminated", "confounded",
                    )):
                        operating_status = "INVALID_CONTAMINATED"
                    elif any(word in stop_lower for word in (
                        "negative_cash", "scheduler_interference", "bug", "stale_quote",
                    )):
                        operating_status = "RETIRED_ENGINEERING_FAILURE"
                    elif stop_reason:
                        operating_status = "SUPERSEDED_CONTRACT"
                    elif (
                        terminal_count >= 30 and realized_pnl <= 0.0
                        and (median_pnl or 0.0) <= 0.0
                        and (trimmed_mean or 0.0) <= 0.0
                    ):
                        operating_status = "RETIRED_ECONOMIC_FAILURE"
                    elif terminal_count > 0:
                        operating_status = "RETAINED_CANDIDATE"
                    else:
                        operating_status = "OBSERVING_INSUFFICIENT"
                    economic_state = (
                        "UNDERPERFORMING_LEARNING"
                        if definition_version == active_version and terminal_count > 0
                        and realized_pnl <= 0.0 and (median_pnl or 0.0) <= 0.0
                        else "POSITIVE_PROVISIONAL"
                        if terminal_count > 0 and realized_pnl > 0.0
                        else "INSUFFICIENT_EVIDENCE"
                    )
                    strategy_registry.append({
                        "strategy_key": f"{definition_version}:{arm_id}",
                        "behavior_hash": behavior_hash,
                        "family_hash": family_hash,
                        "definition_version": definition_version,
                        "registered_at": (
                            policy.get("forward_started_at")
                            or version_item.get("registered_at")
                        ),
                        "activation_frontier": (
                            policy.get("forward_activation_snapshot_id")
                            if policy.get("forward_activation_snapshot_id") is not None
                            else version_item.get("activation_exploration_buy_trade_id")
                        ),
                        "current": definition_version == active_version,
                        "lineage_role": lineage_role,
                        "arm_id": arm_id,
                        "stage": int(policy.get("stage") or 0),
                        "name": str(policy.get("name") or arm_id),
                        "description": str(policy.get("description") or ""),
                        "entry_family": behavior.get("entry_family"),
                        "exit_family": policy.get("exit_family") or policy.get("exit_mode"),
                        "fidelity_status": fidelity_status,
                        "fidelity_note": str(policy.get("fidelity_note") or ""),
                        "forward_enabled": forward_enabled,
                        "status": operating_status,
                        "economic_state": economic_state,
                        "default_visible": operating_status in {
                            "ACTIVE_FORWARD", "RETAINED_CANDIDATE",
                            "OBSERVING_INSUFFICIENT",
                        },
                        "stop_reason": stop_reason or None,
                        "rank_eligible": rank_eligible,
                        "evidence_status": (
                            "MATURE" if terminal_count >= 30
                            else "PROVISIONAL" if terminal_count > 0 else "NO_TERMINAL_SAMPLE"
                        ),
                        "position_count": int(positions.get("position_count") or 0),
                        "open_count": int(positions.get("open_count") or 0),
                        "closed_count": closed_count,
                        "written_off_count": written_off_count,
                        "terminal_count": terminal_count,
                        "win_count": int(positions.get("win_count") or 0),
                        "realized_pnl_usd": realized_pnl,
                        "realized_pnl_per_terminal_usd": (
                            realized_pnl / terminal_count if terminal_count else None
                        ),
                        "median_terminal_pnl_usd": median_pnl,
                        "trimmed_mean_terminal_pnl_usd": trimmed_mean,
                        "worst_terminal_pnl_usd": pnl_values[0] if pnl_values else None,
                        "best_terminal_pnl_usd": pnl_values[-1] if pnl_values else None,
                        "best_win_concentration": best_win_concentration,
                        "time_block_count": len(terminal_blocks.get(key, set())),
                        "sample_unit": "unique_shadow_cohort_id",
                        "paired_comparison_required": True,
                        "cost_contract": {
                            "notional_usd": float(definition.get("policy_notional_usd", 20.0)),
                            "slippage_bps": int(definition.get("slippage_bps", 400)),
                            "additional_fee_usd_each_fill": float(
                                definition.get("additional_fee_usd_each_fill", 0.0)
                            ),
                        },
                        "net_cash_flow_usd": trade_cash_flow.get(key, 0.0),
                        "admitted": int(decision_stats.get(key, {}).get("admitted") or 0),
                        "rejected": int(decision_stats.get(key, {}).get("rejected") or 0),
                    })
            exact_groups: dict[str, list[dict[str, Any]]] = {}
            for item in strategy_registry:
                exact_groups.setdefault(str(item["behavior_hash"]), []).append(item)
            strategy_groups: list[dict[str, Any]] = []
            for members in exact_groups.values():
                members.sort(
                    key=lambda item: (
                        bool(item["current"]), bool(item["rank_eligible"]),
                        str(item.get("registered_at") or ""),
                    ),
                    reverse=True,
                )
                representative = dict(members[0])
                group_current = any(bool(item["current"]) for item in members)
                # Equivalent accounts are aliases of one decision behaviour, not
                # independent samples.  Display the newest/current representative;
                # keep aggregate history separately for audit only.
                terminal_count = int(representative["terminal_count"])
                realized_pnl = float(representative["realized_pnl_usd"])
                historical_members = [item for item in members if not item["current"]]
                representative.update({
                    "member_count": len(members),
                    "active_member_count": sum(bool(item["current"]) for item in members),
                    "member_strategy_keys": [item["strategy_key"] for item in members],
                    "member_versions": list(dict.fromkeys(
                        str(item["definition_version"]) for item in members
                    )),
                    "current": group_current,
                    "status": representative["status"],
                    "default_visible": representative["status"] in {
                        "ACTIVE_FORWARD", "RETAINED_CANDIDATE",
                        "OBSERVING_INSUFFICIENT",
                    },
                    "terminal_count": terminal_count,
                    "realized_pnl_usd": realized_pnl,
                    "realized_pnl_per_terminal_usd": (
                        realized_pnl / terminal_count if terminal_count else None
                    ),
                    "rank_eligible": terminal_count > 0,
                    "evidence_status": (
                        "MATURE" if terminal_count >= 30
                        else "PROVISIONAL" if terminal_count > 0
                        else "NO_TERMINAL_SAMPLE"
                    ),
                    "historical_terminal_count": sum(
                        int(item["terminal_count"]) for item in historical_members
                    ),
                    "historical_realized_pnl_usd": sum(
                        float(item["realized_pnl_usd"]) for item in historical_members
                    ),
                })
                strategy_groups.append(representative)
            strategy_groups.sort(key=lambda item: (
                not bool(item["current"]), str(item["lineage_role"]),
                int(item["stage"]), str(item["name"]),
            ))
            leaderboard = sorted(
                (
                    item for item in strategy_groups
                    if item["rank_eligible"] and item["status"] not in {
                        "INVALID_CONTAMINATED", "RETIRED_ENGINEERING_FAILURE",
                    }
                ),
                key=lambda item: (
                    float(item["realized_pnl_per_terminal_usd"])
                    if item["realized_pnl_per_terminal_usd"] is not None
                    else float("-inf"),
                    float(item["realized_pnl_usd"]),
                ),
                reverse=True,
            )[:3]
            unique_terminal_by_version = {
                str(row["definition_version"]): int(row["cohort_count"] or 0)
                for row in connection.execute(
                    "SELECT definition_version,COUNT(DISTINCT shadow_cohort_id) AS cohort_count "
                    "FROM chain_meme_trader_positions "
                    "WHERE status IN ('closed','written_off') GROUP BY definition_version"
                ).fetchall()
            }
            failure_tombstones: list[dict[str, Any]] = []
            for version_item in versions:
                definition_version = str(version_item["definition_version"])
                reason = stop_reasons.get(definition_version)
                if not reason:
                    continue
                lower = reason.lower()
                if any(word in lower for word in ("invalid", "contaminated", "confounded")):
                    failure_type = "INVALID_CONTAMINATED"
                    reusable = "策略定义与历史证据保留；污染 epoch 不进入经济排名"
                    prohibited = "禁止把多变量或污染样本当作单变量策略证据"
                elif any(word in lower for word in (
                    "negative_cash", "scheduler_interference", "bug", "stale_quote",
                )):
                    failure_type = "RETIRED_ENGINEERING_FAILURE"
                    reusable = "可复用未受故障影响的策略规则；旧成交结果仅供审计"
                    prohibited = "禁止在修复前沿用旧执行/会计结果"
                else:
                    failure_type = "SUPERSEDED_CONTRACT"
                    reusable = "保留为旧合同基线与谱系节点"
                    prohibited = "禁止把不同执行合同的 PNL 直接合并"
                failure_tombstones.append({
                    "definition_version": definition_version,
                    "failure_type": failure_type,
                    "stopped_at": stop_records[definition_version].get("stopped_at"),
                    "source_frontier": stop_records[definition_version].get(
                        "source_frontier"
                    ),
                    "activation_frontier": version_item.get(
                        "activation_exploration_buy_trade_id"
                    ),
                    "unique_terminal_cohorts": unique_terminal_by_version.get(
                        definition_version, 0
                    ),
                    "reason": reason,
                    "reusable": reusable,
                    "prohibited_pattern": prohibited,
                    "historical_evidence_preserved": True,
                })
            pending_marks = connection.execute(
                "SELECT COUNT(*) FROM chain_meme_trader_marks WHERE definition_version=? "
                "AND status IN ('pending','retry','quoting')",
                (active_version,),
            ).fetchone()[0]
            held_targets = connection.execute(
                "SELECT COUNT(*) FROM onchain_held_account_targets WHERE monitor_version=? "
                "AND position_definition_version=?",
                (Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION, active_version),
            ).fetchone()[0]
            held_monitor = connection.execute(
                "SELECT COUNT(*) AS state_count,"
                "SUM(CASE WHEN s.risk_state='HEALTHY' THEN 1 ELSE 0 END) AS healthy_count,"
                "SUM(CASE WHEN s.risk_state='ALERT' THEN 1 ELSE 0 END) AS alert_count,"
                "MAX(s.observed_at) AS latest_observed_at "
                "FROM onchain_held_account_states s "
                "JOIN onchain_held_account_targets t ON t.id=s.target_id "
                "WHERE t.monitor_version=? AND t.position_definition_version=?",
                (Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION, active_version),
            ).fetchone()
            local_surface = connection.execute(
                "SELECT COUNT(*) AS quote_count,COUNT(DISTINCT shadow_cohort_id) AS cohorts,"
                "SUM(CASE WHEN status IN ('LOCAL_SURFACE_CURRENT','LOCAL_SURFACE_DEGRADED',"
                "'LOCAL_SURFACE_CRITICAL') THEN 1 ELSE 0 END) AS current_count,"
                "MAX(completed_at) AS latest_at FROM chain_meme_trader_local_surface_quotes "
                "WHERE version=? AND definition_version=?",
                (
                    Store.CHAIN_MEME_TRADER_LOCAL_SURFACE_QUOTE_VERSION,
                    active_version,
                ),
            ).fetchone()
            latest_snapshot = connection.execute(
                "SELECT MAX(recorded_at) AS recorded_at FROM "
                "chain_meme_trader_account_snapshots WHERE definition_version=?",
                (active_version,),
            ).fetchone()
            open_position_counts = connection.execute(
                "SELECT COUNT(*) AS open_position_count,"
                "COUNT(DISTINCT token_id) AS unique_held_token_count "
                "FROM chain_meme_trader_positions WHERE definition_version=? "
                "AND status='open'",
                (active_version,),
            ).fetchone()
            postbuy_research = self._rows(
                connection,
                "SELECT c.id,c.shadow_cohort_id,c.token_id,c.status,c.reason_code,"
                "c.eligible_at,c.research_cutoff_at,c.recorded_at,r.terminal_status,"
                "r.completed_at,a.outcome AS admission_outcome,a.reason AS admission_reason,"
                "x.status AS assessment_status FROM chain_meme_trader_postbuy_research_cases c "
                "LEFT JOIN chain_meme_trader_postbuy_research_results r ON r.case_id=c.id "
                "LEFT JOIN token_context_admission_attempts a ON a.id=r.admission_id "
                "LEFT JOIN token_context_assessments x ON x.id=r.assessment_id "
                "WHERE c.research_version=? ORDER BY c.id DESC LIMIT 40",
                (Store.CHAIN_MEME_TRADER_POSTBUY_RESEARCH_VERSION,),
            )
            postbuy_registration = connection.execute(
                "SELECT * FROM chain_meme_trader_postbuy_research_registrations "
                "WHERE research_version=?",
                (Store.CHAIN_MEME_TRADER_POSTBUY_RESEARCH_VERSION,),
            ).fetchone()
            postbuy_counts = {
                "cases": int(connection.execute(
                    "SELECT COUNT(*) FROM chain_meme_trader_postbuy_research_cases "
                    "WHERE research_version=?",
                    (Store.CHAIN_MEME_TRADER_POSTBUY_RESEARCH_VERSION,),
                ).fetchone()[0]),
                "completed": int(connection.execute(
                    "SELECT COUNT(*) FROM chain_meme_trader_postbuy_research_results "
                    "WHERE research_version=?",
                    (Store.CHAIN_MEME_TRADER_POSTBUY_RESEARCH_VERSION,),
                ).fetchone()[0]),
                "coverage_gaps": int(connection.execute(
                    "SELECT COUNT(*) FROM chain_meme_trader_postbuy_research_cases "
                    "WHERE research_version=? AND status='coverage_gap'",
                    (Store.CHAIN_MEME_TRADER_POSTBUY_RESEARCH_VERSION,),
                ).fetchone()[0]),
            }
            reverse_registration = connection.execute(
                "SELECT * FROM chain_meme_trader_immediate_reverseability_registrations "
                "WHERE observer_version=?",
                (Store.CHAIN_MEME_TRADER_IMMEDIATE_REVERSEABILITY_VERSION,),
            ).fetchone()
            reverseability: dict[str, Any] = {
                "version": Store.CHAIN_MEME_TRADER_IMMEDIATE_REVERSEABILITY_VERSION,
                "registered_at": None,
                "eligible_entry_fills": 0,
                "horizons": [],
                "items": [],
                "decision_eligible": False,
                "affects": "none",
            }
            if reverse_registration is not None:
                observer = Store.CHAIN_MEME_TRADER_IMMEDIATE_REVERSEABILITY_VERSION
                version = str(reverse_registration["definition_version"])
                frontier = int(reverse_registration["activation_entry_fill_id"])
                eligible_rows = connection.execute(
                    "SELECT id,filled_at FROM chain_meme_trader_v6_entry_fills "
                    "WHERE definition_version=? AND id>? AND filled_at>=?",
                    (version, frontier, str(reverse_registration["registered_at"])),
                ).fetchall()
                all_outcomes = connection.execute(
                    "SELECT * FROM chain_meme_trader_immediate_reverseability_outcomes "
                    "WHERE observer_version=? ORDER BY id", (observer,),
                ).fetchall()
                horizon_rows = []
                for horizon in Store.CHAIN_MEME_TRADER_IMMEDIATE_REVERSEABILITY_HORIZONS_SECONDS:
                    outcomes = [row for row in all_outcomes if int(row["horizon_seconds"]) == horizon]
                    matured = sum(
                        current >= parse_time(row["filled_at"]) + timedelta(seconds=horizon)
                        for row in eligible_rows
                    )
                    counts: dict[str, int] = {}
                    for row in outcomes:
                        status = str(row["outcome_status"])
                        counts[status] = counts.get(status, 0) + 1
                    ratios = sorted(
                        float(row["minimum_recovery_ratio"])
                        for row in outcomes if row["minimum_recovery_ratio"] is not None
                    )
                    route_delays = sorted(
                        float(row["fill_to_first_route_ms"])
                        for row in outcomes if row["fill_to_first_route_ms"] is not None
                    )
                    median = lambda values: (
                        values[len(values) // 2] if len(values) % 2
                        else (values[len(values) // 2 - 1] + values[len(values) // 2]) / 2
                    ) if values else None
                    horizon_rows.append({
                        "seconds": horizon,
                        "matured": matured,
                        "observed": len(outcomes),
                        "pending": max(0, matured - len(outcomes)),
                        "not_yet_due": max(0, len(eligible_rows) - matured),
                        "coverage_rate": len(outcomes) / matured if matured else None,
                        "counts": counts,
                        "minimum_recovery_ratio_p50": median(ratios),
                        "time_to_first_route_ms_p50": median(route_delays),
                    })
                recent_reverse = []
                for row in reversed(all_outcomes[-80:]):
                    item = dict(row)
                    item["evidence"] = Store._json_object(item.pop("evidence_json", "{}"))
                    recent_reverse.append(item)
                reverseability = {
                    "version": observer,
                    "registered_at": reverse_registration["registered_at"],
                    "activation_entry_fill_id": frontier,
                    "eligible_entry_fills": len(eligible_rows),
                    "horizons": horizon_rows,
                    "items": recent_reverse,
                    "decision_eligible": False,
                    "affects": "none",
                }
            wal_path = Path(f"{self.database}-wal")
            disk = shutil.disk_usage(self.database.parent)
            storage = {
                "database_bytes": self.database.stat().st_size,
                "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
                "free_bytes": disk.free,
                "total_bytes": disk.total,
            }
        open_positions = [
            {
                key: position.get(key) for key in (
                    "arm_id", "shadow_cohort_id", "token_id", "opened_at",
                    "holding_seconds", "stake_usd", "realized_pnl_usd",
                    "paper_quantity_tokens", "remaining_quantity_tokens",
                    "indicative_value_usd", "indicative_unrealized_pnl_usd",
                    "indicative_price_usd", "indicative_liquidity_usd",
                    "indicative_market_status", "indicative_mark_age_seconds",
                )
            }
            for strategy in summary.get("strategies", [])
            for position in strategy.get("positions", [])
            if str(position.get("status")) == "open"
        ]
        leaderboard = []
        for strategy in summary.get("strategies", []):
            account = strategy.get("account") or {}
            total_pnl = account.get("capital_neutral_total_pnl_usd")
            terminal_count = int(account.get("closed_position_count") or 0) + int(
                account.get("written_off_position_count") or 0
            )
            if total_pnl is None or terminal_count <= 0:
                continue
            leaderboard.append({
                "current": True,
                "status": "ACTIVE_FORWARD",
                "definition_version": active_version,
                "arm_id": strategy.get("arm_id"),
                "name": strategy.get("name"),
                "stage": strategy.get("stage"),
                "total_pnl_usd": float(total_pnl),
                "realized_pnl_usd": account.get(
                    "capital_neutral_realized_pnl_usd"
                ),
                "unrealized_pnl_usd": account.get(
                    "capital_neutral_unrealized_pnl_usd"
                ),
                "terminal_count": terminal_count,
                "win_count": int(account.get("win_count") or 0),
                "maturity": strategy.get("maturity"),
                "forward_age_seconds": strategy.get("forward_age_seconds"),
                "rank_metric": "maturity_then_expectancy_then_total_pnl",
            })
        maturity_order = {"waiting": 0, "early": 1, "provisional": 2, "mature": 3}
        leaderboard.sort(
            key=lambda item: (
                maturity_order.get(str(item.get("maturity") or "waiting"), 0),
                int(item["terminal_count"]),
                float(item.get("total_pnl_usd") or float("-inf")),
            ),
            reverse=True,
        )
        leaderboard = leaderboard[:3]
        payload = {
            **summary,
            "generated_at": iso(current),
            "open_positions": open_positions,
            "system": {
                "runtime_status": (
                    "running" if age_seconds is not None and age_seconds <= 30 else "stale"
                ),
                "heartbeat_at": heartbeat_at,
                "heartbeat_age_seconds": age_seconds,
                "latest_account_snapshot_at": (
                    latest_snapshot["recorded_at"] if latest_snapshot else None
                ),
                "refresh_seconds": 5,
                "chain": "Solana / BSC / Robinhood",
                "paper_only": not self.live_enabled,
                "live_locked": not self.live_enabled,
                "locked_by_config": not self.live_enabled,
                "notional_usd": 20.0,
                "slippage_bps": 400,
                "extra_fee_usd": 0.0,
                "capital_model": summary.get("capital_model"),
                "open_position_count": int(
                    open_position_counts["open_position_count"] or 0
                ),
                "unique_held_token_count": int(
                    open_position_counts["unique_held_token_count"] or 0
                ),
                "pending_exit_quotes": int(pending_marks or 0),
                "held_account_targets": int(held_targets or 0),
                "held_account_monitor_version": Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION,
                "held_account_states": int(held_monitor["state_count"] or 0),
                "held_account_healthy": int(held_monitor["healthy_count"] or 0),
                "held_account_alerts": int(held_monitor["alert_count"] or 0),
                "held_account_latest_at": held_monitor["latest_observed_at"],
                "local_surface_quote_version": (
                    Store.CHAIN_MEME_TRADER_LOCAL_SURFACE_QUOTE_VERSION
                ),
                "local_surface_quote_count": int(local_surface["quote_count"] or 0),
                "local_surface_cohorts": int(local_surface["cohorts"] or 0),
                "local_surface_current_count": int(local_surface["current_count"] or 0),
                "local_surface_latest_at": local_surface["latest_at"],
                "paper_adapter": "jupiter-buy-one-shot-sell-dexmark-fallback/v1",
                "paper_adapter_status": "active",
                "live_adapter_status": (
                    "ready_per_wallet_opt_in"
                    if self.live_enabled else "locked_by_config"
                ),
                "execution_kernel": "order-intent-fill/v1",
                "storage": storage,
            },
            "source_health": health,
            "discovery": {
                "rounds": discovery_rounds,
                "tokens": discoveries,
                "latest_at": discoveries[0].get("observed_at") if discoveries else None,
            },
            "versions": versions,
            "strategy_ledger": strategy_groups,
            "strategy_registry": strategy_registry,
            "strategy_groups": strategy_groups,
            "failure_tombstones": failure_tombstones,
            "strategy_registry_stats": {
                "raw_strategy_count": len(strategy_registry),
                "display_strategy_count": len(strategy_groups),
                "family_count": len({item["family_hash"] for item in strategy_registry}),
                "retained_count": sum(
                    1 for item in strategy_groups if item["default_visible"]
                ),
                "retired_count": sum(
                    1 for item in strategy_groups
                    if item["status"] in {
                        "RETIRED_ECONOMIC_FAILURE", "RETIRED_ENGINEERING_FAILURE",
                        "INVALID_CONTAMINATED",
                    }
                ),
                "unscored_count": sum(
                    1 for item in strategy_groups
                    if item["status"] == "OBSERVING_INSUFFICIENT"
                ),
            },
            "leaderboard": leaderboard,
            "postbuy_research": {
                "version": Store.CHAIN_MEME_TRADER_POSTBUY_RESEARCH_VERSION,
                "registered_at": (
                    postbuy_registration["registered_at"]
                    if postbuy_registration is not None else None
                ),
                "activation_buy_fill_id": (
                    int(postbuy_registration["activation_buy_fill_id"])
                    if postbuy_registration is not None else None
                ),
                **postbuy_counts,
                "pending": postbuy_counts["cases"] - postbuy_counts["completed"],
                "items": postbuy_research,
                "affects_trading": False,
            },
            "immediate_reverseability": reverseability,
            "exit_challenger": exit_challenger,
            "recent_activity": recent_activity,
            "recent_decisions": recent_decisions,
            "recent_risk": recent_risk,
            "trading": {
                "intent_counts": intent_counts,
                "execution_capacity": execution_capacity,
                "intents": recent_intents,
                "attempts": recent_attempts,
                "fills": recent_fills,
                "entry_participant_outcomes": recent_participant_outcomes,
                "exit_queue": exit_queue,
            },
        }
        return payload

    def strategy_universe(self) -> dict[str, Any]:
        """Return preserved historical strategies plus current additive strategies."""
        if not self.strategy_universe_path.is_file():
            return {
                "status": "not_generated",
                "families": [],
                "summary": {"behavior_contract_families": 0},
            }
        modified_at = self.strategy_universe_path.stat().st_mtime
        with self._connect() as connection:
            active_row = connection.execute(
                "SELECT definition_version FROM chain_meme_trader_v6_activations "
                "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC LIMIT 1"
            ).fetchone()
            active_version = (
                str(active_row["definition_version"])
                if active_row is not None else Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
            )
            has_additions = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='chain_meme_trader_policy_additions'"
            ).fetchone()
            addition_frontier = int(connection.execute(
                "SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_policy_additions "
                "WHERE definition_version=?",
                (active_version,),
            ).fetchone()[0]) if has_additions is not None else 0
            accounting_frontier = (
                Store._chain_meme_trader_accounting_effective_after_from_connection(
                    connection, active_version,
                )
            )
            result_frontier = int(connection.execute(
                "SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_account_snapshots "
                "WHERE definition_version=?", (active_version,),
            ).fetchone()[0])
            cache_key = (
                modified_at, active_version, addition_frontier,
                accounting_frontier, result_frontier,
            )
            with self._cache_lock:
                if self._universe_cache is not None and self._universe_cache[0] == cache_key:
                    return self._universe_cache[1]
            definition_row = connection.execute(
                "SELECT definition_json FROM chain_meme_trader_registrations "
                "WHERE definition_version=?", (active_version,),
            ).fetchone()
            active_definition = (
                Store.chain_meme_trader_effective_definition_from_connection(
                    connection, active_version, definition_row["definition_json"],
                )
                if definition_row is not None else {}
            )
        active_results = {
            str(item.get("arm_id") or ""): item
            for item in self.state(compact=True).get("strategies", [])
        }
        report = json.loads(self.strategy_universe_path.read_text(encoding="utf-8"))
        instances_by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in report.get("instances", []):
            instances_by_hash[str(item.get("behavior_contract_hash") or "")].append({
                key: item.get(key) for key in (
                    "strategy_key", "version", "version_number", "arm_id", "stage",
                    "name", "entry_family", "exit_family", "registered_at", "stopped_at",
                    "stop_reason", "activation_frontier", "samples", "coverage", "outcomes",
                    "causal_data_validity", "comparability", "evidence_grade",
                    "classification", "classification_reason", "reusable_component",
                    "execution_contract", "frozen_policy",
                )
            })
        active_policies = active_definition.get("policies", [])
        active_policy_by_canonical = {
            str(policy.get("canonical_id") or ""): policy
            for policy in active_policies if policy.get("canonical_id")
        }
        families = []
        for display_index, family in enumerate(report.get("behavior_families", []), 1):
            fingerprint = str(family.get("behavior_contract_hash") or "")
            members = sorted(
                instances_by_hash.get(fingerprint, []),
                key=lambda item: (int(item.get("version_number") or 0), str(item.get("arm_id") or "")),
                reverse=True,
            )
            active_members = [item for item in members if item.get("version") == active_version]
            canonical_id = str(family.get("canonical_id") or "")
            active_policy = active_policy_by_canonical.get(canonical_id) or {}
            active_arm_id = str(active_policy.get("arm_id") or "")
            active_result = active_results.get(active_arm_id) or {}
            active_account = active_result.get("account") or {}
            forward_enabled = bool(
                active_policy.get("forward_enabled", bool(active_policy))
            )
            fidelity_status = str(
                active_policy.get("fidelity_status") or "FROZEN_HISTORY"
            )
            historical_terminal = sum(
                int((item.get("samples") or {}).get("terminal_cohorts") or 0)
                for item in members
            )
            historical_pnl = sum(
                float((item.get("outcomes") or {}).get("total_realized_pnl_usd") or 0.0)
                for item in members
            )
            families.append({
                **family,
                "display_index": display_index,
                "entry_family": str(
                    active_policy.get("entry_family") or family.get("entry_family") or ""
                ),
                "exit_family": str(
                    active_policy.get("exit_family") or family.get("exit_family") or ""
                ),
                "members": members,
                "active_version": active_version,
                "active_members": (
                    [f"{active_version}:{active_arm_id}"] if active_arm_id
                    else [item["strategy_key"] for item in active_members]
                ),
                "active_arm_ids": (
                    [active_arm_id] if active_arm_id
                    else [item["arm_id"] for item in active_members]
                ),
                "realtime_state": (
                    "ACTIVE_FORWARD" if active_arm_id and forward_enabled
                    else "COVERAGE_UNAVAILABLE" if active_arm_id
                    else "FROZEN_HISTORY"
                ),
                "fidelity_status": fidelity_status,
                "fidelity_note": str(active_policy.get("fidelity_note") or ""),
                "forward_enabled": forward_enabled,
                "realtime_account": active_account or None,
                "realtime_terminal_count": active_account.get("terminal_position_count"),
                "realtime_realized_pnl_usd": active_account.get(
                    "capital_neutral_realized_pnl_usd"
                ),
                "realtime_total_pnl_usd": active_account.get(
                    "capital_neutral_total_pnl_usd"
                ),
                "historical_terminal_projected_sum": historical_terminal,
                "historical_realized_pnl_projected_sum_usd": historical_pnl,
                "historical_metric_warning": (
                    "projected account totals are descriptive, not independent cohort evidence"
                ),
            })
        represented_arms = {
            str(arm_id)
            for family in families
            for arm_id in family.get("active_arm_ids", [])
        }
        for active_policy in active_policies:
            arm_id = str(active_policy.get("arm_id") or "")
            if not arm_id or arm_id in represented_arms:
                continue
            canonical_id = str(
                active_policy.get("canonical_id") or f"additive-{arm_id}"
            )
            fingerprint = str(
                active_policy.get("behavior_contract_hash")
                or Store.chain_meme_trader_behavior_hash(
                    active_policy, definition_version=active_version,
                )
            )
            forward_enabled = bool(active_policy.get("forward_enabled", True))
            active_result = active_results.get(arm_id) or {}
            active_account = active_result.get("account") or {}
            families.append({
                "canonical_id": canonical_id,
                "behavior_contract_hash": fingerprint,
                "display_index": len(families) + 1,
                "name": str(active_policy.get("name") or arm_id),
                "description": str(active_policy.get("description") or ""),
                "entry_family": str(active_policy.get("entry_family") or ""),
                "exit_family": str(active_policy.get("exit_family") or ""),
                "members": [{
                    "strategy_key": f"{active_version}:{arm_id}",
                    "version": active_version,
                    "arm_id": arm_id,
                    "name": str(active_policy.get("name") or arm_id),
                    "stage": active_policy.get("stage"),
                    "entry_family": active_policy.get("entry_family"),
                    "exit_family": active_policy.get("exit_family"),
                    "classification": "ADDITIVE_FORWARD",
                }],
                "active_version": active_version,
                "active_members": [f"{active_version}:{arm_id}"],
                "active_arm_ids": [arm_id],
                "realtime_state": (
                    "ACTIVE_FORWARD" if forward_enabled else "COVERAGE_UNAVAILABLE"
                ),
                "fidelity_status": str(
                    active_policy.get("fidelity_status") or "ADDITIVE_FORWARD"
                ),
                "fidelity_note": str(active_policy.get("fidelity_note") or ""),
                "forward_enabled": forward_enabled,
                "realtime_account": active_account or None,
                "realtime_terminal_count": active_account.get("terminal_position_count"),
                "realtime_realized_pnl_usd": active_account.get(
                    "capital_neutral_realized_pnl_usd"
                ),
                "realtime_total_pnl_usd": active_account.get(
                    "capital_neutral_total_pnl_usd"
                ),
                "historical_terminal_projected_sum": 0,
                "historical_realized_pnl_projected_sum_usd": 0.0,
                "historical_metric_warning": "new forward strategy; no historical backfill",
            })
        payload = {
            "status": "ok",
            "generated_at": iso(utcnow()),
            "report_generated_at": report.get("metadata", {}).get("generated_at"),
            "active_version": active_version,
            "summary": {
                **report.get("summary", {}),
                "historical_behavior_contract_families": len(
                    report.get("behavior_families", [])
                ),
                "behavior_contract_families": len(families),
                "active_forward_families": sum(
                    family["realtime_state"] == "ACTIVE_FORWARD" for family in families
                ),
                "frozen_history_families": sum(
                    family["realtime_state"] == "FROZEN_HISTORY" for family in families
                ),
                "coverage_unavailable_families": sum(
                    family["realtime_state"] == "COVERAGE_UNAVAILABLE"
                    for family in families
                ),
            },
            "families": families,
            "classification_note": (
                "Historical classifications are evidence labels, not approved promotion decisions."
            ),
            "shared_market_data": True,
            "provider_requests_triggered": 0,
        }
        if len(families) < 124:
            raise ValueError(
                f"expected at least 124 preserved behavior contract families, "
                f"found {len(families)}"
            )
        with self._cache_lock:
            self._universe_cache = (cache_key, payload)
        return payload

    def token_detail(self, token_id: str) -> dict[str, Any]:
        if not token_id or ":" not in token_id:
            return {"status": "not_found", "token_id": token_id}
        current = utcnow()
        with self._connect() as connection:
            token = connection.execute(
                "SELECT token_id,chain,address,name,symbol,created_at,source,url,"
                "first_seen_at,last_seen_at FROM tokens WHERE token_id=?", (token_id,),
            ).fetchone()
            if token is None:
                return {"status": "not_found", "token_id": token_id}
            token_view = dict(token)
            latest_raw = connection.execute(
                "SELECT raw_json FROM token_snapshots WHERE token_id=? "
                "ORDER BY observed_at DESC,id DESC LIMIT 1", (token_id,),
            ).fetchone()
            raw = Store._json_object(latest_raw["raw_json"]) if latest_raw else {}
            pair = raw.get("pair") if isinstance(raw.get("pair"), dict) else {}
            info = pair.get("info") if isinstance(pair.get("info"), dict) else {}
            links: list[dict[str, str]] = []
            seen_links: set[str] = set()

            def add_link(label: str, url: Any) -> None:
                value = str(url or "").strip()
                parsed = urlparse(value)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    return
                if value in seen_links:
                    return
                seen_links.add(value)
                links.append({"label": label, "url": value})

            add_link("行情页面", token_view.get("url") or pair.get("url"))
            chain = str(token_view.get("chain") or "").lower()
            add_link(
                "DexScreener",
                f"https://dexscreener.com/{chain}/{token_view['address']}",
            )
            if chain == "solana":
                add_link("Pump.fun", f"https://pump.fun/coin/{token_view['address']}")
                add_link("Solscan", f"https://solscan.io/token/{token_view['address']}")
            elif chain == "bsc":
                add_link("BscScan", f"https://bscscan.com/token/{token_view['address']}")
            elif chain == "robinhood":
                add_link(
                    "Robinhood Chain Explorer",
                    f"https://robinhoodchain.blockscout.com/address/{token_view['address']}",
                )
            for website in info.get("websites") or []:
                if isinstance(website, dict):
                    add_link(str(website.get("label") or "项目网站"), website.get("url"))
            for social in info.get("socials") or []:
                if isinstance(social, dict):
                    add_link(str(social.get("type") or "社交平台"), social.get("url"))
            token_view["description"] = str(
                info.get("description") or pair.get("description") or ""
            ).strip()
            token_view["image_url"] = str(info.get("imageUrl") or "").strip()
            token_view["links"] = links
            active_row = connection.execute(
                "SELECT definition_version FROM chain_meme_trader_v6_activations "
                "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
            ).fetchone()
            active_version = str(
                active_row["definition_version"]
                if active_row is not None else Store.CHAIN_MEME_TRADER_VERSION
            )
            registration = connection.execute(
                "SELECT definition_json FROM chain_meme_trader_registrations "
                "WHERE definition_version=?", (active_version,),
            ).fetchone()
            definition = Store._json_object(registration["definition_json"]) if registration else {}
            slippage = int(definition.get("slippage_bps") or 400) / 10_000.0
            corrections = Store._chain_meme_trader_market_fill_corrections_from_connection(
                connection, active_version,
            )
            corrections_by_position = {
                (str(row["arm_id"]), int(row["shadow_cohort_id"])): row
                for row in corrections
            }
            corrections_by_trade = {
                int(row["source_trade_id"]): row for row in corrections
            }
            contaminated_positions = {
                (str(row["arm_id"]), int(row["shadow_cohort_id"]))
                for row in (
                    Store._chain_meme_trader_accounting_contaminations_from_connection(
                        connection, active_version,
                    )
                )
            }
            snapshot_rows = self._rows(
                connection,
                "SELECT id,observed_at,ingested_at,provider,price_usd,liquidity_usd,"
                "market_cap_usd,volume_5m_usd,buys_5m,sells_5m,sellable "
                "FROM token_snapshots WHERE token_id=? ORDER BY observed_at DESC LIMIT 240",
                (token_id,),
            )
            tables = {
                str(row[0]) for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            market_history = (
                self._rows(
                    connection,
                    "SELECT id,observed_at,recorded_at AS ingested_at,provider,price_usd,"
                    "liquidity_usd,NULL AS market_cap_usd,volume_5m_usd,buys_5m,"
                    "sells_5m,(status='VISIBLE') AS sellable FROM "
                    "chain_meme_trader_market_mark_history WHERE token_id=? "
                    "AND status='VISIBLE' AND price_usd>0 ORDER BY recorded_at DESC LIMIT 7200",
                    (token_id,),
                )[::-1]
                if "chain_meme_trader_market_mark_history" in tables else []
            )
            market_mark_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(chain_meme_trader_market_marks)"
                ).fetchall()
            }
            optional_market_fields = ",".join(
                field if field in market_mark_columns else f"NULL AS {field}"
                for field in ("first_missing_at", "failure_kind", "sample_sequence")
            )
            market_state_row = (
                connection.execute(
                    "SELECT token_id,pair_address,provider,price_usd,liquidity_usd,"
                    "volume_5m_usd,buys_5m,sells_5m,observed_at,recorded_at,status,"
                    "consecutive_misses,last_attempt_at,last_success_at,"
                    f"{optional_market_fields} FROM "
                    "chain_meme_trader_market_marks WHERE token_id=?",
                    (token_id,),
                ).fetchone()
                if "chain_meme_trader_market_marks" in tables else None
            )
            current_mark = []
            if (
                market_state_row is not None
                and str(market_state_row["status"]) == "VISIBLE"
                and float(market_state_row["price_usd"] or 0.0) > 0.0
            ):
                current_mark.append({
                    "id": None,
                    "observed_at": market_state_row["observed_at"],
                    "ingested_at": market_state_row["recorded_at"],
                    "provider": market_state_row["provider"],
                    "price_usd": market_state_row["price_usd"],
                    "liquidity_usd": market_state_row["liquidity_usd"],
                    "market_cap_usd": None,
                    "volume_5m_usd": market_state_row["volume_5m_usd"],
                    "buys_5m": market_state_row["buys_5m"],
                    "sells_5m": market_state_row["sells_5m"],
                    "sellable": 1,
                })
            price_points: dict[str, dict[str, Any]] = {}
            for item in snapshot_rows[::-1] + market_history + current_mark:
                observed_at = str(item.get("observed_at") or item.get("ingested_at") or "")
                if observed_at and float(item.get("price_usd") or 0.0) > 0.0:
                    price_points[observed_at] = item
            snapshots = sorted(price_points.values(), key=lambda item: str(item["observed_at"]))
            if len(snapshots) > 720:
                stride = max(1, len(snapshots) // 719)
                snapshots = snapshots[::stride]
                latest_point = max(price_points.values(), key=lambda item: str(item["observed_at"]))
                if snapshots[-1]["observed_at"] != latest_point["observed_at"]:
                    snapshots.append(latest_point)
            if market_state_row is not None:
                market = dict(market_state_row)
            elif snapshots:
                latest_fallback = snapshots[-1]
                market = {
                    "token_id": token_id,
                    "pair_address": pair.get("pairAddress"),
                    "provider": latest_fallback.get("provider"),
                    "price_usd": latest_fallback.get("price_usd"),
                    "liquidity_usd": latest_fallback.get("liquidity_usd"),
                    "volume_5m_usd": latest_fallback.get("volume_5m_usd"),
                    "buys_5m": latest_fallback.get("buys_5m"),
                    "sells_5m": latest_fallback.get("sells_5m"),
                    "observed_at": latest_fallback.get("observed_at"),
                    "recorded_at": latest_fallback.get("ingested_at"),
                    "status": "VISIBLE" if latest_fallback.get("sellable") else "UNKNOWN",
                    "consecutive_misses": 0,
                    "first_missing_at": None,
                    "failure_kind": "",
                    "last_attempt_at": latest_fallback.get("ingested_at"),
                    "last_success_at": latest_fallback.get("ingested_at"),
                }
            else:
                market = {
                    "token_id": token_id,
                    "pair_address": None,
                    "provider": None,
                    "price_usd": None,
                    "liquidity_usd": None,
                    "volume_5m_usd": None,
                    "buys_5m": None,
                    "sells_5m": None,
                    "observed_at": None,
                    "recorded_at": None,
                    "status": "UNKNOWN",
                    "consecutive_misses": 0,
                    "first_missing_at": None,
                    "failure_kind": "",
                    "last_attempt_at": None,
                    "last_success_at": None,
                }
            market.setdefault("first_missing_at", None)
            market.setdefault("failure_kind", "")
            market_at = market.get("last_success_at") or market.get("recorded_at")
            market_age = (
                (current - parse_time(market_at)).total_seconds() if market_at else None
            )
            market_observed_age = (
                (current - parse_time(market["observed_at"])).total_seconds()
                if market.get("observed_at") else None
            )
            market["age_seconds"] = market_age
            market["observed_age_seconds"] = market_observed_age
            market["is_fresh"] = bool(
                str(market.get("status")) == "VISIBLE"
                and market.get("pair_address")
                and float(market.get("price_usd") or 0.0) > 0.0
                and (
                    market.get("liquidity_usd") is None
                    or float(market["liquidity_usd"]) >= 0.0
                )
                and market_age is not None
                and 0.0 <= market_age <= 15.0
                and market_observed_age is not None
                and 0.0 <= market_observed_age <= 15.0
            )
            missing_since = market.get("first_missing_at")
            market["missing_duration_seconds"] = (
                max(0.0, (current - parse_time(missing_since)).total_seconds())
                if str(market.get("status")) == "MISSING" and missing_since
                else None
            )
            market["writeoff_after_missing_seconds"] = 60.0
            market["writeoff_due"] = bool(
                market["missing_duration_seconds"] is not None
                and market["missing_duration_seconds"] > 60.0
            )
            price_history = [
                {
                    "observed_at": item.get("observed_at"),
                    "recorded_at": item.get("ingested_at"),
                    "price_usd": item.get("price_usd"),
                    "provider": item.get("provider"),
                }
                for item in snapshots if item.get("price_usd") is not None
            ]
            liquidity_history = [
                {
                    "observed_at": item.get("observed_at"),
                    "recorded_at": item.get("ingested_at"),
                    "liquidity_usd": item.get("liquidity_usd"),
                    "provider": item.get("provider"),
                }
                for item in snapshots if item.get("liquidity_usd") is not None
            ]
            positions = self._rows(
                connection,
                "SELECT arm_id,shadow_cohort_id,status,stake_usd,amount_raw,initial_amount_raw,"
                "entry_signal_price_usd,entry_execution_price_usd,allocated_cost_usd,"
                "realized_pnl_usd,opened_at,"
                "closed_at,close_reason,last_evaluated_at FROM chain_meme_trader_positions "
                "WHERE definition_version=? AND token_id=? ORDER BY arm_id",
                (active_version, token_id),
            )
            latest_price = (
                float(market.get("price_usd") or 0.0)
                if market.get("is_fresh") else 0.0
            )
            for position in positions:
                position_key = (
                    str(position["arm_id"]), int(position["shadow_cohort_id"]),
                )
                correction = corrections_by_position.get(position_key)
                if correction is not None:
                    position["recorded_status"] = position["status"]
                    position["raw_closed_at"] = position["closed_at"]
                    position["recorded_realized_pnl_usd"] = position["realized_pnl_usd"]
                    outcome = str(correction["replacement_outcome"])
                    position["status"] = {
                        "SELL": "closed", "WRITEOFF": "written_off",
                        "UNRESOLVED": "open",
                    }[outcome]
                    position["realized_pnl_usd"] = (
                        float(position.get("realized_pnl_usd") or 0.0)
                        + float(correction["realized_adjustment_usd"] or 0.0)
                    )
                    position["closed_at"] = (
                        None if outcome == "UNRESOLVED" else
                        correction.get("replacement_observed_at")
                        or position["closed_at"]
                    )
                    position["accounting_status"] = "MARKET_FILL_CORRECTED"
                    position["market_fill_correction"] = dict(correction)
                contaminated = position_key in contaminated_positions
                if contaminated:
                    position["accounting_status"] = "ACCOUNTING_CONTAMINATED"
                    position["formal_metrics_eligible"] = False
                terminal_at = position.get("closed_at") or current
                holding_seconds = (
                    parse_time(terminal_at) - parse_time(position["opened_at"])
                ).total_seconds()
                position["holding_seconds"] = (
                    holding_seconds if holding_seconds >= 0.0 else None
                )
                position["holding_time_status"] = (
                    "valid" if holding_seconds >= 0.0 else "invalid_future_opened_at"
                )
                position["indicative_value_usd"] = None
                position["indicative_unrealized_pnl_usd"] = None
                if (
                    not contaminated
                    and str(position.get("status")) == "open"
                    and latest_price > 0.0
                    and float(
                        position.get("entry_execution_price_usd")
                        or position.get("entry_signal_price_usd")
                        or 0.0
                    ) > 0.0
                    and int(position.get("initial_amount_raw") or position.get("amount_raw") or 0) > 0
                ):
                    initial_raw = int(position.get("initial_amount_raw") or position["amount_raw"])
                    remaining_raw = int(position.get("amount_raw") or 0)
                    remaining_fraction = max(0.0, min(1.0, remaining_raw / initial_raw))
                    entry_price = float(
                        position.get("entry_execution_price_usd")
                        or position.get("entry_signal_price_usd")
                    )
                    remaining_cost = max(
                        0.0,
                        float(position["stake_usd"])
                        - float(position.get("allocated_cost_usd") or 0.0),
                    )
                    position["indicative_value_usd"] = (
                        0.0
                        if market.get("liquidity_usd") is not None
                        and float(market["liquidity_usd"]) < 1.0
                        else max(
                            0.0,
                            float(position["stake_usd"]) * remaining_fraction * latest_price
                            / entry_price * (1.0 - slippage),
                        )
                    )
                    position["indicative_unrealized_pnl_usd"] = (
                        float(position["indicative_value_usd"]) - remaining_cost
                    )
            trades = self._rows(
                connection,
                "SELECT id,arm_id,shadow_cohort_id,side,gross_usd,net_cash_flow_usd,"
                "realized_pnl_usd,reason,created_at FROM chain_meme_trader_trades "
                "WHERE definition_version=? AND token_id=? ORDER BY id",
                (active_version, token_id),
            )
            effective_trades = []
            for trade in trades:
                position_key = (
                    str(trade["arm_id"]), int(trade["shadow_cohort_id"]),
                )
                trade.update({
                    "raw_side": trade["side"],
                    "raw_gross_usd": trade["gross_usd"],
                    "raw_net_cash_flow_usd": trade["net_cash_flow_usd"],
                    "raw_realized_pnl_usd": trade["realized_pnl_usd"],
                    "raw_reason": trade["reason"],
                    "raw_created_at": trade["created_at"],
                })
                correction = corrections_by_trade.get(int(trade["id"]))
                if correction is not None:
                    outcome = str(correction["replacement_outcome"])
                    trade.update({
                        "side": outcome,
                        "gross_usd": (
                            float(correction["replacement_gross_usd"] or 0.0)
                            if outcome == "SELL" else 0.0
                        ),
                        "net_cash_flow_usd": (
                            float(trade.get("net_cash_flow_usd") or 0.0)
                            + float(correction["cash_adjustment_usd"] or 0.0)
                        ),
                        "realized_pnl_usd": (
                            float(trade.get("realized_pnl_usd") or 0.0)
                            + float(correction["realized_adjustment_usd"] or 0.0)
                        ),
                        "reason": str(correction["reason"]),
                        "created_at": (
                            correction.get("replacement_observed_at")
                            or trade["created_at"]
                        ),
                        "accounting_status": "MARKET_FILL_CORRECTED",
                        "market_fill_correction": dict(correction),
                    })
                if position_key in contaminated_positions:
                    trade.update({
                        "side": "EXCLUDED", "gross_usd": None,
                        "net_cash_flow_usd": None, "realized_pnl_usd": None,
                        "accounting_status": "ACCOUNTING_CONTAMINATED",
                        "formal_metrics_eligible": False,
                    })
                effective_trades.append(trade)
            trades = effective_trades
            unique_trade_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
            for trade in trades:
                if str(trade.get("side")) == "EXCLUDED":
                    continue
                unique_trade_rows[(
                    str(trade.get("shadow_cohort_id") or ""),
                    str(trade.get("side") or ""),
                    str(trade.get("created_at") or ""),
                    str(trade.get("arm_id") or ""),
                )] = trade
            marker_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
            for (cohort_id, side, created_at, _arm_id), trade in unique_trade_rows.items():
                marker_groups[(cohort_id, side, created_at)].append(trade)
            trade_markers = []
            for (cohort_id, side, created_at), rows in sorted(
                marker_groups.items(), key=lambda item: item[0][2]
            ):
                reasons = list(dict.fromkeys(
                    str(row.get("reason") or "") for row in rows
                ))
                arm_ids = sorted({str(row.get("arm_id") or "") for row in rows})
                gross_values = [float(row.get("gross_usd") or 0.0) for row in rows]
                trade_markers.append({
                    "shadow_cohort_id": int(cohort_id) if cohort_id else None,
                    "side": side,
                    "marker_type": "WRITEOFF" if side == "WRITEOFF" else side,
                    "created_at": created_at,
                    "time": created_at,
                    "strategy_count": len(arm_ids),
                    "arm_ids": arm_ids,
                    "gross_usd_total": sum(gross_values),
                    "gross_usd_each": (
                        gross_values[0]
                        if gross_values and all(value == gross_values[0] for value in gross_values)
                        else None
                    ),
                    "net_cash_flow_usd_total": sum(
                        float(row.get("net_cash_flow_usd") or 0.0) for row in rows
                    ),
                    "realized_pnl_usd_total": sum(
                        float(row.get("realized_pnl_usd") or 0.0) for row in rows
                    ),
                    "reason": reasons[0] if len(reasons) == 1 else None,
                    "reasons": reasons,
                })
            values = (active_version, token_id)
            return {
                "status": "ok",
                "version": active_version,
                "token": token_view,
                "market": market,
                "snapshots": snapshots,
                "price_history": price_history,
                "liquidity_history": liquidity_history,
                "decisions": self._rows(
                    connection,
                    "SELECT arm_id,shadow_cohort_id,status,reason,decided_at "
                    "FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
                    "AND token_id=? ORDER BY arm_id", values,
                ),
                "positions": positions,
                "trades": trades,
                "trade_markers": trade_markers,
                "intents": self._rows(
                    connection,
                    "SELECT id,arm_id,shadow_cohort_id,side,status,reason,created_at,"
                    "next_attempt_at,completed_at FROM chain_meme_trader_order_intents "
                    "WHERE definition_version=? AND token_id=? ORDER BY id", values,
                ),
                "fills": self._rows(
                    connection,
                    "SELECT id,arm_id,shadow_cohort_id,side,input_amount_raw,"
                    "output_amount_raw,gross_usd,adapter,filled_at "
                    "FROM chain_meme_trader_fills WHERE definition_version=? "
                    "AND token_id=? ORDER BY id", values,
                ) + (
                    self._rows(
                        connection,
                        "SELECT f.id,('entry:' || c.entry_family) AS arm_id,"
                        "f.entry_cohort_id AS shadow_cohort_id,'BUY' AS side,"
                        "f.input_usdc_raw AS input_amount_raw,"
                        "f.output_token_raw AS output_amount_raw,20.0 AS gross_usd,"
                        "'jupiter_quote_minimum_output_paper/v1' AS adapter,f.filled_at "
                        "FROM chain_meme_trader_v6_entry_fills f "
                        "JOIN chain_meme_trader_v6_cohorts c ON c.id=f.entry_cohort_id "
                        "WHERE f.definition_version=? AND f.token_id=? ORDER BY f.id",
                        values,
                    ) if active_version == Store.CHAIN_MEME_TRADER_V6_VERSION else []
                ),
                "routes": self._rows(
                    connection,
                    "SELECT direction,status,observed_at FROM execution_route_observations "
                    "WHERE token_id=? ORDER BY id DESC LIMIT 30", (token_id,),
                ),
                "risk": self._rows(
                    connection,
                    "SELECT account_kind,risk_state,risk_reason,slot,observed_at "
                    "FROM onchain_held_account_risk_events WHERE monitor_version=? "
                    "AND position_definition_version=? AND token_id=? ORDER BY id DESC LIMIT 30",
                    (Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION,
                     active_version, token_id),
                ),
                "held_accounts": self._rows(
                    connection,
                    "SELECT account_kind,pool_address,registered_at FROM "
                    "onchain_held_account_targets WHERE monitor_version=? "
                    "AND position_definition_version=? AND token_id=? ORDER BY account_kind",
                    (Store.ONCHAIN_HELD_ACCOUNT_MONITOR_VERSION,
                     active_version, token_id),
                ),
                "immediate_reverseability": [
                    {
                        **dict(row),
                        "evidence": Store._json_object(row["evidence_json"]),
                    }
                    for row in connection.execute(
                        "SELECT * FROM chain_meme_trader_immediate_reverseability_outcomes "
                        "WHERE observer_version=? AND definition_version=? AND token_id=? "
                        "ORDER BY entry_fill_id,horizon_seconds",
                        (
                            Store.CHAIN_MEME_TRADER_IMMEDIATE_REVERSEABILITY_VERSION,
                            active_version, token_id,
                        ),
                    ).fetchall()
                ],
            }

    def health(self) -> dict[str, Any]:
        try:
            current = utcnow()
            with self._connect() as connection:
                heartbeat = connection.execute(
                    "SELECT last_item_at,last_ok_at FROM source_health "
                    "WHERE source='chain-meme-trader'"
                ).fetchone()
                active = connection.execute(
                    "SELECT definition_version FROM chain_meme_trader_v6_activations "
                    "WHERE entry_execution_enabled=1 "
                    "ORDER BY activated_at DESC,rowid DESC LIMIT 1"
                ).fetchone()
        except (OSError, sqlite3.Error, ValueError) as exc:
            return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
        heartbeat_at = (
            heartbeat["last_item_at"] or heartbeat["last_ok_at"]
            if heartbeat is not None else None
        )
        heartbeat_age = (
            (current - parse_time(heartbeat_at)).total_seconds()
            if heartbeat_at else None
        )
        return {
            "ok": True,
            "runtime_status": (
                "running"
                if heartbeat_age is not None and 0.0 <= heartbeat_age <= 30.0
                else "stale"
            ),
            "version": (
                str(active["definition_version"])
                if active is not None else Store.CHAIN_MEME_TRADER_VERSION
            ),
        }


class ChainWebHandler(BaseHTTPRequestHandler):
    server: "ChainWebServer"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _send_asset(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _read_json(self) -> Any:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise LiveWalletError("请求长度无效") from None
        if length <= 0 or length > 20_000:
            raise LiveWalletError("请求内容为空或过大")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise LiveWalletError("请求不是有效 JSON") from None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/health":
            self._send_json(self.server.data.health())
            return
        if route == "/api/state":
            try:
                arm_id = str(
                    parse_qs(parsed.query).get("arm_id", [""])[0]
                ).strip() or None
                self._send_json(self.server.data.state(arm_id=arm_id))
            except (OSError, sqlite3.Error, ValueError) as exc:
                self.server.data.record_web_error(route, exc)
                self._send_json(
                    {"status": "error", "error": type(exc).__name__},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return
        if route == "/api/live":
            try:
                arm_id = str(
                    parse_qs(parsed.query).get("arm_id", [""])[0]
                ).strip() or None
                self._send_json(
                    self.server.data.state(compact=True, arm_id=arm_id)
                )
            except (OSError, sqlite3.Error, ValueError) as exc:
                self.server.data.record_web_error(route, exc)
                self._send_json(
                    {"status": "error", "error": type(exc).__name__},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return
        if route == "/api/strategy-universe":
            try:
                self._send_json(self.server.data.strategy_universe())
            except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
                self.server.data.record_web_error(route, exc)
                self._send_json(
                    {"status": "error", "error": type(exc).__name__},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return
        if route == "/api/wallets":
            try:
                refresh = str(parse_qs(parsed.query).get("refresh", [""])[0]) == "1"
                self._send_json(self.server.data.wallet_state(refresh=refresh))
            except LiveWalletError as exc:
                self._send_json({"status": "error", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/wallet":
            try:
                query = parse_qs(parsed.query)
                refresh = str(query.get("refresh", [""])[0]) == "1"
                wallet_id = str(query.get("id", [""])[0])
                self._send_json(
                    self.server.data.wallet_detail(wallet_id, refresh=refresh)
                )
            except LiveWalletError as exc:
                self._send_json(
                    {"status": "error", "error": str(exc)}, HTTPStatus.BAD_REQUEST
                )
            except (OSError, sqlite3.Error, ValueError) as exc:
                self.server.data.record_web_error(route, exc)
                self._send_json(
                    {"status": "error", "error": type(exc).__name__},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return
        if route == "/api/errors":
            try:
                self._send_json(self.server.data.error_state())
            except (OSError, sqlite3.Error, ValueError) as exc:
                self.server.data.record_web_error(route, exc)
                self._send_json(
                    {"status": "error", "error": type(exc).__name__},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return
        if route == "/api/error":
            try:
                raw_id = str(parse_qs(parsed.query).get("id", [""])[0])
                payload = self.server.data.error_detail(int(raw_id))
                status = HTTPStatus.OK if payload.get("status") == "ok" else HTTPStatus.NOT_FOUND
                self._send_json(payload, status)
            except (TypeError, ValueError):
                self._send_json(
                    {"status": "error", "error": "错误编号无效"}, HTTPStatus.BAD_REQUEST
                )
            except (OSError, sqlite3.Error) as exc:
                self.server.data.record_web_error(route, exc)
                self._send_json(
                    {"status": "error", "error": type(exc).__name__},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return
        if route == "/api/token":
            token_id = str(parse_qs(parsed.query).get("token_id", [""])[0])
            payload = self.server.data.token_detail(token_id)
            status = HTTPStatus.OK if payload["status"] == "ok" else HTTPStatus.NOT_FOUND
            self._send_json(payload, status)
            return
        asset_name = "index.html" if route in {"", "/"} else route.lstrip("/")
        asset = (self.server.static_dir / asset_name).resolve()
        if self.server.static_dir not in asset.parents and asset != self.server.static_dir:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_asset(asset)

    def do_POST(self) -> None:
        route = urlparse(self.path).path.rstrip("/")
        actions = {
            "/api/wallets/connect": self.server.data.connect_wallet,
            "/api/wallets/bind": self.server.data.bind_wallet,
            "/api/wallets/live": self.server.data.set_wallet_live,
            "/api/errors/status": self.server.data.update_error,
        }
        action = actions.get(route)
        if action is None:
            self._send_json({"status": "error", "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        try:
            self._send_json(action(self._read_json()))
        except LiveWalletError as exc:
            self._send_json({"status": "error", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except ValueError as exc:
            self._send_json({"status": "error", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, sqlite3.Error) as exc:
            self.server.data.record_web_error(route, exc)
            self._send_json(
                {"status": "error", "error": type(exc).__name__},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )


class ChainWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], data: ChainWebData, static_dir: Path):
        self.data = data
        self.static_dir = static_dir.resolve()
        self._live_stop = threading.Event()
        super().__init__(address, ChainWebHandler)
        self._live_thread: threading.Thread | None = None
        if self.data.live_enabled:
            self._live_thread = threading.Thread(target=self._live_loop, daemon=True)
            self._live_thread.start()

    def _live_loop(self) -> None:
        while not self._live_stop.wait(1.0):
            try:
                self.data.wallets.sync_once()
            except (OSError, sqlite3.Error, ValueError):
                continue

    def server_close(self) -> None:
        self._live_stop.set()
        super().server_close()


def create_server(
    config_path: str | Path = "config.json",
    host: str = "127.0.0.1",
    port: int = 8790,
    *,
    static_dir: str | Path | None = None,
) -> ChainWebServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("ChainMemeTrader Web is loopback-only")
    if not 1 <= int(port) <= 65535:
        raise ValueError("web port must be between 1 and 65535")
    assets = Path(static_dir).resolve() if static_dir else Path(__file__).with_name("chain_web_static")
    return ChainWebServer((host, int(port)), ChainWebData(config_path), assets)


def serve(config_path: str | Path = "config.json", host: str = "127.0.0.1", port: int = 8790) -> int:
    server = create_server(config_path, host, port)
    print(f"ChainMemeTrader Web: http://{host}:{port}")
    print("Forward Paper active; each connected wallet can bind one strategy for Mainnet Live.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent ChainMemeTrader Web")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args(argv)
    return serve(args.config, args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
