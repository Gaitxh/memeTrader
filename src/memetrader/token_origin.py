"""Verify the initial Pump coin creator from one known create transaction.

Authority:
* Pump official IDL: https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump.json
* Official create_v2 account/data guide:
  https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/COIN_CREATION.md

This intentionally parses only an outer Pump ``create`` or ``create_v2``
instruction in a confirmed ``getTransaction`` response for a caller-supplied
signature.  It does not scan history, infer identity from payer/user, pool
creator or fee recipient, inspect later ``admin_set_creator`` changes, or turn
wallets into human/bundle identities.  The returned identity is therefore the
initial creator argument proven by that exact create instruction.
"""
from __future__ import annotations

import copy
from typing import Any, Awaitable, Callable, Mapping

from solders.pubkey import Pubkey


PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
CREATE_DISCRIMINATOR = bytes((24, 30, 200, 40, 5, 28, 7, 119))
CREATE_V2_DISCRIMINATOR = bytes((214, 144, 76, 236, 95, 139, 49, 180))
IDL_URL = "https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump.json"
CREATE_V2_DOC_URL = (
    "https://github.com/pump-fun/pump-public-docs/blob/main/"
    "docs/instructions/COIN_CREATION.md"
)

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58 = {character: index for index, character in enumerate(_ALPHABET)}


def _unverified(reason: str, *, signature: str, mint: str) -> dict[str, Any]:
    return {
        "status": "unverified",
        "reason": reason,
        "mint": mint,
        "create_signature": signature,
        "creator_address": None,
        "proof": None,
    }


def _b58decode(value: Any) -> bytes | None:
    if not isinstance(value, str) or not value:
        return None
    number = 0
    try:
        for character in value:
            number = number * 58 + _B58[character]
    except KeyError:
        return None
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + decoded


def _keys(message: Mapping[str, Any], meta: Mapping[str, Any]) -> tuple[list[str], set[str]]:
    raw = message.get("accountKeys")
    if not isinstance(raw, list):
        return [], set()
    keys: list[str] = []
    explicit_signers: set[str] = set()
    for item in raw:
        if isinstance(item, Mapping):
            key = str(item.get("pubkey") or "")
            if item.get("signer") is True and key:
                explicit_signers.add(key)
        else:
            key = str(item or "")
        if not key:
            return [], set()
        keys.append(key)
    header = message.get("header")
    if isinstance(header, Mapping):
        required = header.get("numRequiredSignatures")
        if type(required) is int and 0 <= required <= len(keys):
            explicit_signers.update(keys[:required])
    loaded = meta.get("loadedAddresses")
    if isinstance(loaded, Mapping):
        for group in ("writable", "readonly"):
            values = loaded.get(group)
            if isinstance(values, list):
                keys.extend(str(value) for value in values if str(value))
    return keys, explicit_signers


def _address(value: Any, keys: list[str]) -> str | None:
    if type(value) is int:
        return keys[value] if 0 <= value < len(keys) else None
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        candidate = str(value.get("pubkey") or "")
        return candidate or None
    return None


def _instruction_program(instruction: Mapping[str, Any], keys: list[str]) -> str | None:
    return _address(
        instruction.get("programId", instruction.get("programIdIndex")), keys
    )


def _read_borsh_string(data: bytes, offset: int) -> int | None:
    if offset + 4 > len(data):
        return None
    length = int.from_bytes(data[offset:offset + 4], "little")
    end = offset + 4 + length
    return end if length <= 4096 and end <= len(data) else None


def _creator_argument(data: bytes) -> tuple[str, str, int] | None:
    if data.startswith(CREATE_DISCRIMINATOR):
        kind, discriminator = "create", CREATE_DISCRIMINATOR
    elif data.startswith(CREATE_V2_DISCRIMINATOR):
        kind, discriminator = "create_v2", CREATE_V2_DISCRIMINATOR
    else:
        return None
    offset = len(discriminator)
    for _ in range(3):
        next_offset = _read_borsh_string(data, offset)
        if next_offset is None:
            return None
        offset = next_offset
    if offset + 32 > len(data):
        return None
    creator = str(Pubkey.from_bytes(data[offset:offset + 32]))
    if creator == "11111111111111111111111111111111":
        return None
    return kind, creator, offset


