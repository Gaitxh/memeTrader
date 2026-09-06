"""Bounded, read-only native launch-event observers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _stamp_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _BoundedEvmLogObserver:
    CHAIN = ""
    CHAIN_ID = 0
    NETWORK: Mapping[str, Any] = {}
    ADDRESSES: tuple[str, ...] = ()
    TOPICS: tuple[str, ...] = ()
    ERROR_PREFIX = "evm_native"
    CONFIRMATIONS = 3
    MAX_BLOCKS = 100
    MAX_LOGS = 200

    def __init__(self, existing_rpc_client: Any):
        self.rpc = existing_rpc_client
        self._frontier: int | None = None

    @staticmethod
    def _hex_int(value: Any) -> int:
        return int(str(value), 16)

    def _decode_log(self, log: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _identities(self, events: list[dict[str, Any]]) -> tuple[list[str], list[Any]]:
        raise NotImplementedError

    def _result(self, status: str, *, chain_id: int, latest: int,
                requested_at: str, observed_at: str, events=(),
                from_block: int | None = None, to_block: int | None = None,
                skipped_blocks: int = 0) -> dict[str, Any]:
        event_list = list(events)
        tokens, pools = self._identities(event_list)
        result = {
            "status": status,
            "chain": self.CHAIN,
            "chain_id": chain_id,
            "block_number": latest,
            "confirmation_depth": self.CONFIRMATIONS,
            "finality": False,
            "frontier": self._frontier,
            "skipped_blocks": skipped_blocks,
            "events": event_list,
            "tokens": tokens,
            "pools": pools,
            "requested_at": requested_at,
            "observed_at": observed_at,
            "recorded_at": observed_at,
        }
        if from_block is not None:
            result["from_block"] = from_block
        if to_block is not None:
            result["to_block"] = to_block
        return result

    async def observe(self, *, now: Any = None) -> dict[str, Any]:
        """Read only the newest bounded three-confirmation block window."""
        del now  # Receipt availability is the actual RPC completion time.
        requested_at = _stamp_now()
        try:
            chain_id = self._hex_int(
                await self.rpc._rpc(self.NETWORK, "eth_chainId", [])
            )
            if chain_id != self.CHAIN_ID:
                raise ValueError(f"{self.ERROR_PREFIX}_chain_mismatch")
            latest = self._hex_int(
                await self.rpc._rpc(self.NETWORK, "eth_blockNumber", [])
            )
            confirmed_head = max(0, latest - self.CONFIRMATIONS)
            if self._frontier is None:
                self._frontier = confirmed_head
                observed_at = _stamp_now()
                return self._result(
                    "SEEDED_NO_WINDOW", chain_id=chain_id, latest=latest,
                    requested_at=requested_at, observed_at=observed_at,
                )
            natural_from = self._frontier + 1
            if natural_from > confirmed_head:
                observed_at = _stamp_now()
                return self._result(
                    "NO_NEW_BLOCKS", chain_id=chain_id, latest=latest,
                    requested_at=requested_at, observed_at=observed_at,
                )
            from_block = max(natural_from, confirmed_head - self.MAX_BLOCKS + 1)
            skipped_blocks = max(0, from_block - natural_from)
            to_block = confirmed_head
            logs = await self.rpc._rpc(self.NETWORK, "eth_getLogs", [{
                "fromBlock": hex(from_block),
                "toBlock": hex(to_block),
                "address": list(self.ADDRESSES),
                "topics": [list(self.TOPICS)],
            }])
            if not isinstance(logs, list) or len(logs) > self.MAX_LOGS:
                raise ValueError(f"{self.ERROR_PREFIX}_log_limit_or_shape")
            events = []
            for raw in logs:
                if not isinstance(raw, Mapping):
                    raise ValueError(f"{self.ERROR_PREFIX}_log_identity_invalid")
                event = self._decode_log(raw)
                if not from_block <= int(event["block_number"]) <= to_block:
                    raise ValueError(f"{self.ERROR_PREFIX}_log_block_out_of_range")
                events.append(event)
            observed_at = _stamp_now()
            for event in events:
                event["observed_at"] = observed_at
                event["recorded_at"] = observed_at
            self._frontier = to_block
            return self._result(
                "OK", chain_id=chain_id, latest=latest,
                requested_at=requested_at, observed_at=observed_at,
                events=events, from_block=from_block, to_block=to_block,
                skipped_blocks=skipped_blocks,
            )
        except Exception as exc:
            observed_at = _stamp_now()
            return {
                "status": "ERROR",
                "chain": self.CHAIN,
                "error": str(exc),
                "frontier": self._frontier,
                "events": [],
                "tokens": [],
                "pools": [],
                "requested_at": requested_at,
                "observed_at": observed_at,
                "recorded_at": observed_at,
            }


class PonsV1Observer(_BoundedEvmLogObserver):
    CHAIN = "robinhood"
    CHAIN_ID = 4663
    TOPIC0 = "0xdb51ea9ad51ab453a65a4cb7e60c3cb378c9501bb002609f8f97778fb6c4235a"
    FACTORIES = {
        "0xa5aab3f0c6eeadf30ef1d3eb997108e976351feb": "active",
        "0x0c37a24f5d23a486fa692d1500881d698b1f77a4": "legacy",
    }
    NETWORK = {"chain_id": CHAIN_ID, "rpc_url": "https://rpc.mainnet.chain.robinhood.com"}
    ADDRESSES = tuple(FACTORIES)
    TOPICS = (TOPIC0,)
    ERROR_PREFIX = "pons_v1"

    @staticmethod
    def _address(topic: Any) -> str:
        value = str(topic or "")
        body = value[2:] if value.startswith("0x") else ""
        if (
            len(body) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in body)
            or body[:24] != "0" * 24
        ):
            raise ValueError("pons_v1_topic_address_invalid")
        return "0x" + body[-40:].lower()

    def _decode_log(self, log: Mapping[str, Any]) -> dict[str, Any]:
        if log.get("removed") is True:
            raise ValueError("pons_v1_removed_log")
        address = str(log.get("address") or "").lower()
        topics = log.get("topics")
        if address not in self.FACTORIES or not isinstance(topics, list):
            raise ValueError("pons_v1_log_identity_invalid")
        if len(topics) != 4 or str(topics[0]).lower() != self.TOPIC0:
            raise ValueError("pons_v1_topic_invalid")
        data = str(log.get("data") or "")
        if (
            not data.startswith("0x")
            or len(data) != 2 + 64 * 7
            or any(char not in "0123456789abcdefABCDEF" for char in data[2:])
        ):
            raise ValueError("pons_v1_data_invalid")
        words = [data[2 + 64 * i:2 + 64 * (i + 1)] for i in range(7)]
        token = self._address(topics[1])
        pool = self._address("0x" + words[1])
        event = {
            "chain": self.CHAIN,
            "event": "Launch",
            "token": token,
            "token_id": f"{self.CHAIN}:{token}",
            "deployer": self._address(topics[2]),
            "dex_factory": self._address(topics[3]),
            "pair_token": self._address("0x" + words[0]),
            "pool": pool,
            "pool_identity": pool,
            "dex_id": int(words[2], 16),
            "launch_config_id": int(words[3], 16),
            "position_id": int(words[4], 16),
            "restrictions_end_block": int(words[5], 16),
            "initial_buy_amount": int(words[6], 16),
            "block_number": self._hex_int(log.get("blockNumber")),
            "block_hash": str(log.get("blockHash") or ""),
            "transaction_hash": str(log.get("transactionHash") or ""),
            "log_index": self._hex_int(log.get("logIndex")),
            "factory": address,
            "version": self.FACTORIES[address],
            "topic0": self.TOPIC0,
        }
        if not event["block_hash"] or not event["transaction_hash"]:
            raise ValueError("pons_v1_log_identity_invalid")
        return event

    def _identities(self, events: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        return (
            list(dict.fromkeys(event["token"] for event in events)),
            list(dict.fromkeys(event["pool"] for event in events)),
        )


class FourMemeObserver(_BoundedEvmLogObserver):
    CHAIN = "bsc"
    CHAIN_ID = 56
    NETWORK = {"chain_id": CHAIN_ID, "rpc_url": "https://bsc-dataseed.bnbchain.org"}
    ERROR_PREFIX = "four_meme"

    def __init__(self, existing_rpc_client: Any):
        from .four_meme_observer import EVENT_TOPICS, TOKEN_MANAGER2

        self.ADDRESSES = (TOKEN_MANAGER2,)
        self.TOPICS = tuple(EVENT_TOPICS.values())
        super().__init__(existing_rpc_client)

    def _decode_log(self, log: Mapping[str, Any]) -> dict[str, Any]:
        from .four_meme_observer import decode_four_meme_log

        event = decode_four_meme_log(log)
        token = event.get("token") or event.get("base")
        if token:
            event["token"] = token
            event["token_id"] = f"bsc:{token}"
        if event["event"] == "LiquidityAdded":
            event["pool_identity"] = {
                "base": event["base"],
                "quote": event["quote"],
                "source_contract": event["contract"],
            }
        else:
            event["pool_identity"] = None
        return event

    def _identities(self, events: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]]]:
        tokens = list(dict.fromkeys(
            event["token"] for event in events if event.get("token")
        ))
        pools = []
        seen = set()
        for event in events:
            identity = event.get("pool_identity")
            if not isinstance(identity, Mapping):
                continue
            key = (identity["base"], identity["quote"], identity["source_contract"])
            if key not in seen:
                seen.add(key)
                pools.append(dict(identity))
        return tokens, pools


__all__ = ["PonsV1Observer", "FourMemeObserver"]
