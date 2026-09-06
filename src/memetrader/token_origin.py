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
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
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


def _raw_token_amount(balance: Mapping[str, Any]) -> int | None:
    ui_amount = balance.get("uiTokenAmount")
    if not isinstance(ui_amount, Mapping):
        return None
    raw = ui_amount.get("amount")
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    if type(raw) is int and raw >= 0:
        return raw
    return None


def _issuance_unknown(
    reason: str, *, mint: str, signature: str,
    transaction: Mapping[str, Any], token_program: str | None = None,
) -> dict[str, Any]:
    return {
        "snapshot_version": "pump-create-issuance-holders/v1",
        "status": "unknown",
        "complete": False,
        "reason": reason,
        "mint": mint,
        "create_signature": signature,
        "slot": transaction.get("slot"),
        "block_time": transaction.get("blockTime"),
        "token_program": token_program,
        "minted_raw": None,
        "burned_raw": None,
        "total_supply_raw": None,
        "post_balance_sum_raw": None,
        "owner_count": 0,
        "token_account_count": 0,
        "coverage": "unknown",
        "identity_scope": "token_account_owner_address_not_human_or_custody_identity",
        "owners": [],
    }


def _issuance_holder_snapshot(
    transaction: Mapping[str, Any], message: Mapping[str, Any],
    meta: Mapping[str, Any], keys: list[str], *, mint: str, signature: str,
    creator: str, user: str, bonding_curve: str | None,
) -> dict[str, Any]:
    """Close initial supply against the same transaction's parsed SPL evidence."""
    if (type(transaction.get("slot")) is not int or transaction["slot"] < 0
            or type(transaction.get("blockTime")) is not int or transaction["blockTime"] < 0):
        return _issuance_unknown("transaction_time_or_slot_unavailable", mint=mint,
                                 signature=signature, transaction=transaction)
    token_programs = {TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID}
    all_instructions: list[Mapping[str, Any]] = []
    outer = message.get("instructions")
    if isinstance(outer, list):
        all_instructions.extend(item for item in outer if isinstance(item, Mapping))
    inner = meta.get("innerInstructions")
    if not isinstance(inner, list):
        return _issuance_unknown(
            "inner_instructions_unavailable", mint=mint, signature=signature,
            transaction=transaction,
        )
    for group in inner:
        if not isinstance(group, Mapping) or not isinstance(group.get("instructions"), list):
            return _issuance_unknown(
                "inner_instruction_shape", mint=mint, signature=signature,
                transaction=transaction,
            )
        all_instructions.extend(
            item for item in group["instructions"] if isinstance(item, Mapping)
        )

    minted = burned = 0
    supply_programs: set[str] = set()
    for instruction in all_instructions:
        program = _instruction_program(instruction, keys)
        if program not in token_programs:
            continue
        parsed = instruction.get("parsed")
        if not isinstance(parsed, Mapping):
            return _issuance_unknown(
                "unparsed_token_instruction", mint=mint, signature=signature,
                transaction=transaction, token_program=program,
            )
        kind, info = parsed.get("type"), parsed.get("info")
        if not isinstance(kind, str) or not isinstance(info, Mapping):
            return _issuance_unknown(
                "parsed_token_instruction_shape", mint=mint, signature=signature,
                transaction=transaction, token_program=program,
            )
        if str(info.get("mint") or "") != mint:
            continue
        if kind in {"mintTo", "mintToChecked", "burn", "burnChecked"}:
            amount_value = info.get("amount")
            if amount_value is None and isinstance(info.get("tokenAmount"), Mapping):
                amount_value = info["tokenAmount"].get("amount")
            if isinstance(amount_value, str) and amount_value.isdigit():
                amount = int(amount_value)
            elif type(amount_value) is int and amount_value >= 0:
                amount = amount_value
            else:
                return _issuance_unknown(
                    "supply_instruction_amount", mint=mint, signature=signature,
                    transaction=transaction, token_program=program,
                )
            supply_programs.add(program)
            if kind.startswith("mintTo"):
                minted += amount
            else:
                burned += amount
        elif ("mint" in kind.lower() or "burn" in kind.lower()) \
                and not kind.lower().startswith("initialize"):
            return _issuance_unknown(
                "unsupported_supply_instruction", mint=mint, signature=signature,
                transaction=transaction, token_program=program,
            )
    if minted <= 0:
        return _issuance_unknown(
            "mint_to_not_proven", mint=mint, signature=signature,
            transaction=transaction,
        )
    if burned > minted or len(supply_programs) != 1:
        return _issuance_unknown(
            "net_supply_not_proven", mint=mint, signature=signature,
            transaction=transaction,
        )
    token_program = next(iter(supply_programs))

    pre_balances, post_balances = meta.get("preTokenBalances"), meta.get("postTokenBalances")
    if not isinstance(pre_balances, list) or not isinstance(post_balances, list):
        return _issuance_unknown(
            "token_balances_unavailable", mint=mint, signature=signature,
            transaction=transaction, token_program=token_program,
        )
    seen_pre: set[int] = set()
    for balance in pre_balances:
        if not isinstance(balance, Mapping) or str(balance.get("mint") or "") != mint:
            continue
        account_index = balance.get("accountIndex")
        amount = _raw_token_amount(balance)
        if (
            type(account_index) is not int or not 0 <= account_index < len(keys)
            or account_index in seen_pre or amount is None
            or balance.get("programId") != token_program
        ):
            return _issuance_unknown(
                "pre_balance_shape", mint=mint, signature=signature,
                transaction=transaction, token_program=token_program,
            )
        seen_pre.add(account_index)
        if amount != 0:
            return _issuance_unknown(
                "preexisting_mint_balance", mint=mint, signature=signature,
                transaction=transaction, token_program=token_program,
            )

    seen_post: set[int] = set()
    by_owner: dict[str, int] = {}
    owner_on_curve: dict[str, bool] = {}
    matching_post = 0
    for balance in post_balances:
        if not isinstance(balance, Mapping) or str(balance.get("mint") or "") != mint:
            continue
        matching_post += 1
        account_index = balance.get("accountIndex")
        owner = balance.get("owner")
        amount = _raw_token_amount(balance)
        if (
            type(account_index) is not int or not 0 <= account_index < len(keys)
            or account_index in seen_post or not isinstance(owner, str) or not owner
            or amount is None or balance.get("programId") != token_program
        ):
            return _issuance_unknown(
                "post_balance_shape", mint=mint, signature=signature,
                transaction=transaction, token_program=token_program,
            )
        seen_post.add(account_index)
        try:
            owner_on_curve[owner] = Pubkey.from_string(owner).is_on_curve()
        except ValueError:
            return _issuance_unknown("invalid_token_owner", mint=mint, signature=signature,
                                     transaction=transaction, token_program=token_program)
        if amount > 0:
            by_owner[owner] = by_owner.get(owner, 0) + amount
    post_sum = sum(by_owner.values())
    total_supply = minted - burned
    if matching_post == 0 or post_sum != total_supply:
        return _issuance_unknown(
            "post_balance_supply_mismatch", mint=mint, signature=signature,
            transaction=transaction, token_program=token_program,
        )

    derived_curve = str(Pubkey.find_program_address(
        [b"bonding-curve", bytes(Pubkey.from_string(mint))], Pubkey.from_string(PUMP_PROGRAM_ID))[0])

    def role(owner: str) -> str:
        if owner == bonding_curve == derived_curve:
            return "derived_bonding_curve"
        if owner == creator and owner == user:
            return "creator_and_create_user"
        if owner == creator:
            return "creator_address"
        if owner == user:
            return "create_user"
        if not owner_on_curve[owner]:
            return "off_curve_program_owner"
        return "token_account_owner"

    owners = [
        {"owner": owner, "amount_raw": amount, "role": role(owner),
         "is_on_curve": owner_on_curve[owner]}
        for owner, amount in sorted(by_owner.items())
    ]
    return {
        "snapshot_version": "pump-create-issuance-holders/v1",
        "status": "complete",
        "complete": True,
        "reason": "net_supply_closed_by_post_token_balances",
        "mint": mint,
        "create_signature": signature,
        "slot": transaction.get("slot"),
        "block_time": transaction.get("blockTime"),
        "token_program": token_program,
        "minted_raw": minted,
        "burned_raw": burned,
        "total_supply_raw": total_supply,
        "post_balance_sum_raw": post_sum,
        "owner_count": len(owners),
        "token_account_count": matching_post,
        "coverage": "complete_same_transaction_post_token_balances",
        "identity_scope": "token_account_owner_address_not_human_or_custody_identity",
        "owners": owners,
    }


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
            "bonding_curve": _address(accounts[2], keys),
            "discriminator": data[:8].hex(),
        })
    if len(matches) != 1:
        reason = "create_instruction_not_found" if not matches else "ambiguous_create_instructions"
        return _unverified(reason, signature=signature, mint=mint)
    match = matches[0]
    result = {
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
    result["issuance_holder_snapshot"] = _issuance_holder_snapshot(
        transaction, message, meta, keys, mint=mint, signature=signature,
        creator=match["creator"], user=match["user"],
        bonding_curve=match["bonding_curve"],
    )
    return result


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
    "PUMP_PROGRAM_ID", "TOKEN_PROGRAM_ID", "TOKEN_2022_PROGRAM_ID",
    "CREATE_DISCRIMINATOR", "CREATE_V2_DISCRIMINATOR",
    "IDL_URL", "CREATE_V2_DOC_URL", "creator_from_create_transaction",
    "verify_creator_from_known_signature",
]
