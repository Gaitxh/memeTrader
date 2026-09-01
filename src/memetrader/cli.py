from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sqlite3
import sys
import tempfile
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .autonomous_search import CONTEXT_RESULT_KEY, REGISTRY_KEY, SOURCE_RESULT_KEY, TREND_RESULT_KEY
from .models import Observation, parse_time
from .runtime import Runtime, SingleInstance, configure_project_temp, initial_config, load_config
from .store import Store
from .strategy import EventEngine, replay_guard, token_snapshot_temporal_rejections


def _doctor_payload_valid(name: str, response) -> bool:
    if not 200 <= int(response.status_code) < 400:
        return False
    if name not in {"goplus_evm", "goplus_solana", "honeypot", "rugcheck", "jupiter_quote"}:
        return True
    try:
        payload = response.json()
    except Exception:
        return False
    if name.startswith("goplus_"):
        if not isinstance(payload, dict) or payload.get("code") not in {1, "1"}:
            return False
        result = payload.get("result")
        return isinstance(result, dict) and any(isinstance(row, dict) and row for row in result.values())
    if name == "honeypot":
        result = payload.get("honeypotResult") if isinstance(payload, dict) else None
        return isinstance(result, dict) and "isHoneypot" in result
    if name == "jupiter_quote":
        return (
            isinstance(payload, dict)
            and payload.get("transaction") is None
            and int(payload.get("outAmount") or 0) > 0
            and int(payload.get("otherAmountThreshold") or 0) > 0
            and isinstance(payload.get("routePlan"), list)
            and bool(payload["routePlan"])
        )
    return isinstance(payload, dict) and any(
        key in payload for key in ("score", "score_normalised", "risks", "rugged")
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memetrader", description="Forward-only event-driven meme-token paper bot")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a local config with a random browser bridge token")
    init.add_argument("--config", default="config.json")
    for name in ("run", "once", "status", "doctor"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", default="config.json")
        if name == "status":
            cmd.add_argument("--limit", type=int, default=30)
        if name == "doctor":
            cmd.add_argument("--online", action="store_true")
    discover = sub.add_parser("discover-sources", help="let the budgeted Agent find and verify public feeds")
    discover.add_argument("--config", default="config.json")
    discover.add_argument("--force", action="store_true")
    scout = sub.add_parser("scout-trends", help="run the proactive global meme-event search Agent")
    scout.add_argument("--config", default="config.json")
    scout.add_argument("--force", action="store_true")
    web = sub.add_parser("web", help="run the loopback Web console")
    web.add_argument("--config", default="config.json")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8787)
    web.add_argument("--access-token-file")
    replay = sub.add_parser("replay")
    replay.add_argument("fixture")
    replay.add_argument("--decision-at", required=True)
    return parser


