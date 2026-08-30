from __future__ import annotations

import base64
import json
import os

import pytest
from solders.hash import Hash
from solders.keypair import Keypair
from solders.transaction import Transaction

import memetrader.wallet as wallet_module
from memetrader.wallet import DEVNET_GENESIS_HASH, SolanaDevnetWallet, WalletError


def _portable_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SolanaDevnetWallet, "secure_storage_available", property(lambda self: True))
    monkeypatch.setattr(wallet_module, "_dpapi_protect", lambda value: bytes(reversed(value)))
    monkeypatch.setattr(wallet_module, "_dpapi_unprotect", lambda value: bytes(reversed(value)))


def _read_rpc(address: str):
    def rpc(method, params, timeout=10):
        if method == "getGenesisHash":
            return DEVNET_GENESIS_HASH
        if method == "getBalance":
            return {"context": {"slot": 1}, "value": 2_000_000_000}
        if method == "getTokenAccountsByOwner":
            if str(params[1]["programId"]).startswith("Tokenz"):
                return {"value": []}
            return {
                "value": [
                    {
                        "pubkey": "TokenAccount1111111111111111111111111111111",
                        "account": {
                            "data": {
                                "parsed": {
                                    "info": {
                                        "mint": "Mint111111111111111111111111111111111111",
                                        "tokenAmount": {"uiAmountString": "12.5", "decimals": 6},
                                    }
                                }
                            }
                        },
                    }
                ]
            }
        if method == "getSignaturesForAddress":
            return [
                {
                    "signature": "5" * 88,
                    "slot": 123,
                    "blockTime": 1_700_000_000,
                    "confirmationStatus": "confirmed",
                    "err": None,
                    "memo": None,
                }
            ]
        raise AssertionError(method)

    return rpc


def test_wallet_secret_is_encrypted_and_public_view_is_masked(tmp_path, monkeypatch):
    _portable_vault(monkeypatch)
    keypair = Keypair()
    private_key = str(keypair)
    wallet = SolanaDevnetWallet(tmp_path)
    monkeypatch.setattr(wallet, "_rpc", _read_rpc(str(keypair.pubkey())))

    local = wallet.connect(private_key, "QA Devnet")
    serialized = json.dumps(local)
    assert local["wallet"]["address"] == str(keypair.pubkey())
    assert local["balances"]["sol"] == 2
    assert local["balances"]["token_count"] == 1
    assert private_key not in serialized
    assert private_key not in wallet.vault_path.read_text(encoding="ascii")
    assert private_key not in wallet.metadata_path.read_text(encoding="utf-8")

    public = wallet.snapshot(public_view=True)
    assert public["view_scope"] == "public_masked"
    assert "address" not in public["wallet"]
    assert "…" in public["wallet"]["address_display"]
    assert "mint" not in public["balances"]["tokens"][0]
    assert "signature" not in public["transactions"][0]
    assert public["signing"]["available"] is False
    assert public["execution"]["manual_devnet_transactions"] is False

    disconnected = wallet.disconnect()
    assert disconnected["configured"] is False
    assert not wallet.vault_path.exists() and not wallet.metadata_path.exists()


def test_wallet_devnet_transfer_is_simulated_confirmed_and_reconciled(tmp_path, monkeypatch):
    _portable_vault(monkeypatch)
    keypair = Keypair()
    address = str(keypair.pubkey())
    wallet = SolanaDevnetWallet(tmp_path)
    captured = {}

    def rpc(method, params, timeout=10):
        if method == "getGenesisHash":
            return DEVNET_GENESIS_HASH
        if method == "getBalance":
            return {"value": 2_000_000_000}
        if method == "getTokenAccountsByOwner":
            return {"value": []}
        if method == "getSignaturesForAddress":
            return []
        if method == "getLatestBlockhash":
            return {"value": {"blockhash": str(Hash.default()), "lastValidBlockHeight": 999}}
        if method == "getFeeForMessage":
            return {"value": 5000}
        if method == "simulateTransaction":
            return {"value": {"err": None}}
        if method == "sendTransaction":
            transaction = Transaction.from_bytes(base64.b64decode(params[0]))
            captured["signature"] = str(transaction.signatures[0])
            return captured["signature"]
        if method == "getSignatureStatuses":
            return {"value": [{"confirmationStatus": "confirmed", "err": None}]}
        if method == "getTransaction":
            return {
                "slot": 321,
                "meta": {"err": None, "fee": 5000},
                "transaction": {
                    "message": {
                        "instructions": [
                            {
                                "program": "system",
                                "parsed": {
                                    "type": "transfer",
                                    "info": {"source": address, "destination": address, "lamports": 1_000_000},
                                },
                            }
                        ]
                    }
                },
            }
        raise AssertionError(method)

    monkeypatch.setattr(wallet, "_rpc", rpc)
    wallet.connect(str(keypair), "Transfer QA")
    result = wallet.transfer("", 0.001, "DEVNET ONLY")

    assert result["signature"] == captured["signature"]
    assert result["status"] == "confirmed" and result["success"] is True
    assert result["simulation"] == "passed" and result["receipt_verified"] is True
    assert result["fee_lamports"] == 5000 and result["slot"] == 321
    log = wallet.execution_log_path.read_text(encoding="utf-8")
    assert '"state":"simulated"' in log and '"state":"confirmed"' in log
    assert str(keypair) not in log


def test_wallet_rejects_invalid_or_oversized_actions(tmp_path, monkeypatch):
    _portable_vault(monkeypatch)
    wallet = SolanaDevnetWallet(tmp_path)
    with pytest.raises(WalletError, match="valid Solana keypair"):
        wallet.connect("not-a-key")

    keypair = Keypair()
    monkeypatch.setattr(wallet, "_rpc", _read_rpc(str(keypair.pubkey())))
    wallet.connect(str(keypair))
    with pytest.raises(WalletError, match="DEVNET ONLY"):
        wallet.transfer("", 0.001, "yes")
    with pytest.raises(WalletError, match="between"):
        wallet.transfer("", 1, "DEVNET ONLY")


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI is Windows-only")
def test_windows_dpapi_round_trip():
    original = b"disposable-test-secret"
    encrypted = wallet_module._dpapi_protect(original)
    assert encrypted != original
    assert wallet_module._dpapi_unprotect(encrypted) == original
