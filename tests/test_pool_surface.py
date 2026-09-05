import asyncio
import base64
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from solders.pubkey import Pubkey

from memetrader.collectors import (PUMP_AMM_PROGRAM_ID, PUMP_PROGRAM_ID,
    PUMPSWAP_POOL_DISCRIMINATOR, SOLANA_WRAPPED_SOL_MINT,
    SPL_TOKEN_PROGRAM_ID, SPL_TOKEN_2022_PROGRAM_ID)
from memetrader.pool_surface import (ASSOCIATED_TOKEN_PROGRAM, classify_pumpswap_pool_surface,
                                    collect_pumpswap_pool_surface)

NOW = "2026-09-05T12:00:00Z"


def key():
    return str(Pubkey.new_unique())


def pda(seeds, program=PUMP_AMM_PROGRAM_ID):
    return str(Pubkey.find_program_address(seeds, Pubkey.from_string(program))[0])


def rawkey(value):
    return bytes(Pubkey.from_string(value))


def account(raw, owner):
    return dict(data=[base64.b64encode(raw).decode(), "base64"], owner=owner, lamports=1000)


def mint(supply, decimals, authority=None, program=SPL_TOKEN_2022_PROGRAM_ID):
    raw = bytearray(82)
    if authority:
        raw[0:4] = (1).to_bytes(4, "little")
        raw[4:36] = rawkey(authority)
    raw[36:44], raw[44], raw[45] = supply.to_bytes(8, "little"), decimals, 1
    return account(raw, program)


def token(mint_address, owner, amount, program=SPL_TOKEN_2022_PROGRAM_ID, delegate=None):
    raw = bytearray(165)
    raw[:32], raw[32:64], raw[64:72], raw[108] = rawkey(mint_address), rawkey(owner), amount.to_bytes(8, "little"), 1
    if delegate:
        raw[72:76], raw[76:108], raw[121:129] = (1).to_bytes(4, "little"), rawkey(delegate), amount.to_bytes(8, "little")
    return account(raw, program)


