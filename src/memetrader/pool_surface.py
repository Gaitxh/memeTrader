"""Exact current PumpSwap surfaces and bounded LP custody evidence.

Protocol: pump-fun/pump-public-docs docs/PUMP_SWAP_README.md and idl/pump_amm.json.
Pool.lp_supply includes directly burned/locked liquidity; mint supply does not.
A supply gap is therefore not a reconstructed burn transaction. This module
never equates missing holder accounts, PDA custody, or zero supply with a lock.
"""
from __future__ import annotations

import base64
from collections import defaultdict
from typing import Any, Mapping

from solders.pubkey import Pubkey

from .collectors import (PUMP_AMM_PROGRAM_ID, PUMP_PROGRAM_ID, PUMPSWAP_POOL_DECODER_V2,
                         SOLANA_WRAPPED_SOL_MINT, SPL_TOKEN_PROGRAM_ID,
                         SPL_TOKEN_2022_PROGRAM_ID, SolanaHeldAccountCollector)
from .models import iso, parse_time, utcnow

ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
TOKEN_PROGRAMS = {SPL_TOKEN_PROGRAM_ID, SPL_TOKEN_2022_PROGRAM_ID}


def _pda(seeds, program=PUMP_AMM_PROGRAM_ID):
    return str(Pubkey.find_program_address(seeds, Pubkey.from_string(program))[0])


def _key(address):
    return bytes(Pubkey.from_string(address))


def _decode(target, account):
    decoded = SolanaHeldAccountCollector.decode_account(target, account)
    if decoded.get("status") != "verified":
        raise ValueError(decoded.get("reason", "account_not_verified"))
    return decoded


def _pool(account, candidate):
    pool = _decode(dict(account_kind="pool", decoder_version=PUMPSWAP_POOL_DECODER_V2,
                        expected_program_owner=PUMP_AMM_PROGRAM_ID), account)
    if pool["base_mint"] != candidate["base_mint"]:
        raise ValueError("pool_base_mint_mismatch")
    if candidate.get("quote_mint") and pool["quote_mint"] != candidate["quote_mint"]:
        raise ValueError("pool_quote_mint_mismatch")
    derived = _pda([b"pool", pool["index"].to_bytes(2, "little"), _key(pool["creator"]),
                    _key(pool["base_mint"]), _key(pool["quote_mint"])])
    if derived != candidate["pool_address"]:
        raise ValueError("pool_pda_mismatch")
    if pool["lp_mint"] != _pda([b"pool_lp_mint", _key(derived)]):
        raise ValueError("lp_mint_pda_mismatch")
    return pool


def _lp_account(address, value, mint, program):
    if not isinstance(value, Mapping) or value.get("owner") != program:
        raise ValueError("lp_holder_account_missing_or_program_mismatch")
    raw = base64.b64decode(value["data"][0], validate=True)
    if len(raw) < 165 or str(Pubkey.from_bytes(raw[:32])) != mint or raw[108] not in (1, 2):
        raise ValueError("lp_holder_mint_or_state_invalid")
    delegate_option = int.from_bytes(raw[72:76], "little")
    if delegate_option not in (0, 1):
        raise ValueError("lp_delegate_option_invalid")
    return dict(address=address, owner=str(Pubkey.from_bytes(raw[32:64])),
                amount_raw=int.from_bytes(raw[64:72], "little"), frozen=raw[108] == 2,
                delegate=str(Pubkey.from_bytes(raw[76:108])) if delegate_option else None,
                delegated_amount_raw=int.from_bytes(raw[121:129], "little") if delegate_option else 0)