def creator_from_create_transaction(
    transaction: Mapping[str, Any], expected_mint: str,
    expected_signature: str,
) -> dict[str, Any]:
    """Return a verified initial creator and compact proof, else unverified."""
    mint, signature = str(expected_mint).strip(), str(expected_signature).strip()
    if not mint or not signature:
        return _unverified("expected_identity_required", signature=signature, mint=mint)
    if not isinstance(transaction, Mapping):
        return _unverified("transaction_shape", signature=signature, mint=mint)
    meta = transaction.get("meta")
    envelope = transaction.get("transaction")
    if not isinstance(meta, Mapping) or not isinstance(envelope, Mapping):
        return _unverified("transaction_shape", signature=signature, mint=mint)
    if meta.get("err") is not None:
        return _unverified("transaction_failed", signature=signature, mint=mint)
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or not signatures or signatures[0] != signature:
        return _unverified("transaction_signature_mismatch", signature=signature, mint=mint)
    message = envelope.get("message")
    if not isinstance(message, Mapping):
        return _unverified("message_shape", signature=signature, mint=mint)
    keys, signers = _keys(message, meta)
    if not keys or mint not in signers:
        return _unverified("mint_signer_not_proven", signature=signature, mint=mint)
    instructions = message.get("instructions")
    if not isinstance(instructions, list):
        return _unverified("instruction_shape", signature=signature, mint=mint)

    matches: list[dict[str, Any]] = []
    for index, instruction in enumerate(instructions):
        if not isinstance(instruction, Mapping):
            continue
        if _instruction_program(instruction, keys) != PUMP_PROGRAM_ID:
            continue
        accounts = instruction.get("accounts")
        if not isinstance(accounts, list) or not accounts:
            continue
        instruction_mint = _address(accounts[0], keys)
        if instruction_mint != mint:
            continue
        data = _b58decode(instruction.get("data"))
        decoded = _creator_argument(data) if data is not None else None
        if decoded is None:
            continue
        kind, creator, creator_offset = decoded
        user_index = 7 if kind == "create" else 5
        minimum_accounts = 14 if kind == "create" else 16
        program_account_index = 13 if kind == "create" else 15
        if (
            len(accounts) < minimum_accounts
            or _address(accounts[program_account_index], keys) != PUMP_PROGRAM_ID
        ):
            continue
        user = _address(accounts[user_index], keys) if len(accounts) > user_index else None
        if user is None or user not in signers:
            continue
        matches.append({
            "creator": creator,
            "kind": kind,
            "index": index,
            "offset": creator_offset,
            "user": user,
            "discriminator": data[:8].hex(),
        })
    if len(matches) != 1:
        reason = "create_instruction_not_found" if not matches else "ambiguous_create_instructions"
        return _unverified(reason, signature=signature, mint=mint)
    match = matches[0]
    return {
        "status": "verified",
        "reason": "pump_create_creator_argument_verified",
        "mint": mint,
        "create_signature": signature,
        "creator_address": match["creator"],
        "creator_identity_kind": "token_creator",
        "creator_identity_verified": True,
        "proof": {
            "proof_version": "pump-create-origin/v1",
            "program_id": PUMP_PROGRAM_ID,
            "instruction_kind": match["kind"],
            "instruction_discriminator_hex": match["discriminator"],
            "outer_instruction_index": match["index"],
            "mint_account_index": 0,
            "creator_argument_offset": match["offset"],
            "creator_argument_decoded": True,
            "mint_signer": True,
            "user_signer": match["user"],
            "transaction_signature_verified": True,
            "slot": transaction.get("slot"),
            "block_time": transaction.get("blockTime"),
            "idl_url": IDL_URL,
            "create_v2_doc_url": CREATE_V2_DOC_URL,
            "scope": "initial_creator_only_not_pool_creator_fee_recipient_or_human",
        },
    }


def _existing_verified(
    evidence: Mapping[str, Any] | None, mint: str, signature: str,
) -> dict[str, Any] | None:
    if not isinstance(evidence, Mapping):
        return None
    proof = evidence.get("proof")
    if not isinstance(proof, Mapping):
        return None
    if (
        evidence.get("status") == "verified"
        and evidence.get("creator_identity_verified") is True
        and evidence.get("creator_identity_kind") == "token_creator"
        and str(evidence.get("mint") or "") == mint
        and str(evidence.get("create_signature") or "") == signature
        and proof.get("proof_version") == "pump-create-origin/v1"
        and proof.get("program_id") == PUMP_PROGRAM_ID
        and proof.get("transaction_signature_verified") is True
        and proof.get("mint_signer") is True
        and isinstance(evidence.get("creator_address"), str)
        and evidence.get("creator_address") not in {"", "11111111111111111111111111111111"}
    ):
        return copy.deepcopy(dict(evidence))
    return None


async def verify_creator_from_known_signature(
    collector: Any, expected_mint: str, expected_signature: str, *,
    existing_evidence: Mapping[str, Any] | None = None,
    rpc: Callable[[str, list[Any]], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    """Use zero or one getTransaction call; never retries or scans signatures."""
    mint, signature = str(expected_mint).strip(), str(expected_signature).strip()
    existing = _existing_verified(existing_evidence, mint, signature)
    if existing is not None:
        existing["rpc_requested"] = False
        return existing
    params = [signature, {
        "commitment": "confirmed",
        "encoding": "jsonParsed",
        "maxSupportedTransactionVersion": 0,
    }]
    try:
        if rpc is not None:
            transaction = await rpc("getTransaction", params)
        else:
            response = await collector.http.post(collector.rpc_url, json={
                "jsonrpc": "2.0", "id": 50_002,
                "method": "getTransaction", "params": params,
            })
            response.raise_for_status()
            payload = response.json()
            if payload.get("error") or "result" not in payload:
                raise ValueError("creator_rpc_error")
            transaction = payload["result"]
    except Exception as exc:
        result = _unverified(
            f"get_transaction_failed:{type(exc).__name__}",
            signature=signature, mint=mint,
        )
        result["rpc_requested"] = True
        return result
    result = creator_from_create_transaction(transaction, mint, signature)
    result["rpc_requested"] = True
    return result


__all__ = [
    "PUMP_PROGRAM_ID", "CREATE_DISCRIMINATOR", "CREATE_V2_DISCRIMINATOR",
    "IDL_URL", "CREATE_V2_DOC_URL", "creator_from_create_transaction",
    "verify_creator_from_known_signature",
]
