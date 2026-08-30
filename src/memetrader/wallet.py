from __future__ import annotations

import base64
import copy
import ctypes
import json
import math
import os
import tempfile
import threading
import time
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from solders.hash import Hash
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction


DEVNET_RPC = "https://api.devnet.solana.com"
DEVNET_GENESIS_HASH = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"
TOKEN_PROGRAMS = (
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
)
LAMPORTS_PER_SOL = 1_000_000_000
MAX_DEVNET_TRANSFER_SOL = 0.05


class WalletError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mask(value: str, left: int = 6, right: int = 4) -> str:
    return value if len(value) <= left + right + 1 else f"{value[:left]}…{value[-right:]}"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _data_blob(value: bytes) -> tuple[_DataBlob, Any]:
    buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _dpapi_protect(value: bytes) -> bytes:
    if os.name != "nt":
        raise WalletError("secure wallet storage requires Windows DPAPI")
    source, source_buffer = _data_blob(value)
    target = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptProtectData(
        ctypes.byref(source),
        "memeTrader Solana Devnet wallet",
        None,
        None,
        None,
        0x1,
        ctypes.byref(target),
    )
    del source_buffer
    if not ok:
        raise WalletError("Windows could not encrypt the wallet")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def _dpapi_unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise WalletError("secure wallet storage requires Windows DPAPI")
    source, source_buffer = _data_blob(value)
    target = _DataBlob()
    description = wintypes.LPWSTR()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(source),
        ctypes.byref(description),
        None,
        None,
        None,
        0x1,
        ctypes.byref(target),
    )
    del source_buffer
    if not ok:
        raise WalletError("Windows could not decrypt the wallet")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)
        if description:
            kernel32.LocalFree(description)


