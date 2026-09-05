from memetrader.collectors import SolanaHeldAccountCollector


def test_pumpswap_transfer_edges_keep_wallet_funding_and_drop_pool_leg():
    signer = "BUYER"
    funder = "FUNDER"
    vault = "VAULT"
    tx = {
        "transaction": {"signatures": ["sig"], "message": {"accountKeys": [
            {"pubkey": signer, "signer": True}, {"pubkey": funder, "signer": False},
            {"pubkey": vault, "signer": False}, {"pubkey": "ATA", "signer": False},
        ]}},
        "meta": {"preTokenBalances": [{"accountIndex": 3, "owner": signer, "mint": "MINT"}]},
    }
    instructions = [("outer:0", {"programId": "11111111111111111111111111111111", "parsed": {
        "type": "transfer", "info": {"source": funder, "destination": signer, "lamports": 500}}}),
        ("inner:0:1", {"programId": "spl-token", "parsed": {
        "type": "transfer", "info": {"source": vault, "destination": "ATA", "amount": "9", "mint": "MINT"}}})]
    edges = SolanaHeldAccountCollector._pumpswap_observed_funding_transfers(
        tx, {signer}, {"pool_address": "POOL", "base_vault": vault, "quote_vault": "QV"}, instructions)
    assert len(edges) == 1
    assert edges[0]["source"] == funder
    assert edges[0]["destination"] == signer
    assert edges[0]["amount_raw"] == 500