def classify_pumpswap_pool_surface(candidate: Mapping[str, Any], accounts: Mapping[str, Any], *,
                                   observed_at, recorded_at, decision_at, slot: int,
                                   lp_holder_addresses=(), holder_scan_complete=False,
                                   holder_scan_slot=None):
    """Classify one same-bank account bundle. Missing custody never implies safety.

    accounts maps public key to raw getMultipleAccounts value; candidate requires
    exact pool_address/base_mint (optional expected quote_mint). All quantities
    and custody come from this bundle, not earlier largest-account amounts.
    LP withdrawal figures are pool-share upper bounds, not executable quotes.
    """
    out = dict(status="UNKNOWN_IDENTITY", complete=False, surface="UNKNOWN",
               pool_address=candidate.get("pool_address"), base_mint=candidate.get("base_mint"),
               observed_at=observed_at, recorded_at=recorded_at, slot=slot,
               lp_burn_status="UNKNOWN_NO_BURN_TRANSACTION_EVIDENCE", lp_burned_amount_raw=None,
               lp_lock_status="UNKNOWN", sellability_status="NOT_MEASURED")
    try:
        if any(value is None for value in (observed_at, recorded_at, decision_at)):
            raise ValueError("missing_asof_provenance")
        observed, recorded, decision = map(parse_time, (observed_at, recorded_at, decision_at))
        if observed is None or recorded is None or decision is None or not observed <= recorded <= decision or slot <= 0:
            raise ValueError("missing_or_future_asof_provenance")
        pool = _pool(accounts.get(candidate["pool_address"]), candidate)
        mints = {}
        for side in ("base", "quote", "lp"):
            address = pool[side + "_mint"]
            mint = _decode(dict(account_kind="token_mint"), accounts.get(address))
            if mint["owner"] not in TOKEN_PROGRAMS or not mint["initialized"]:
                raise ValueError("mint_program_or_initialization_invalid")
            mints[side] = mint
        if mints["lp"]["mint_authority"] not in (candidate["pool_address"], None):
            raise ValueError("lp_mint_authority_mismatch")
        vaults = {}
        for side in ("base", "quote"):
            mint, vault = pool[side + "_mint"], pool[side + "_vault"]
            program = mints[side]["owner"]
            expected_vault = _pda([_key(candidate["pool_address"]), _key(program), _key(mint)], ASSOCIATED_TOKEN_PROGRAM)
            if vault != expected_vault:
                raise ValueError("vault_ata_mismatch")
            vaults[side] = _decode(dict(account_kind=side + "_vault", expected_mint=mint,
                expected_program_owner=program, pool_address=candidate["pool_address"]), accounts.get(vault))
        supply, reserve = mints["base"]["supply_raw"], vaults["base"]["amount_raw"]
        if reserve > supply:
            raise ValueError("pool_base_reserve_exceeds_mint_supply")
        canonical_creator = _pda([b"pool-authority", _key(pool["base_mint"])], PUMP_PROGRAM_ID)
        canonical = (pool["creator"] == canonical_creator and pool["index"] == 0
                     and pool["quote_mint"] == SOLANA_WRAPPED_SOL_MINT)
        out.update(status="RESOLVED", complete=True,
            surface="CANONICAL_MIGRATION" if canonical else "NORMAL_DIRECT",
            canonical_migration_pool=canonical, pool_creator=pool["creator"], pool_index=pool["index"],
            quote_mint=pool["quote_mint"], lp_mint=pool["lp_mint"],
            base_vault=pool["base_vault"], quote_vault=pool["quote_vault"],
            base_token_program=mints["base"]["owner"], quote_token_program=mints["quote"]["owner"],
            base_decimals=mints["base"]["decimals"], quote_decimals=mints["quote"]["decimals"],
            mint_total_supply_raw=supply, base_vault_raw=reserve, quote_vault_raw=vaults["quote"]["amount_raw"],
            pool_supply_share=reserve / supply if supply else None,
            outside_pool_supply_raw=supply - reserve,
            outside_pool_supply_is_tradable_float=False,
            requires_fast_vault_exit=not canonical,
            mint_authority=mints["base"]["mint_authority"], freeze_authority=mints["base"]["freeze_authority"])

        recorded_lp, current_lp = pool["lp_supply_recorded_raw"], mints["lp"]["supply_raw"]
        out.update(lp_supply_recorded_raw=recorded_lp, lp_mint_supply_raw=current_lp,
            lp_decimals=mints["lp"]["decimals"], lp_mint_authority=mints["lp"]["mint_authority"],
            lp_freeze_authority=mints["lp"]["freeze_authority"],
            lp_zero_current_supply=current_lp == 0, lp_supply_gap_raw=None,
            lp_custody_status="UNKNOWN", lp_holders=[], lp_holder_coverage_complete=False,
            creator_lp_owned_raw=None, creator_lp_controlled_raw=None,
            creator_withdraw_fraction_observed=None, max_single_controller_withdraw_fraction_observed=None,
            total_lp_withdraw_fraction_upper_bound=None, lp_holder_scan_slot=holder_scan_slot)
        if current_lp > recorded_lp or recorded_lp == 0:
            out["lp_custody_reason"] = "inconsistent_or_zero_recorded_lp_supply"
            return out
        out.update(lp_supply_gap_raw=recorded_lp - current_lp,
            lp_supply_gap_meaning="burn_or_protocol_lock_gap_not_burn_transaction",
            total_lp_withdraw_fraction_upper_bound=current_lp / recorded_lp)
        if current_lp == 0:
            out.update(lp_custody_status="ZERO_CURRENT_SUPPLY", lp_holder_coverage_complete=True,
                       creator_lp_owned_raw=0, creator_lp_controlled_raw=0,
                       creator_withdraw_fraction_observed=0, max_single_controller_withdraw_fraction_observed=0)
            return out
        addresses = list(lp_holder_addresses)
        if len(addresses) > 20 or len(addresses) != len(set(addresses)):
            out["lp_custody_reason"] = "invalid_or_unbounded_holder_addresses"
            return out
        holders, issues = [], []
        for address in addresses:
            try:
                holders.append(_lp_account(address, accounts.get(address), pool["lp_mint"], mints["lp"]["owner"]))
            except (KeyError, TypeError, ValueError):
                issues.append("holder_account_unavailable_or_invalid")
        sampled = sum(holder["amount_raw"] for holder in holders)
        if sampled > current_lp:
            out["lp_custody_reason"] = "holder_amounts_exceed_mint_supply"
            return out
        custody_complete = (holder_scan_complete and not issues and sampled == current_lp
                            and type(holder_scan_slot) is int and 0 < holder_scan_slot <= slot)
        controls = defaultdict(int)
        for holder in holders:
            amount, owner = holder["amount_raw"], holder["owner"]
            controls[owner] += amount
            if holder["delegate"] and holder["delegate"] != owner:
                controls[holder["delegate"]] += min(amount, holder["delegated_amount_raw"])
        creator_owned = sum(holder["amount_raw"] for holder in holders if holder["owner"] == pool["creator"])
        creator_control = controls.get(pool["creator"], 0)
        largest = max(controls.values(), default=0)
        out.update(lp_custody_status="OBSERVED_COMPLETE" if custody_complete else "PARTIAL_UNKNOWN_REMAINDER",
            lp_holder_coverage_complete=bool(custody_complete), lp_holders=holders,
            lp_observed_holder_supply_raw=sampled, lp_unobserved_supply_raw=current_lp - sampled,
            creator_lp_owned_raw=creator_owned, creator_lp_controlled_raw=creator_control,
            creator_lp_amounts_are_lower_bounds=not custody_complete,
            creator_withdraw_fraction_observed=creator_control / recorded_lp,
            max_single_controller_withdraw_fraction_observed=largest / recorded_lp,
            max_single_controller_withdraw_fraction_upper_bound=min(current_lp, largest + current_lp - sampled) / recorded_lp,
            lp_custody_reason=";".join(sorted(set(issues))))
        return out
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        out.update(status="UNKNOWN_IDENTITY", complete=False, surface="UNKNOWN", reason=str(exc))
        return out