def fixture(canonical=False, current_lp=800, recorded_lp=1000):
    base, quote = key(), SOLANA_WRAPPED_SOL_MINT
    creator = pda([b"pool-authority", rawkey(base)], PUMP_PROGRAM_ID) if canonical else key()
    address = pda([b"pool", (0).to_bytes(2, "little"), rawkey(creator), rawkey(base), rawkey(quote)])
    lp = pda([b"pool_lp_mint", rawkey(address)])
    bv = pda([rawkey(address), rawkey(SPL_TOKEN_2022_PROGRAM_ID), rawkey(base)], ASSOCIATED_TOKEN_PROGRAM)
    qv = pda([rawkey(address), rawkey(SPL_TOKEN_PROGRAM_ID), rawkey(quote)], ASSOCIATED_TOKEN_PROGRAM)
    raw = bytearray(301)
    raw[:8] = PUMPSWAP_POOL_DISCRIMINATOR
    for offset, value in ((11, creator), (43, base), (75, quote), (107, lp), (139, bv), (171, qv)):
        raw[offset:offset + 32] = rawkey(value)
    raw[203:211] = recorded_lp.to_bytes(8, "little")
    h1, h2, other = key(), key(), key()
    accounts = {address: account(raw, PUMP_AMM_PROGRAM_ID), base: mint(1_000_000_000, 6),
                quote: mint(10**15, 9, program=SPL_TOKEN_PROGRAM_ID), lp: mint(current_lp, 9, address),
                bv: token(base, address, 900_000_000), qv: token(quote, address, 10**10, SPL_TOKEN_PROGRAM_ID),
                h1: token(lp, creator, current_lp * 3 // 4),
                h2: token(lp, other, current_lp - current_lp * 3 // 4, delegate=creator)}
    return dict(pool_address=address, base_mint=base), accounts, [h1, h2]


def classify(candidate, accounts, holders, **changes):
    args = dict(observed_at=NOW, recorded_at=NOW, decision_at=NOW, slot=100,
                lp_holder_addresses=holders, holder_scan_complete=True, holder_scan_slot=99)
    args.update(changes)
    return classify_pumpswap_pool_surface(candidate, accounts, **args)


@pytest.mark.parametrize("canonical", [False, True])
def test_exact_surface_supply_and_lp_control_without_migration_history(canonical):
    candidate, accounts, holders = fixture(canonical)
    out = classify(candidate, accounts, holders)
    assert out["complete"] and out["canonical_migration_pool"] is canonical
    assert out["surface"] == ("CANONICAL_MIGRATION" if canonical else "NORMAL_DIRECT")
    assert out["pool_supply_share"] == .9
    assert out["base_decimals"] == 6 and out["quote_decimals"] == 9
    assert out["outside_pool_supply_raw"] == 100_000_000
    assert not out["outside_pool_supply_is_tradable_float"]
    assert out["creator_lp_owned_raw"] == 600 and out["creator_lp_controlled_raw"] == 800
    assert out["creator_withdraw_fraction_observed"] == .8
    assert out["total_lp_withdraw_fraction_upper_bound"] == .8
    assert out["lp_supply_gap_raw"] == 200 and out["lp_burned_amount_raw"] is None
    assert out["lp_lock_status"] == "UNKNOWN" and out["sellability_status"] == "NOT_MEASURED"


def test_zero_supply_and_absent_holders_do_not_claim_burn_or_locked_safety():
    candidate, accounts, holders = fixture(current_lp=0)
    zero = classify(candidate, accounts, [])
    assert zero["lp_custody_status"] == "ZERO_CURRENT_SUPPLY"
    assert zero["lp_burned_amount_raw"] is None and zero["total_lp_withdraw_fraction_upper_bound"] == 0
    candidate, accounts, holders = fixture()
    absent = classify(candidate, accounts, [])
    assert absent["lp_custody_status"] == "PARTIAL_UNKNOWN_REMAINDER"
    assert absent["lp_unobserved_supply_raw"] == 800
    assert absent["max_single_controller_withdraw_fraction_upper_bound"] == .8
    assert absent["creator_lp_amounts_are_lower_bounds"]


def test_partial_holder_distribution_keeps_unknown_remainder_and_owner_mismatch():
    candidate, accounts, holders = fixture()
    del accounts[holders[1]]
    out = classify(candidate, accounts, holders)
    assert out["complete"] and not out["lp_holder_coverage_complete"]
    assert out["creator_lp_controlled_raw"] == 600 and out["lp_unobserved_supply_raw"] == 200
    assert out["max_single_controller_withdraw_fraction_observed"] == .6
    assert out["max_single_controller_withdraw_fraction_upper_bound"] == .8


@pytest.mark.parametrize("change", ["base", "pool", "lp", "vault", "future", "missing_time", "mint_owner"])
def test_wrong_identity_and_future_data_fail_closed(change):
    candidate, accounts, holders = fixture()
    args = {}
    if change == "base":
        candidate["base_mint"] = key()
    elif change == "pool":
        old = candidate["pool_address"]
        candidate["pool_address"] = key()
        accounts[candidate["pool_address"]] = accounts[old]
    elif change in {"lp", "vault"}:
        raw = bytearray(base64.b64decode(accounts[candidate["pool_address"]]["data"][0]))
        offset = 107 if change == "lp" else 139
        raw[offset:offset + 32] = rawkey(key())
        accounts[candidate["pool_address"]] = account(raw, PUMP_AMM_PROGRAM_ID)
    elif change == "future":
        args["recorded_at"] = "2026-09-05T12:00:01Z"
    elif change == "missing_time":
        args["observed_at"] = None
    elif change == "mint_owner":
        accounts[candidate["base_mint"]]["owner"] = key()
    assert not classify(candidate, accounts, holders, **args)["complete"]


@pytest.mark.parametrize("largest_error", [False, True])
def test_collector_is_bounded_and_custody_failure_preserves_surface(largest_error):
    candidate, accounts, holders = fixture()
    calls = []
    class Http:
        async def post(self, url, *, json):
            method, params = json["method"], json["params"]
            calls.append((method, params))
            if method == "getTokenLargestAccounts":
                payload = {"error": {"message": "rate limited"}} if largest_error else {
                    "result": {"context": {"slot": 101}, "value": [dict(address=h, amount="wrong_unused") for h in holders]}}
            else:
                slot = 100 if len(calls) == 1 else 102
                payload = {"result": {"context": {"slot": slot}, "value": [accounts.get(k) for k in params[0]]}}
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))
    out = asyncio.run(collect_pumpswap_pool_surface(SimpleNamespace(http=Http(), rpc_url="https://rpc.invalid"), candidate))
    assert [call[0] for call in calls] == ["getMultipleAccounts", "getTokenLargestAccounts", "getMultipleAccounts"]
    assert out["complete"] and out["rpc_count"] == 3
    assert out["lp_holder_coverage_complete"] is (not largest_error)
    assert calls[-1][1][1]["minContextSlot"] == (100 if largest_error else 101)
    assert len(calls[-1][1][0]) <= 26
