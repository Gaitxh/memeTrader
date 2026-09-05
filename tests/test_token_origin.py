import asyncio
from types import SimpleNamespace

import pytest
from solders.pubkey import Pubkey

from memetrader.token_origin import (
    CREATE_DISCRIMINATOR,
    CREATE_V2_DISCRIMINATOR,
    PUMP_PROGRAM_ID,
    creator_from_create_transaction,
    verify_creator_from_known_signature,
)


ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(value):
    zeros = len(value) - len(value.lstrip(b"\0"))
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = ALPHABET[remainder] + encoded
    return "1" * zeros + encoded


def borsh_string(value):
    raw = value.encode()
    return len(raw).to_bytes(4, "little") + raw


def create_data(discriminator, creator):
    return (
        discriminator + borsh_string("Name") + borsh_string("SYM")
        + borsh_string("https://example.invalid/meta.json") + bytes(creator)
        + (b"\0\0" if discriminator == CREATE_V2_DISCRIMINATOR else b"")
    )


def transaction(discriminator=CREATE_DISCRIMINATOR, *, signature="sig", changes=None):
    mint, user, creator = Pubkey.new_unique(), Pubkey.new_unique(), Pubkey.new_unique()
    fee_recipient = Pubkey.new_unique()
    account_keys = [
        {"pubkey": str(mint), "signer": True, "writable": True},
        {"pubkey": str(user), "signer": True, "writable": True},
        {"pubkey": str(fee_recipient), "signer": False, "writable": True},
        {"pubkey": PUMP_PROGRAM_ID, "signer": False, "writable": False},
    ]
    user_index = 7 if discriminator == CREATE_DISCRIMINATOR else 5
    account_count = 14 if discriminator == CREATE_DISCRIMINATOR else 16
    accounts = [str(Pubkey.new_unique()) for _ in range(account_count)]
    accounts[0], accounts[user_index] = str(mint), str(user)
    accounts[-1] = PUMP_PROGRAM_ID
    tx = {
        "slot": 123, "blockTime": 1_788_000_000, "meta": {"err": None},
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": account_keys,
                "instructions": [{
                    "programId": PUMP_PROGRAM_ID,
                    "accounts": accounts,
                    "data": b58encode(create_data(discriminator, creator)),
                }],
            },
        },
    }
    if changes:
        changes(tx, mint, user, creator, fee_recipient)
    return tx, str(mint), str(user), str(creator), str(fee_recipient)


@pytest.mark.parametrize("discriminator,kind", [
    (CREATE_DISCRIMINATOR, "create"),
    (CREATE_V2_DISCRIMINATOR, "create_v2"),
])
def test_decodes_official_creator_argument_not_user_or_fee_recipient(discriminator, kind):
    tx, mint, user, creator, fee = transaction(discriminator)
    result = creator_from_create_transaction(tx, mint, "sig")
    assert result["status"] == "verified"
    assert result["creator_address"] == creator
    assert creator not in {user, fee}
    assert result["creator_identity_kind"] == "token_creator"
    assert result["proof"]["instruction_kind"] == kind
    assert result["proof"]["mint_signer"] is True
    assert result["proof"]["scope"].startswith("initial_creator_only")


def test_requires_exact_signature_mint_signer_and_pump_program():
    tx, mint, _, _, _ = transaction()
    assert creator_from_create_transaction(tx, mint, "other")["reason"] == "transaction_signature_mismatch"
    tx["transaction"]["message"]["accountKeys"][0]["signer"] = False
    assert creator_from_create_transaction(tx, mint, "sig")["reason"] == "mint_signer_not_proven"
    tx, mint, _, _, _ = transaction()
    tx["transaction"]["message"]["instructions"][0]["programId"] = str(Pubkey.new_unique())
    assert creator_from_create_transaction(tx, mint, "sig")["reason"] == "create_instruction_not_found"


def test_malformed_or_ambiguous_create_never_verifies():
    tx, mint, _, _, _ = transaction()
    instruction = tx["transaction"]["message"]["instructions"][0]
    instruction["data"] = b58encode(CREATE_DISCRIMINATOR + b"\x05\0\0")
    assert creator_from_create_transaction(tx, mint, "sig")["status"] == "unverified"
    tx, mint, _, _, _ = transaction()
    instructions = tx["transaction"]["message"]["instructions"]
    instructions.append(dict(instructions[0]))
    assert creator_from_create_transaction(tx, mint, "sig")["reason"] == "ambiguous_create_instructions"


def test_known_signature_uses_one_get_transaction_without_retry():
    tx, mint, _, creator, _ = transaction()
    calls = []

    async def rpc(method, params):
        calls.append((method, params))
        return tx

    result = asyncio.run(verify_creator_from_known_signature(
        None, mint, "sig", rpc=rpc,
    ))
    assert result["creator_address"] == creator
    assert result["rpc_requested"] is True
    assert [call[0] for call in calls] == ["getTransaction"]
    assert calls[0][1][1]["commitment"] == "confirmed"


class Response:
    def __init__(self, result):
        self.result = result

    def raise_for_status(self):
        return None

    def json(self):
        return {"jsonrpc": "2.0", "result": self.result}


class Http:
    def __init__(self, result):
        self.result, self.calls = result, []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.result)


def test_existing_chain_proof_skips_collector_http_otherwise_one_call():
    tx, mint, _, _, _ = transaction()
    http = Http(tx)
    collector = SimpleNamespace(http=http, rpc_url="https://rpc.invalid")
    verified = asyncio.run(verify_creator_from_known_signature(collector, mint, "sig"))
    assert len(http.calls) == 1
    cached = asyncio.run(verify_creator_from_known_signature(
        collector, mint, "sig", existing_evidence=verified,
    ))
    assert cached["status"] == "verified"
    assert cached["rpc_requested"] is False
    assert len(http.calls) == 1
