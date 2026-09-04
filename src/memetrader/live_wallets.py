from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
import sqlite3
import tempfile
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from .wallet import _dpapi_protect, _dpapi_unprotect


MAINNET_RPC = "https://api.mainnet-beta.solana.com"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SLIPPAGE_BPS = 400
BUY_USDC_RAW = 20_000_000


class LiveWalletError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SolanaLiveWalletManager:
    """Local multi-wallet signer that mirrors future Paper actions on mainnet."""

    def __init__(self, root: str | Path, database: str | Path):
        self.root = Path(root)
        self.database = Path(database)
        self.directory = self.root / "data" / "chain_live"
        self.state_path = self.directory / "wallets.json"
        self.execution_log_path = self.directory / "executions.jsonl"
        self.rpc_url = os.environ.get("MEMETRADER_SOLANA_RPC_URL", MAINNET_RPC)
        self.jupiter_api_key = os.environ.get("JUPITER_API_KEY", "").strip()
        self.jupiter_base = (
            "https://api.jup.ag/swap/v1" if self.jupiter_api_key
            else "https://lite-api.jup.ag/swap/v1"
        )
        self._lock = threading.RLock()
        self._balance_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def _write_atomic(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(prefix=".live-wallet-", dir=path.parent, delete=False)
        temp = Path(handle.name)
        try:
            with handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {"version": 1, "wallets": [], "positions": {}}
        value.setdefault("wallets", [])
        value.setdefault("positions", {})
        return value

    def _write(self, value: dict[str, Any]) -> None:
        self._write_atomic(
            self.state_path,
            (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )

    def _append_execution(self, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        line = json.dumps({**payload, "recorded_at": _now()}, ensure_ascii=False, separators=(",", ":"))
        with self.execution_log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _parse_keypair(value: Any) -> Keypair:
        text = str(value or "").strip()
        try:
            if text.startswith("["):
                raw = bytes(int(item) for item in json.loads(text))
                return Keypair.from_bytes(raw)
            return Keypair.from_base58_string(text)
        except Exception as exc:
            raise LiveWalletError("私钥格式无效；支持 Solana base58 或 64 字节 JSON 数组") from exc

    def _vault_path(self, wallet_id: str) -> Path:
        return self.directory / f"wallet-{wallet_id}.dpapi"

    def _keypair(self, wallet_id: str) -> Keypair:
        try:
            protected = base64.b64decode(self._vault_path(wallet_id).read_bytes(), validate=True)
            secret = bytearray(_dpapi_unprotect(protected))
            return Keypair.from_bytes(bytes(secret))
        except Exception as exc:
            raise LiveWalletError("本机无法解密该钱包") from exc
        finally:
            if "secret" in locals():
                secret[:] = b"\x00" * len(secret)

    def _connect_db(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.database.as_posix()}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _active_version(self) -> str:
        with self._connect_db() as connection:
            row = connection.execute(
                "SELECT definition_version FROM chain_meme_trader_v6_activations "
                "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise LiveWalletError("当前没有运行中的策略版本")
        return str(row["definition_version"])

    def _strategy_exists(self, strategy_id: str, version: str) -> bool:
        if version != self._active_version():
            return False
        from .store import Store

        with self._connect_db() as connection:
            row = connection.execute(
                "SELECT definition_json FROM chain_meme_trader_registrations WHERE definition_version=?",
                (version,),
            ).fetchone()
            if row is None:
                return False
            definition = Store.chain_meme_trader_effective_definition_from_connection(
                connection, version, row["definition_json"],
            )
        return any(
            str(policy.get("arm_id")) == strategy_id
            and bool(policy.get("forward_enabled", True))
            for policy in definition.get("policies", [])
        )

    def _rpc(self, method: str, params: list[Any], timeout: float = 15.0) -> Any:
        try:
            response = httpx.post(
                self.rpc_url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=timeout,
                headers={"User-Agent": "ChainMemeTrader/0.6.3"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LiveWalletError("Solana 主网节点暂时不可用") from exc
        if payload.get("error"):
            raise LiveWalletError(str((payload.get("error") or {}).get("message") or "Solana RPC 失败")[:240])
        return payload.get("result")

    def _token_balance_raw(self, owner: str, mint: str) -> int:
        result = self._rpc(
            "getTokenAccountsByOwner",
            [owner, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}],
        ) or {}
        total = 0
        for row in result.get("value") or []:
            info = (((row.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
            total += int((info.get("tokenAmount") or {}).get("amount") or 0)
        return total

    def _balances(self, wallet: dict[str, Any], refresh: bool = False) -> dict[str, Any]:
        wallet_id = str(wallet["id"])
        cached = self._balance_cache.get(wallet_id)
        if not refresh and cached is not None and time.monotonic() - cached[0] < 15:
            return copy.deepcopy(cached[1])
        address = str(wallet["address"])
        try:
            sol = int((self._rpc("getBalance", [address, {"commitment": "confirmed"}]) or {}).get("value") or 0)
            usdc = self._token_balance_raw(address, USDC_MINT)
            value = {"status": "ok", "sol": sol / 1_000_000_000, "usdc": usdc / 1_000_000, "as_of": _now()}
        except LiveWalletError as exc:
            value = {"status": "error", "sol": None, "usdc": None, "error": str(exc), "as_of": _now()}
        self._balance_cache[wallet_id] = (time.monotonic(), copy.deepcopy(value))
        return value

    def connect(self, private_key: Any, alias: Any, strategy_id: Any) -> dict[str, Any]:
        version = self._active_version()
        strategy = str(strategy_id or "").strip()
        if not self._strategy_exists(strategy, version):
            raise LiveWalletError("请选择当前正在运行的策略")
        keypair = self._parse_keypair(private_key)
        address = str(keypair.pubkey())
        wallet_id = hashlib.sha256(address.encode("ascii")).hexdigest()[:16]
        secret = bytearray(bytes(keypair))
        try:
            protected = _dpapi_protect(bytes(secret))
        finally:
            secret[:] = b"\x00" * len(secret)
            private_key = None
        with self._lock:
            state = self._read()
            self._write_atomic(self._vault_path(wallet_id), base64.b64encode(protected))
            existing = next((item for item in state["wallets"] if item.get("id") == wallet_id), None)
            row = existing if existing is not None else {}
            row.update({
                "id": wallet_id,
                "alias": str(alias or "实盘钱包").strip()[:60] or "实盘钱包",
                "address": address,
                "strategy_id": strategy,
                "definition_version": version,
                "enabled": False,
                "connected_at": row.get("connected_at") or _now(),
                "last_trade_id": row.get("last_trade_id"),
                "pending": row.get("pending"),
                "status": "已连接",
                "error": None,
            })
            if existing is None:
                state["wallets"].append(row)
            self._write(state)
            self._balance_cache.pop(wallet_id, None)
        return self.snapshot(refresh=True)

    def bind(self, wallet_id: Any, strategy_id: Any) -> dict[str, Any]:
        version = self._active_version()
        wallet_key = str(wallet_id or "")
        strategy = str(strategy_id or "").strip()
        if not self._strategy_exists(strategy, version):
            raise LiveWalletError("请选择当前正在运行的策略")
        with self._lock:
            state = self._read()
            wallet = next((item for item in state["wallets"] if item.get("id") == wallet_key), None)
            if wallet is None:
                raise LiveWalletError("钱包不存在")
            if wallet.get("enabled"):
                raise LiveWalletError("请先停止该钱包的实盘交易")
            wallet.update({"strategy_id": strategy, "definition_version": version, "last_trade_id": None, "pending": None})
            self._write(state)
        return self.snapshot()

    def set_enabled(self, wallet_id: Any, enabled: Any) -> dict[str, Any]:
        wallet_key = str(wallet_id or "")
        target = bool(enabled)
        with self._lock:
            state = self._read()
            wallet = next((item for item in state["wallets"] if item.get("id") == wallet_key), None)
            if wallet is None:
                raise LiveWalletError("钱包不存在")
            if target:
                version = self._active_version()
                if wallet.get("pending"):
                    raise LiveWalletError("该钱包有一笔待确认交易，不能重新启动")
                if not self._strategy_exists(str(wallet.get("strategy_id") or ""), version):
                    raise LiveWalletError("绑定策略已不在当前运行版本")
                balance = self._balances(wallet, refresh=True)
                if balance.get("status") != "ok":
                    raise LiveWalletError(str(balance.get("error") or "无法读取钱包余额"))
                if float(balance.get("usdc") or 0) < 20:
                    raise LiveWalletError("钱包 USDC 不足 20，无法启动实盘")
                if float(balance.get("sol") or 0) <= 0:
                    raise LiveWalletError("钱包没有 SOL，无法支付链上费用")
                if wallet.get("last_trade_id") is None or wallet.get("definition_version") != version:
                    with self._connect_db() as connection:
                        frontier = int(connection.execute(
                            "SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_trades WHERE definition_version=?",
                            (version,),
                        ).fetchone()[0])
                    wallet["last_trade_id"] = frontier
                wallet.update({"definition_version": version, "enabled": True, "status": "实盘运行中", "error": None})
            else:
                wallet.update({"enabled": False, "status": "已停止"})
            self._write(state)
        return self.snapshot(refresh=True)

    def snapshot(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            wallets = []
            for item in state["wallets"]:
                public = {key: value for key, value in item.items() if key != "pending"}
                public["address_display"] = f"{str(item['address'])[:6]}…{str(item['address'])[-4:]}"
                public["balance"] = self._balances(item, refresh=refresh)
                public["pending_transaction"] = bool(item.get("pending"))
                public["secret_stored"] = self._vault_path(str(item["id"])).is_file()
                wallets.append(public)
        return {
            "status": "ok",
            "network": "solana-mainnet",
            "wallets": wallets,
            "running": sum(bool(item.get("enabled")) for item in wallets),
            "storage": "Windows 本机加密存储",
            "as_of": _now(),
        }

    def detail(
        self, wallet_id: Any, *, refresh: bool = False, execution_limit: int = 20,
    ) -> dict[str, Any]:
        """Return a safe, read-only wallet view without signer material."""
        wallet_key = str(wallet_id or "")
        try:
            limit = int(execution_limit)
        except (TypeError, ValueError) as exc:
            raise LiveWalletError("操作记录数量无效") from exc
        if not 1 <= limit <= 100:
            raise LiveWalletError("操作记录数量必须在 1 到 100 之间")
        with self._lock:
            state = self._read()
            wallet = next((item for item in state["wallets"] if item.get("id") == wallet_key), None)
            if wallet is None:
                raise LiveWalletError("钱包不存在")
            executions: deque[dict[str, Any]] = deque(maxlen=limit)
            try:
                with self.execution_log_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(item, dict) or item.get("wallet_id") != wallet_key:
                            continue
                        executions.append({
                            key: item[key] for key in (
                                "recorded_at", "paper_trade_id", "side", "status", "amount_raw",
                            ) if key in item
                        })
            except OSError:
                pass
            address = str(wallet["address"])
            return {
                "status": "ok",
                "network": "solana-mainnet",
                "wallet": {
                    "id": wallet_key,
                    "alias": str(wallet.get("alias") or "实盘钱包"),
                    "address_display": f"{address[:6]}…{address[-4:]}",
                    "strategy_id": str(wallet.get("strategy_id") or ""),
                    "definition_version": str(wallet.get("definition_version") or ""),
                    "enabled": bool(wallet.get("enabled")),
                    "status": str(wallet.get("status") or ""),
                    "connected_at": wallet.get("connected_at"),
                    "last_trade_id": wallet.get("last_trade_id"),
                    "pending_transaction": bool(wallet.get("pending")),
                    "secret_stored": self._vault_path(wallet_key).is_file(),
                },
                "balance": self._balances(wallet, refresh=refresh),
                "executions": list(reversed(executions)),
                "as_of": _now(),
            }

    def _jupiter_headers(self) -> dict[str, str]:
        headers = {"User-Agent": "ChainMemeTrader/0.6.3"}
        if self.jupiter_api_key:
            headers["x-api-key"] = self.jupiter_api_key
        return headers

    def _quote(self, input_mint: str, output_mint: str, amount_raw: int) -> dict[str, Any]:
        try:
            response = httpx.get(
                f"{self.jupiter_base}/quote",
                params={
                    "inputMint": input_mint, "outputMint": output_mint,
                    "amount": str(int(amount_raw)), "slippageBps": str(SLIPPAGE_BPS),
                    "swapMode": "ExactIn",
                },
                headers=self._jupiter_headers(), timeout=20,
            )
            response.raise_for_status()
            quote = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LiveWalletError("Jupiter 当前没有返回可用报价") from exc
        if quote.get("error") or not quote.get("outAmount"):
            raise LiveWalletError(str(quote.get("error") or "Jupiter 当前没有可用路线")[:240])
        return quote

    def _swap_transaction(self, quote: dict[str, Any], address: str) -> str:
        try:
            response = httpx.post(
                f"{self.jupiter_base}/swap",
                json={
                    "quoteResponse": quote,
                    "userPublicKey": address,
                    "wrapAndUnwrapSol": True,
                    "dynamicComputeUnitLimit": True,
                },
                headers={**self._jupiter_headers(), "Content-Type": "application/json"},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LiveWalletError("Jupiter 无法生成交换交易") from exc
        transaction = str(payload.get("swapTransaction") or "")
        if not transaction:
            raise LiveWalletError(str(payload.get("error") or "Jupiter 未返回交易")[:240])
        return transaction

    def _sign_and_send(self, wallet_id: str, transaction_b64: str) -> str:
        keypair = self._keypair(wallet_id)
        try:
            transaction = VersionedTransaction.from_bytes(base64.b64decode(transaction_b64))
            signed = VersionedTransaction(transaction.message, [keypair])
            encoded = base64.b64encode(bytes(signed)).decode("ascii")
        except Exception as exc:
            raise LiveWalletError("Jupiter 交易签名失败") from exc
        signature = self._rpc(
            "sendTransaction",
            [encoded, {"encoding": "base64", "skipPreflight": False, "preflightCommitment": "confirmed", "maxRetries": 3}],
            timeout=30,
        )
        if not signature:
            raise LiveWalletError("Solana 节点没有返回交易签名")
        return str(signature)

    def _confirm(self, signature: str) -> bool | None:
        for _ in range(24):
            result = self._rpc("getSignatureStatuses", [[signature], {"searchTransactionHistory": True}], timeout=8) or {}
            row = ((result.get("value") or [None]) + [None])[0]
            if isinstance(row, dict):
                if row.get("err") is not None:
                    return False
                if str(row.get("confirmationStatus") or "") in {"confirmed", "finalized"}:
                    return True
            time.sleep(0.5)
        return None

    def _next_trade(self, wallet: dict[str, Any]) -> dict[str, Any] | None:
        with self._connect_db() as connection:
            row = connection.execute(
                "SELECT id,arm_id,shadow_cohort_id,token_id,side,execution_fill_id,created_at "
                "FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=? AND id>? "
                "ORDER BY id LIMIT 1",
                (
                    str(wallet["definition_version"]), str(wallet["strategy_id"]),
                    int(wallet.get("last_trade_id") or 0),
                ),
            ).fetchone()
            if row is None:
                return None
            trade = dict(row)
            if trade["side"] == "SELL" and trade.get("execution_fill_id") is not None:
                ratio = connection.execute(
                    "SELECT CAST(f.input_amount_raw AS REAL)/NULLIF("
                    "CAST(p.initial_amount_raw AS REAL)-COALESCE(("
                    "SELECT SUM(CAST(prior.input_amount_raw AS REAL)) FROM "
                    "chain_meme_trader_fills prior WHERE "
                    "prior.definition_version=f.definition_version "
                    "AND prior.arm_id=f.arm_id "
                    "AND prior.shadow_cohort_id=f.shadow_cohort_id "
                    "AND prior.side='SELL' AND prior.id<f.id),0),0) "
                    "FROM chain_meme_trader_fills f JOIN chain_meme_trader_positions p "
                    "ON p.definition_version=f.definition_version AND p.arm_id=f.arm_id "
                    "AND p.shadow_cohort_id=f.shadow_cohort_id WHERE f.id=?",
                    (int(trade["execution_fill_id"]),),
                ).fetchone()[0]
                trade["sell_fraction"] = min(1.0, max(0.0, float(ratio or 1.0)))
        return trade

    def _stop_with_error(self, state: dict[str, Any], wallet: dict[str, Any], message: str) -> None:
        wallet.update({"enabled": False, "status": "需要处理", "error": message[:240]})
        self._write(state)

    def sync_once(self) -> int:
        completed = 0
        with self._lock:
            state = self._read()
            for wallet in state["wallets"]:
                if not wallet.get("enabled") or wallet.get("pending"):
                    continue
                trade = self._next_trade(wallet)
                if trade is None:
                    continue
                token_id = str(trade["token_id"])
                if not token_id.startswith("solana:"):
                    wallet["last_trade_id"] = int(trade["id"])
                    continue
                mint = token_id.split(":", 1)[1]
                position_key = str(trade["shadow_cohort_id"])
                live_positions = state["positions"].setdefault(str(wallet["id"]), {})
                try:
                    if trade["side"] == "BUY":
                        amount_raw = BUY_USDC_RAW
                        input_mint, output_mint = USDC_MINT, mint
                        before = self._token_balance_raw(str(wallet["address"]), mint)
                    else:
                        held = int((live_positions.get(position_key) or {}).get("amount_raw") or 0)
                        if held <= 0:
                            wallet["last_trade_id"] = int(trade["id"])
                            self._append_execution({"wallet_id": wallet["id"], "paper_trade_id": trade["id"], "status": "ignored_no_live_position"})
                            continue
                        amount_raw = max(1, math.floor(held * float(trade.get("sell_fraction") or 1.0)))
                        input_mint, output_mint = mint, USDC_MINT
                        before = held
                    quote = self._quote(input_mint, output_mint, amount_raw)
                    transaction = self._swap_transaction(quote, str(wallet["address"]))
                    wallet["pending"] = {
                        "paper_trade_id": int(trade["id"]), "side": str(trade["side"]),
                        "cohort_id": position_key, "mint": mint, "amount_raw": amount_raw,
                        "before_raw": before, "prepared_at": _now(), "signature": None,
                    }
                    self._write(state)
                    signature = self._sign_and_send(str(wallet["id"]), transaction)
                    wallet["pending"]["signature"] = signature
                    self._write(state)
                    confirmed = self._confirm(signature)
                    if confirmed is not True:
                        self._stop_with_error(state, wallet, "交易失败或确认超时，已自动暂停")
                        self._append_execution({"wallet_id": wallet["id"], "paper_trade_id": trade["id"], "side": trade["side"], "status": "failed_or_unknown", "signature": signature})
                        continue
                    if trade["side"] == "BUY":
                        after = self._token_balance_raw(str(wallet["address"]), mint)
                        acquired = max(0, after - before)
                        if acquired <= 0:
                            acquired = int(quote["outAmount"])
                        live_positions[position_key] = {"token_id": token_id, "amount_raw": acquired}
                    else:
                        remaining = max(0, before - amount_raw)
                        if remaining:
                            live_positions[position_key]["amount_raw"] = remaining
                        else:
                            live_positions.pop(position_key, None)
                    wallet.update({"last_trade_id": int(trade["id"]), "pending": None, "status": "实盘运行中", "error": None})
                    self._write(state)
                    self._append_execution({"wallet_id": wallet["id"], "paper_trade_id": trade["id"], "side": trade["side"], "status": "confirmed", "signature": signature, "amount_raw": amount_raw})
                    self._balance_cache.pop(str(wallet["id"]), None)
                    completed += 1
                except LiveWalletError as exc:
                    self._stop_with_error(state, wallet, str(exc))
                    self._append_execution({"wallet_id": wallet["id"], "paper_trade_id": trade["id"], "side": trade["side"], "status": "error", "error": str(exc)})
        return completed
