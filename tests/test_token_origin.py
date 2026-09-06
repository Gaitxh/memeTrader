import asyncio
from types import SimpleNamespace

import pytest
from solders.pubkey import Pubkey

from memetrader.token_origin import (
    CREATE_DISCRIMINATOR,
    CREATE_V2_DISCRIMINATOR,
    PUMP_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
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


def add_issuance(tx, mint, user, creator, _fee, *, program=TOKEN_PROGRAM_ID):
    message = tx["transaction"]["message"]
    message["instructions"][0]["accounts"][2] = str(Pubkey.find_program_address(
        [b"bonding-curve", bytes(mint)], Pubkey.from_string(PUMP_PROGRAM_ID))[0])
    bonding_curve = message["instructions"][0]["accounts"][2]
    account_keys = message["accountKeys"]
    account_keys.extend([
        {"pubkey": str(Pubkey.new_unique()), "signer": False, "writable": True},
        {"pubkey": str(Pubkey.new_unique()), "signer": False, "writable": True},
    ])
    tx["meta"].update({
        "innerInstructions": [{"index": 0, "instructions": [
            {"programId": program, "parsed": {
                "type": "mintTo", "info": {"mint": str(mint), "amount": "100"},
            }},
            {"programId": program, "parsed": {
                "type": "burnChecked", "info": {
                    "mint": str(mint), "tokenAmount": {"amount": "10"},
                },
            }},
        ]}],
        "preTokenBalances": [],
        "postTokenBalances": [
            {
                "accountIndex": 4, "mint": str(mint), "owner": bonding_curve,
                "programId": program, "uiTokenAmount": {"amount": "70"},
            },
            {
                "accountIndex": 5, "mint": str(mint), "owner": str(creator),
                "programId": program, "uiTokenAmount": {"amount": "20"},
            },
        ],
    })


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


@pytest.mark.parametrize("program", [TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID])
def test_complete_issuance_snapshot_closes_net_supply_and_keeps_protocol_separate(program):
    def changes(tx, mint, user, creator, fee):
        add_issuance(tx, mint, user, creator, fee, program=program)

    tx, mint, _, creator, _ = transaction(changes=changes)
    snapshot = creator_from_create_transaction(tx, mint, "sig")["issuance_holder_snapshot"]
    assert snapshot["status"] == "complete"
    assert snapshot["complete"] is True
    assert snapshot["token_program"] == program
    assert snapshot["minted_raw"] == 100
    assert snapshot["burned_raw"] == 10
    assert snapshot["total_supply_raw"] == snapshot["post_balance_sum_raw"] == 90
    assert snapshot["owner_count"] == snapshot["token_account_count"] == 2
    owners = {item["owner"]: item for item in snapshot["owners"]}
    bonding_curve = tx["transaction"]["message"]["instructions"][0]["accounts"][2]
    assert owners[bonding_curve] == {
        "owner": bonding_curve, "amount_raw": 70, "role": "derived_bonding_curve",
        "is_on_curve": False,
    }
    assert owners[creator]["role"] == "creator_address"
    assert snapshot["identity_scope"].startswith("token_account_owner_address")


@pytest.mark.parametrize("mutation,reason", [
    ("unparsed", "unparsed_token_instruction"),
    ("preexisting", "preexisting_mint_balance"),
    ("bad_index", "post_balance_shape"),
    ("missing_owner", "post_balance_shape"),
    ("duplicate", "post_balance_shape"),
    ("mismatch", "post_balance_supply_mismatch"),
    ("invalid_owner", "invalid_token_owner"),
    ("no_slot", "transaction_time_or_slot_unavailable"),
])
def test_incomplete_issuance_evidence_stays_unknown(mutation, reason):
    def changes(tx, mint, user, creator, fee):
        add_issuance(tx, mint, user, creator, fee)
        meta = tx["meta"]
        if mutation == "unparsed":
            meta["innerInstructions"][0]["instructions"][0] = {
                "programId": TOKEN_PROGRAM_ID, "accounts": [0], "data": "raw",
            }
        elif mutation == "preexisting":
            meta["preTokenBalances"] = [{
                "accountIndex": 4, "mint": str(mint), "owner": str(creator),
                "programId": TOKEN_PROGRAM_ID, "uiTokenAmount": {"amount": "1"},
            }]
        elif mutation == "bad_index":
            meta["postTokenBalances"][0]["accountIndex"] = 99
        elif mutation == "missing_owner":
            del meta["postTokenBalances"][0]["owner"]
        elif mutation == "duplicate":
            meta["postTokenBalances"].append(dict(meta["postTokenBalances"][0]))
        elif mutation == "mismatch":
            meta["postTokenBalances"][0]["uiTokenAmount"]["amount"] = "69"
        elif mutation == "invalid_owner":
            meta["postTokenBalances"][0]["owner"] = "not-an-address"
        elif mutation == "no_slot":
            del tx["slot"]

    tx, mint, _, _, _ = transaction(changes=changes)
    snapshot = creator_from_create_transaction(tx, mint, "sig")["issuance_holder_snapshot"]
    assert snapshot["status"] == "unknown"
    assert snapshot["complete"] is False
    assert snapshot["reason"] == reason
    assert snapshot["owners"] == []


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