def cmd_init(path: str) -> int:
    target = Path(path).resolve()
    if target.exists():
        print(f"refusing to overwrite existing {target}", file=sys.stderr)
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(initial_config(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"created {target}")
    print("Copy the bridge.token into the browser extension options. Live remains disabled.")
    return 0


async def _run_runtime(config_path: str, forever: bool) -> int:
    config, root = load_config(config_path)
    lock_path = Path(str(config.get("lock_file", "data/memetrader.lock")))
    lock_path = lock_path if lock_path.is_absolute() else root / lock_path
    try:
        with SingleInstance(lock_path):
            runtime = Runtime(config, root)
            try:
                if forever:
                    await runtime.run_forever()
                else:
                    await runtime.run_once()
                return 0
            except KeyboardInterrupt:
                runtime.stop()
                return 130
            finally:
                await runtime.close()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except Exception:
        crash_log = root / "data" / "logs" / "runtime-crash.log"
        crash_log.parent.mkdir(parents=True, exist_ok=True)
        detail = traceback.format_exc()
        with crash_log.open("a", encoding="utf-8") as handle:
            handle.write(detail + "\n")
        print(detail, file=sys.stderr)
        return 1


def _store_from_config(config_path: str) -> tuple[Store, dict, Path]:
    config, root = load_config(config_path)
    db_path = Path(str(config["database"]))
    return (
        Store(
            db_path if db_path.is_absolute() else root / db_path,
            initial_cash_usd=float(config["paper"].get("starting_cash_usd", 1_000)),
        ),
        config,
        root,
    )


def cmd_status(config_path: str, limit: int) -> int:
    store, config, _ = _store_from_config(config_path)
    try:
        account = store.account()
        disabled_sources = {
            str(item.get("name") or item.get("url") or "")
            for item in config["sources"].get("rss", [])
            if not item.get("enabled", True)
        }
        day = datetime.now(timezone.utc).date().isoformat()
        payload = {
            "mode": config["mode"],
            "account": account,
            "positions": [asdict(p) for p in store.open_positions()],
            "decisions": [dict(row) for row in store.decisions(limit)],
            "trades": [dict(row) for row in store.trades(limit)],
            "sources": [
                dict(row)
                for row in store.source_health()
                if str(row["source"]) not in disabled_sources
            ],
            "autonomous_sources": store.get_kv(REGISTRY_KEY, []),
            "autonomous_search_usage": {
                "trend_scout": int(store.get_kv(f"autonomous_search_quota:{day}:trend_scout", 0)),
                "trend_scout_tokens": int(store.get_kv(f"autonomous_search_tokens:{day}:trend_scout", 0)),
                "source_discovery": int(store.get_kv(f"autonomous_search_quota:{day}:source_discovery", 0)),
                "source_discovery_tokens": int(store.get_kv(f"autonomous_search_tokens:{day}:source_discovery", 0)),
                "token_context": int(store.get_kv(f"autonomous_search_quota:{day}:token_context", 0)),
                "token_context_tokens": int(store.get_kv(f"autonomous_search_tokens:{day}:token_context", 0)),
            },
            "autonomous_trend_last_result": store.get_kv(TREND_RESULT_KEY),
            "autonomous_source_last_result": store.get_kv(SOURCE_RESULT_KEY),
            "autonomous_context_last_result": store.get_kv(CONTEXT_RESULT_KEY),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        store.close()


def cmd_doctor(config_path: str, online: bool) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []
    try:
        config, root = load_config(config_path)
        checks.append({"name": "config", "ok": True, "path": str(Path(config_path).resolve())})
        checks.append({"name": "live_lock", "ok": not config["live"]["enabled"] and config["mode"] in {"shadow", "paper"}})
        db = Path(str(config["database"]))
        db = db if db.is_absolute() else root / db
        store = Store(
            db,
            initial_cash_usd=float(config["paper"].get("starting_cash_usd", 1_000)),
        )
        integrity = store.db.execute("PRAGMA integrity_check").fetchone()[0]
        store.close()
        checks.append({"name": "sqlite", "ok": integrity == "ok", "path": str(db), "result": integrity})
        bridge = config["bridge"]
        checks.append({"name": "bridge_loopback", "ok": bridge["host"] in {"127.0.0.1", "localhost", "::1"}})
        checks.append({"name": "bridge_private_token", "ok": len(str(bridge["token"])) >= 24 and bridge["token"] != "CHANGE_ME"})
        codex_path = shutil.which(str(config["agent"].get("codex_path", "codex")))
        checks.append({"name": "codex_optional", "ok": bool(codex_path) or not config["agent"].get("enabled"), "path": codex_path})
        search_cfg = config["autonomous_search"]
        search_codex_path = shutil.which(str(search_cfg.get("codex_path", "codex")))
        checks.append(
            {
                "name": "autonomous_search_codex",
                "ok": bool(search_codex_path) or not search_cfg.get("enabled", False),
                "path": search_codex_path,
            }
        )
        if online:
            safety_cfg = config["safety"]
            targets = {
                "dexscreener": ("https://api.dexscreener.com/latest/dex/search?q=PNUT", True),
                "geckoterminal": ("https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1", True),
                "jupiter_quote": (
                    "https://api.jup.ag/swap/v2/order?"
                    "inputMint=So11111111111111111111111111111111111111112&"
                    "outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&"
                    "amount=1000000&slippageBps=400",
                    True,
                ),
            }
            if safety_cfg.get("goplus_evm", True):
                targets["goplus_evm"] = (
                    "https://api.gopluslabs.io/api/v1/token_security/56?contract_addresses=0x55d398326f99059fF775485246999027B3197955",
                    False,
                )
            if safety_cfg.get("honeypot_is", True):
                targets["honeypot"] = (
                    "https://api.honeypot.is/v2/IsHoneypot?address=0x55d398326f99059fF775485246999027B3197955&chainID=56",
                    bool(safety_cfg.get("require_evm_simulation", False)),
                )
            if safety_cfg.get("goplus_solana", True):
                targets["goplus_solana"] = (
                    "https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    False,
                )
            if safety_cfg.get("rugcheck", True):
                targets["rugcheck"] = (
                    "https://api.rugcheck.xyz/v1/tokens/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/report/summary",
                    False,
                )
            if config["sources"].get("bluesky_queries"):
                targets["bluesky"] = (
                    "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=memecoin&limit=1",
                    True,
                )
            for item in config["sources"].get("rss", []):
                if item.get("enabled", True) and item.get("url"):
                    targets[f"rss:{item.get('name') or item['url']}"] = (str(item["url"]), True)
            online_reachable: dict[str, bool] = {}
            with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": "memeTrader-doctor/0.6.1"}) as client:
                for name, (url, required) in targets.items():
                    try:
                        response = client.get(url)
                        reachable = _doctor_payload_valid(name, response)
                        online_reachable[name] = reachable
                        checks.append(
                            {
                                "name": f"online:{name}",
                                "ok": reachable or not required,
                                "reachable": reachable,
                                "required": required,
                                "status": response.status_code,
                            }
                        )
                    except Exception as exc:
                        online_reachable[name] = False
                        checks.append(
                            {
                                "name": f"online:{name}",
                                "ok": not required,
                                "reachable": False,
                                "required": required,
                                "error": type(exc).__name__,
                            }
                        )
            if safety_cfg.get("require_evm_security_report", True):
                configured_evm_chains = {
                    str(chain).lower()
                    for chain in config["candidate"].get("chains", [])
                    if str(chain).lower() in {"ethereum", "eth", "bsc", "base"}
                }
                coverage: dict[str, bool] = {}
                for chain in configured_evm_chains:
                    if chain == "bsc":
                        coverage[chain] = bool(
                            online_reachable.get("goplus_evm", False)
                            or online_reachable.get("honeypot", False)
                        )
                    else:
                        coverage[chain] = bool(online_reachable.get("goplus_evm", False))
                reachable = bool(coverage) and all(coverage.values())
                checks.append(
                    {
                        "name": "online:evm_security_provider",
                        "ok": reachable,
                        "reachable": reachable,
                        "required": True,
                        "coverage": coverage,
                    }
                )
            if safety_cfg.get("require_solana_report", True):
                providers = [name for name in ("goplus_solana", "rugcheck") if name in targets]
                reachable = any(online_reachable.get(name, False) for name in providers)
                checks.append(
                    {
                        "name": "online:solana_security_provider",
                        "ok": reachable,
                        "reachable": reachable,
                        "required": True,
                        "providers": providers,
                    }
                )
    except Exception as exc:
        checks.append({"name": "startup", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    for check in checks:
        if not check.get("ok"):
            errors.append(check["name"])
        elif check.get("reachable") is False:
            warnings.append(check["name"])
    print(
        json.dumps(
            {"ok": not errors, "checks": checks, "errors": errors, "warnings": warnings},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 4


async def cmd_discover_sources(config_path: str, force: bool) -> int:
    config, root = load_config(config_path)
    runtime = Runtime(config, root)
    try:
        result = await runtime.discover_sources_once(force=force)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 5 if result.get("status") == "agent_error" else 0
    finally:
        await runtime.close()


async def cmd_scout_trends(config_path: str, force: bool) -> int:
    config, root = load_config(config_path)
    runtime = Runtime(config, root)
    try:
        result = await runtime.scout_trends_once(force=force)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 5 if result.get("status") == "agent_error" else 0
    finally:
        await runtime.close()


def cmd_replay(fixture_path: str, decision_at: str) -> int:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    decision = parse_time(decision_at)
    temp_root = configure_project_temp(Path(__file__).resolve().parents[2])
    with tempfile.TemporaryDirectory(prefix="memetrader-replay-", dir=temp_root) as temp:
        store = Store(Path(temp) / "replay.sqlite3")
        engine = EventEngine(store)
        event_ids: list[int] = []
        for item in fixture.get("observations", []):
            obs = Observation(
                source=item["source"], source_kind=item.get("source_kind", "news"), title=item["title"],
                text=item.get("text", ""), url=item.get("url", ""), author=item.get("author", ""),
                published_at=parse_time(item["published_at"]) if item.get("published_at") else None,
                observed_at=parse_time(item["observed_at"]), ingested_at=parse_time(item.get("ingested_at") or item["observed_at"]),
                availability_proof=item.get("availability_proof", "fixture_arrival"), role=item.get("role", "feature"),
                raw=item.get("raw", {}),
            )
            event_id, _, _ = engine.ingest(obs)
            event_ids.append(event_id)
        rows = store.recent_observations(minutes=10_000_000, limit=10000)
        accepted, rejected = replay_guard(rows, decision)

        accepted_tokens: list[str] = []
        rejected_tokens: dict[str, list[str]] = {}
        fixture_tokens: dict[str, dict] = {}
        for item in fixture.get("tokens", []):
            token_key = str(item.get("token_key") or f"{item.get('chain', '')}:{item.get('address', '')}")
            fixture_tokens[token_key] = item
            reasons = token_snapshot_temporal_rejections(item, None, decision, require_first_seen=True)
            if reasons:
                rejected_tokens[token_key] = reasons
            else:
                accepted_tokens.append(token_key)

        accepted_snapshots: list[str] = []
        rejected_snapshots: dict[str, list[str]] = {}
        for index, item in enumerate(fixture.get("snapshots", [])):
            token_key = str(item.get("token_key") or "")
            snapshot_id = str(item.get("snapshot_id") or f"{token_key}#{index}")
            token = fixture_tokens.get(token_key)
            if token is None:
                rejected_snapshots[snapshot_id] = ["token_not_in_fixture"]
                continue
            reasons = token_snapshot_temporal_rejections(token, item, decision, require_first_seen=True)
            if token_key in rejected_tokens:
                reasons.append("token_unavailable_at_decision")
            if reasons:
                rejected_snapshots[snapshot_id] = list(dict.fromkeys(reasons))
            else:
                accepted_snapshots.append(snapshot_id)

        result = {
            "fixture": fixture.get("case_id", Path(fixture_path).stem),
            "decision_at": decision.isoformat(),
            "accepted": [row["source"] for row in accepted],
            "rejected": rejected,
            "accepted_tokens": accepted_tokens,
            "rejected_tokens": rejected_tokens,
            "accepted_snapshots": accepted_snapshots,
            "rejected_snapshots": rejected_snapshots,
            "events": sorted(set(event_ids)),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "init":
        return cmd_init(args.config)
    if args.command == "run":
        return asyncio.run(_run_runtime(args.config, True))
    if args.command == "once":
        return asyncio.run(_run_runtime(args.config, False))
    if args.command == "status":
        return cmd_status(args.config, args.limit)
    if args.command == "doctor":
        return cmd_doctor(args.config, args.online)
    if args.command == "discover-sources":
        return asyncio.run(cmd_discover_sources(args.config, args.force))
    if args.command == "scout-trends":
        return asyncio.run(cmd_scout_trends(args.config, args.force))
    if args.command == "web":
        from .web import serve

        return serve(args.config, args.host, args.port, args.access_token_file)
    if args.command == "replay":
        return cmd_replay(args.fixture, args.decision_at)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