class SolanaDevnetWallet:
    """Local-only signer plus read-only public view for Solana Devnet.

    The strategy Runtime never receives this object. Automated mainnet execution
    remains locked; signed actions are explicit requests to the loopback Web API.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.metadata_path = self.directory / "wallet.json"
        self.vault_path = self.directory / "wallet.dpapi"
        self.execution_log_path = self.directory / "devnet_transactions.jsonl"
        self._lock = threading.RLock()
        self._cache: dict[str, Any] | None = None
        self._cache_at = 0.0

    def _append_execution(self, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        line = json.dumps({**payload, "recorded_at": _now()}, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock, self.execution_log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    @property
    def secure_storage_available(self) -> bool:
        return os.name == "nt"

    @staticmethod
    def _write_atomic(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(prefix=".wallet-", dir=path.parent, delete=False)
        temp = Path(handle.name)
        try:
            with handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _metadata(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        address = str(value.get("address") or "").strip()
        if not address:
            return None
        try:
            Pubkey.from_string(address)
        except ValueError:
            return None
        return {
            "address": address,
            "alias": str(value.get("alias") or "Devnet wallet")[:60],
            "network": "devnet",
            "connected_at": value.get("connected_at"),
        }

    def _keypair(self) -> Keypair:
        metadata = self._metadata()
        if metadata is None or not self.vault_path.is_file():
            raise WalletError("no Devnet signer is connected")
        try:
            protected = base64.b64decode(self.vault_path.read_bytes(), validate=True)
            secret = bytearray(_dpapi_unprotect(protected))
            keypair = Keypair.from_bytes(bytes(secret))
        except WalletError:
            raise
        except Exception as exc:
            raise WalletError("the encrypted wallet cannot be opened") from exc
        finally:
            if "secret" in locals():
                secret[:] = b"\x00" * len(secret)
        if str(keypair.pubkey()) != metadata["address"]:
            raise WalletError("wallet metadata does not match the encrypted signer")
        return keypair

    def connect(self, private_key: Any, alias: Any = "Devnet wallet") -> dict[str, Any]:
        if not self.secure_storage_available:
            raise WalletError("secure wallet storage is unavailable on this host")
        text = str(private_key or "").strip()
        if not 40 <= len(text) <= 200:
            raise WalletError("private key is not a valid Solana keypair")
        try:
            keypair = Keypair.from_base58_string(text)
        except Exception as exc:
            raise WalletError("private key is not a valid Solana keypair") from exc
        label = str(alias or "Devnet wallet").strip()[:60] or "Devnet wallet"
        secret = bytearray(bytes(keypair))
        try:
            protected = _dpapi_protect(bytes(secret))
        finally:
            secret[:] = b"\x00" * len(secret)
            text = ""
        metadata = {
            "version": 1,
            "network": "devnet",
            "address": str(keypair.pubkey()),
            "alias": label,
            "connected_at": _now(),
        }
        with self._lock:
            self._write_atomic(self.vault_path, base64.b64encode(protected))
            self._write_atomic(
                self.metadata_path,
                (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
            self._cache = None
            self._cache_at = 0.0
        return self.snapshot(public_view=False, refresh=True)

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            self.vault_path.unlink(missing_ok=True)
            self.metadata_path.unlink(missing_ok=True)
            self._cache = None
            self._cache_at = 0.0
        return self.snapshot(public_view=False, refresh=True)

    @staticmethod
    def _rpc(method: str, params: list[Any], timeout: float = 10.0) -> Any:
        try:
            response = httpx.post(
                DEVNET_RPC,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=timeout,
                headers={"User-Agent": "memeTrader/0.6.3"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WalletError("Solana Devnet RPC is unavailable") from exc
        if payload.get("error"):
            message = str((payload.get("error") or {}).get("message") or "RPC request failed")
            raise WalletError(message[:200])
        return payload.get("result")

    def _assert_devnet(self) -> None:
        genesis = str(self._rpc("getGenesisHash", []) or "")
        if genesis != DEVNET_GENESIS_HASH:
            raise WalletError("RPC cluster identity is not the approved Solana Devnet")

    def _remote_snapshot(self, metadata: dict[str, Any]) -> dict[str, Any]:
        address = metadata["address"]
        self._assert_devnet()
        balance_result = self._rpc("getBalance", [address, {"commitment": "confirmed"}]) or {}
        lamports = int(balance_result.get("value") or 0)
        tokens: list[dict[str, Any]] = []
        seen_accounts: set[str] = set()
        for program_id in TOKEN_PROGRAMS:
            result = self._rpc(
                "getTokenAccountsByOwner",
                [address, {"programId": program_id}, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            ) or {}
            for row in result.get("value") or []:
                account = str(row.get("pubkey") or "")
                if not account or account in seen_accounts:
                    continue
                seen_accounts.add(account)
                info = (((row.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
                token_amount = info.get("tokenAmount") or {}
                amount = str(token_amount.get("uiAmountString") or "0")
                if amount in {"0", "0.0"}:
                    continue
                tokens.append(
                    {
                        "mint": str(info.get("mint") or ""),
                        "token_account": account,
                        "amount": amount,
                        "decimals": int(token_amount.get("decimals") or 0),
                        "program": "token-2022" if program_id.startswith("Tokenz") else "spl-token",
                    }
                )
        signatures = self._rpc(
            "getSignaturesForAddress", [address, {"limit": 12, "commitment": "confirmed"}]
        ) or []
        transactions = []
        for row in signatures:
            signature = str(row.get("signature") or "")
            if not signature:
                continue
            status = str(row.get("confirmationStatus") or "processed")
            transactions.append(
                {
                    "signature": signature,
                    "slot": row.get("slot"),
                    "block_time": (
                        datetime.fromtimestamp(int(row["blockTime"]), timezone.utc).isoformat().replace("+00:00", "Z")
                        if row.get("blockTime") is not None
                        else None
                    ),
                    "status": "failed" if row.get("err") is not None else status,
                    "success": row.get("err") is None,
                    "memo": row.get("memo"),
                    "error": None if row.get("err") is None else "transaction_failed",
                }
            )
        return {
            "configured": True,
            "view_scope": "local_full",
            "wallet": {
                **metadata,
                "address_display": address,
                "explorer_url": f"https://explorer.solana.com/address/{address}?cluster=devnet",
                "secret_stored": self.vault_path.is_file(),
                "secret_exportable": False,
                "storage": "Windows DPAPI / current user / current computer",
            },
            "balances": {
                "lamports": lamports,
                "sol": lamports / LAMPORTS_PER_SOL,
                "token_count": len(tokens),
                "tokens": tokens,
            },
            "transactions": transactions,
            "rpc": {
                "status": "ok",
                "cluster": "devnet",
                "genesis_hash": DEVNET_GENESIS_HASH,
                "host": "api.devnet.solana.com",
                "last_ok_at": _now(),
            },
            "signing": {
                "attached": self.vault_path.is_file(),
                "available": self.vault_path.is_file() and self.secure_storage_available,
                "local_only": True,
                "secret_exportable": False,
            },
            "execution": {
                "network": "devnet",
                "manual_devnet_transactions": True,
                "automated_strategy": False,
                "mainnet_enabled": False,
                "mainnet_locked": True,
                "max_transfer_sol": MAX_DEVNET_TRANSFER_SOL,
            },
            "as_of": _now(),
            "stale": False,
        }

    @staticmethod
    def _empty_snapshot() -> dict[str, Any]:
        return {
            "configured": False,
            "view_scope": "local_full",
            "wallet": None,
            "balances": {"lamports": None, "sol": None, "token_count": 0, "tokens": []},
            "transactions": [],
            "rpc": {"status": "not_configured", "cluster": "devnet", "host": "api.devnet.solana.com"},
            "signing": {"attached": False, "available": False, "local_only": True, "secret_exportable": False},
            "execution": {
                "network": "devnet",
                "manual_devnet_transactions": True,
                "automated_strategy": False,
                "mainnet_enabled": False,
                "mainnet_locked": True,
                "max_transfer_sol": MAX_DEVNET_TRANSFER_SOL,
            },
            "as_of": _now(),
            "stale": False,
        }

    @staticmethod
    def _public_copy(snapshot: dict[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(snapshot)
        value["view_scope"] = "public_masked"
        wallet = value.get("wallet")
        if isinstance(wallet, dict):
            address = str(wallet.pop("address", ""))
            wallet["address_display"] = _mask(address)
            wallet.pop("explorer_url", None)
            wallet.pop("storage", None)
        for token in (value.get("balances") or {}).get("tokens") or []:
            token["mint_display"] = _mask(str(token.pop("mint", "")))
            token.pop("token_account", None)
        for transaction in value.get("transactions") or []:
            transaction["signature_display"] = _mask(str(transaction.pop("signature", "")))
        value["signing"]["available"] = False
        value["execution"]["manual_devnet_transactions"] = False
        return value

    def snapshot(self, *, public_view: bool, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            metadata = self._metadata()
            if metadata is None:
                value = self._empty_snapshot()
            elif not refresh and self._cache is not None and time.monotonic() - self._cache_at < 20:
                value = copy.deepcopy(self._cache)
            else:
                try:
                    value = self._remote_snapshot(metadata)
                    self._cache = copy.deepcopy(value)
                    self._cache_at = time.monotonic()
                except WalletError as exc:
                    if self._cache is not None:
                        value = copy.deepcopy(self._cache)
                        value["stale"] = True
                        value["rpc"] = {**value["rpc"], "status": "stale", "error": str(exc)}
                        value["as_of"] = _now()
                    else:
                        value = self._empty_snapshot()
                        value["configured"] = True
                        value["wallet"] = {
                            **metadata,
                            "address_display": metadata["address"],
                            "secret_stored": self.vault_path.is_file(),
                            "secret_exportable": False,
                        }
                        value["rpc"] = {"status": "error", "cluster": "devnet", "host": "api.devnet.solana.com", "error": str(exc)}
                        value["stale"] = True
            return self._public_copy(value) if public_view else value

    def _confirm(self, signature: str) -> dict[str, Any]:
        status = "submitted"
        error = None
        for _ in range(12):
            result = self._rpc(
                "getSignatureStatuses", [[signature], {"searchTransactionHistory": True}], timeout=5
            ) or {}
            row = ((result.get("value") or [None]) + [None])[0]
            if isinstance(row, dict):
                if row.get("err") is not None:
                    status, error = "failed", "transaction_failed"
                    break
                status = str(row.get("confirmationStatus") or "processed")
                if status in {"confirmed", "finalized"}:
                    break
            time.sleep(0.5)
        return {"status": status, "success": error is None and status in {"confirmed", "finalized"}, "error": error}

    def request_airdrop(self, sol: Any = 0.1) -> dict[str, Any]:
        try:
            amount = float(sol)
        except (TypeError, ValueError):
            raise WalletError("airdrop amount must be a number") from None
        if not math.isfinite(amount) or not 0 < amount <= 1:
            raise WalletError("airdrop amount must be between 0 and 1 Devnet SOL")
        metadata = self._metadata()
        if metadata is None:
            raise WalletError("no Devnet wallet is connected")
        self._assert_devnet()
        signature = str(
            self._rpc(
                "requestAirdrop",
                [metadata["address"], int(amount * LAMPORTS_PER_SOL), {"commitment": "confirmed"}],
            )
            or ""
        )
        if not signature:
            raise WalletError("Devnet faucet did not return a transaction signature")
        result = {"signature": signature, **self._confirm(signature)}
        result["network"] = "devnet"
        result["explorer_url"] = f"https://explorer.solana.com/tx/{signature}?cluster=devnet"
        self._append_execution(
            {
                "intent_id": uuid.uuid4().hex,
                "kind": "airdrop",
                "network": "devnet",
                "recipient": metadata["address"],
                "lamports": int(amount * LAMPORTS_PER_SOL),
                "signature": signature,
                "state": result["status"],
            }
        )
        with self._lock:
            self._cache = None
        return result

    def transfer(self, recipient: Any, sol: Any, confirm_phrase: Any) -> dict[str, Any]:
        if str(confirm_phrase or "") != "DEVNET ONLY":
            raise WalletError("confirmation phrase must be DEVNET ONLY")
        try:
            amount = float(sol)
        except (TypeError, ValueError):
            raise WalletError("transfer amount must be a number") from None
        if not math.isfinite(amount) or not 0 < amount <= MAX_DEVNET_TRANSFER_SOL:
            raise WalletError(f"transfer amount must be between 0 and {MAX_DEVNET_TRANSFER_SOL} Devnet SOL")
        keypair = self._keypair()
        recipient_text = str(recipient or "").strip() or str(keypair.pubkey())
        try:
            recipient_key = Pubkey.from_string(recipient_text)
        except ValueError:
            raise WalletError("recipient is not a valid Solana address") from None
        self._assert_devnet()
        lamports = int(amount * LAMPORTS_PER_SOL)
        balance = self._rpc("getBalance", [str(keypair.pubkey()), {"commitment": "confirmed"}]) or {}
        blockhash_result = self._rpc("getLatestBlockhash", [{"commitment": "confirmed"}]) or {}
        blockhash_value = blockhash_result.get("value") or {}
        blockhash = str(blockhash_value.get("blockhash") or "")
        last_valid_block_height = blockhash_value.get("lastValidBlockHeight")
        if not blockhash:
            raise WalletError("Devnet did not return a recent blockhash")
        instruction = transfer(
            TransferParams(from_pubkey=keypair.pubkey(), to_pubkey=recipient_key, lamports=lamports)
        )
        transaction = Transaction([keypair], Message([instruction], keypair.pubkey()), Hash.from_string(blockhash))
        expected_signature = str(transaction.signatures[0])
        encoded = base64.b64encode(bytes(transaction)).decode("ascii")
        encoded_message = base64.b64encode(bytes(transaction.message)).decode("ascii")
        fee_result = self._rpc("getFeeForMessage", [encoded_message, {"commitment": "confirmed"}]) or {}
        fee_lamports = int(fee_result.get("value") or 0)
        if fee_lamports <= 0:
            raise WalletError("Devnet did not return a valid transaction fee")
        if int(balance.get("value") or 0) < lamports + fee_lamports:
            raise WalletError("insufficient Devnet SOL for the transfer and fee")
        simulation = self._rpc(
            "simulateTransaction",
            [encoded, {"encoding": "base64", "commitment": "confirmed", "sigVerify": True}],
        ) or {}
        simulation_error = (simulation.get("value") or {}).get("err")
        if simulation_error is not None:
            raise WalletError("Devnet transaction simulation failed")
        intent_id = uuid.uuid4().hex
        self._append_execution(
            {
                "intent_id": intent_id,
                "kind": "native_transfer",
                "network": "devnet",
                "payer": str(keypair.pubkey()),
                "recipient": recipient_text,
                "lamports": lamports,
                "fee_lamports": fee_lamports,
                "signature": expected_signature,
                "recent_blockhash": blockhash,
                "last_valid_block_height": last_valid_block_height,
                "state": "simulated",
            }
        )
        signature = str(
            self._rpc(
                "sendTransaction",
                [
                    encoded,
                    {
                        "encoding": "base64",
                        "skipPreflight": False,
                        "preflightCommitment": "confirmed",
                        "maxRetries": 3,
                    },
                ],
            )
            or ""
        )
        if not signature:
            raise WalletError("Devnet did not return a transaction signature")
        if signature != expected_signature:
            raise WalletError("Devnet returned an unexpected transaction signature")
        confirmation = self._confirm(signature)
        receipt_verified = False
        receipt_fee = None
        receipt_slot = None
        if confirmation.get("success"):
            receipt = None
            for _ in range(8):
                receipt = self._rpc(
                    "getTransaction",
                    [
                        signature,
                        {
                            "commitment": "confirmed",
                            "encoding": "jsonParsed",
                            "maxSupportedTransactionVersion": 0,
                        },
                    ],
                )
                if isinstance(receipt, dict):
                    break
                time.sleep(0.5)
            if isinstance(receipt, dict):
                meta = receipt.get("meta") or {}
                message = ((receipt.get("transaction") or {}).get("message") or {})
                instructions = message.get("instructions") or []
                transfer_match = any(
                    isinstance(item, dict)
                    and item.get("program") == "system"
                    and ((item.get("parsed") or {}).get("type") == "transfer")
                    and str((((item.get("parsed") or {}).get("info") or {}).get("source") or "")) == str(keypair.pubkey())
                    and str((((item.get("parsed") or {}).get("info") or {}).get("destination") or "")) == recipient_text
                    and int((((item.get("parsed") or {}).get("info") or {}).get("lamports") or -1)) == lamports
                    for item in instructions
                )
                receipt_verified = meta.get("err") is None and transfer_match
                receipt_fee = meta.get("fee")
                receipt_slot = receipt.get("slot")
        result = {
            "signature": signature,
            "network": "devnet",
            "recipient": recipient_text,
            "sol": amount,
            "simulation": "passed",
            **confirmation,
            "receipt_verified": receipt_verified,
            "fee_lamports": receipt_fee if receipt_fee is not None else fee_lamports,
            "slot": receipt_slot,
            "explorer_url": f"https://explorer.solana.com/tx/{signature}?cluster=devnet",
        }
        self._append_execution(
            {
                "intent_id": intent_id,
                "kind": "native_transfer",
                "network": "devnet",
                "payer": str(keypair.pubkey()),
                "recipient": recipient_text,
                "lamports": lamports,
                "fee_lamports": result["fee_lamports"],
                "signature": signature,
                "state": result["status"],
                "receipt_verified": receipt_verified,
                "slot": receipt_slot,
            }
        )
        with self._lock:
            self._cache = None
        return result