async def collect_pumpswap_pool_surface(collector, candidate: Mapping[str, Any]):
    """Read one candidate: at most two getMultipleAccounts and one largest call.

    Caller owns cadence/budget. Reuses collector.http/rpc_url, adds no client,
    scanner or retry loop. A failed largest-account request still returns pool
    identity/supply evidence, with explicitly unavailable custody coverage.
    """
    rpc_count, provenance = 0, []
    async def rpc(method, params):
        nonlocal rpc_count
        rpc_count += 1
        response = await collector.http.post(collector.rpc_url, json={
            "jsonrpc": "2.0", "id": 61_000 + rpc_count, "method": method, "params": params})
        response.raise_for_status()
        payload = response.json()
        if payload.get("error") or not isinstance(payload.get("result"), Mapping):
            raise ValueError("pool_surface_rpc_result_unavailable")
        result = payload["result"]
        slot = int((result.get("context") or {}).get("slot") or 0)
        if slot <= 0:
            raise ValueError("pool_surface_rpc_slot_missing")
        provenance.append(dict(method=method, slot=slot, observed_at=iso(utcnow())))
        return result, slot
    try:
        first, first_slot = await rpc("getMultipleAccounts", [[candidate["pool_address"]],
            {"encoding": "base64", "commitment": "confirmed"}])
        if not isinstance(first.get("value"), list) or len(first["value"]) != 1:
            raise ValueError("pool_surface_initial_bundle_shape")
        pool = _pool(first["value"][0], candidate)
        addresses, holder_slot, holder_complete, holder_error = [], None, False, None
        try:
            largest, holder_slot = await rpc("getTokenLargestAccounts", [pool["lp_mint"], {"commitment": "confirmed"}])
            rows = largest.get("value")
            if not isinstance(rows, list) or len(rows) > 20 or holder_slot < first_slot:
                raise ValueError("pool_surface_largest_shape_or_stale_slot")
            addresses = [str(row["address"]) for row in rows]
            if len(set(addresses)) != len(addresses):
                raise ValueError("pool_surface_duplicate_holder_account")
            holder_complete = True
        except Exception as exc:
            addresses, holder_error = [], type(exc).__name__
        keys = list(dict.fromkeys([candidate["pool_address"], pool["base_mint"], pool["quote_mint"],
            pool["lp_mint"], pool["base_vault"], pool["quote_vault"], *addresses]))
        minimum_slot = max(first_slot, holder_slot or 0)
        bundle, slot = await rpc("getMultipleAccounts", [keys,
            {"encoding": "base64", "commitment": "confirmed", "minContextSlot": minimum_slot}])
        if not isinstance(bundle.get("value"), list) or len(bundle["value"]) != len(keys) or slot < minimum_slot:
            raise ValueError("pool_surface_bundle_shape_or_stale_slot")
        received = iso(utcnow())
        out = classify_pumpswap_pool_surface(candidate, dict(zip(keys, bundle["value"])),
            observed_at=received, recorded_at=received, decision_at=received, slot=slot,
            lp_holder_addresses=addresses, holder_scan_complete=holder_complete, holder_scan_slot=holder_slot)
        out.update(rpc_count=rpc_count, rpc_provenance=provenance, holder_rpc_error=holder_error)
        return out
    except Exception as exc:
        received = iso(utcnow())
        return dict(status="UNKNOWN_RPC" if not isinstance(exc, ValueError) else "UNKNOWN_IDENTITY",
            complete=False, surface="UNKNOWN", pool_address=candidate.get("pool_address"),
            base_mint=candidate.get("base_mint"), observed_at=received, recorded_at=received,
            reason=str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
            rpc_count=rpc_count, rpc_provenance=provenance)
