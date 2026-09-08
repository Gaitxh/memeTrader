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


class PonsV2Observer(_BoundedEvmLogObserver):
    """Observe the current Pons factory; it remains identity-only evidence."""

    CHAIN = "robinhood"
    CHAIN_ID = 4663
    FACTORY = "0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e"
    TOKEN_LAUNCHED_TOPIC = (
        "0x8d4aad4953d0ca700d468f3753aa14432d1b35b43ec6409f051fb6aa43a89607"
    )
    POOL_GRADUATED_TOPIC = (
        "0x0a44ef75df69c534f43cd6c1aa3ef8983065fe5fe79ef9e79f6494e6f258c259"
    )
    NETWORK = {"chain_id": CHAIN_ID, "rpc_url": "https://rpc.mainnet.chain.robinhood.com"}
    ADDRESSES = (FACTORY,)
    TOPICS = (TOKEN_LAUNCHED_TOPIC, POOL_GRADUATED_TOPIC)
    ERROR_PREFIX = "pons_v2"
    MAX_LOGS = 50  # Blockscout's documented maximum page size.
    INDEXED_LOGS_URL = (
        "https://robinhoodchain.blockscout.com/api/v2/addresses/"
        f"{FACTORY}/logs"
    )

    def __init__(self, existing_rpc_client: Any, existing_http_client: Any):
        super().__init__(existing_rpc_client)
        self.http = existing_http_client
        self._rpc_frontier: int | None = None

    @staticmethod
    def _address(value: Any) -> str:
        body = str(value or "").removeprefix("0x")
        if len(body) != 64 or any(char not in "0123456789abcdefABCDEF" for char in body):
            raise ValueError("pons_v2_topic_address_invalid")
        if body[:24] != "0" * 24:
            raise ValueError("pons_v2_topic_address_invalid")
        return "0x" + body[-40:].lower()

    @staticmethod
    def _word_address(word: str) -> str:
        return PonsV2Observer._address("0x" + word)

    def _decode_log(self, log: Mapping[str, Any]) -> dict[str, Any]:
        if log.get("removed") is True:
            raise ValueError("pons_v2_removed_log")
        address = str(log.get("address") or "").lower()
        topics = log.get("topics")
        if address != self.FACTORY or not isinstance(topics, list):
            raise ValueError("pons_v2_log_identity_invalid")
        topic0 = str(topics[0]).lower() if topics else ""
        data = str(log.get("data") or "")
        if (
            not data.startswith("0x")
            or any(char not in "0123456789abcdefABCDEF" for char in data[2:])
        ):
            raise ValueError("pons_v2_data_invalid")
        words = [data[2 + 64 * index:2 + 64 * (index + 1)]
                 for index in range(len(data[2:]) // 64)]
        common = {
            "chain": self.CHAIN,
            "block_number": self._hex_int(log.get("blockNumber")),
            "block_hash": str(log.get("blockHash") or ""),
            "transaction_hash": str(log.get("transactionHash") or ""),
            "log_index": self._hex_int(log.get("logIndex")),
            "factory": address,
            "version": "v2",
            "topic0": topic0,
            "evidence_kind": "evm_native_launch",
        }
        source_block_timestamp = log.get("source_block_timestamp")
        if source_block_timestamp is not None:
            value = str(source_block_timestamp)
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("pons_v2_source_block_timestamp_invalid") from exc
            common["source_block_timestamp"] = value
        if not common["block_hash"] or not common["transaction_hash"]:
            raise ValueError("pons_v2_log_identity_invalid")
        if topic0 == self.TOKEN_LAUNCHED_TOPIC:
            if len(topics) != 4 or len(words) != 3:
                raise ValueError("pons_v2_token_launched_abi_invalid")
            token = self._address(topics[1])
            return {
                **common,
                "event": "TokenLaunched",
                "token": token,
                "token_id": f"{self.CHAIN}:{token}",
                "curve": self._address(topics[2]),
                "deployer": self._address(topics[3]),
                "pair_token": self._word_address(words[0]),
                "launch_config_id": int(words[1], 16),
                "graduation_threshold": int(words[2], 16),
                # A curve is not a DEX pool. The V4 pool is derivable only after
                # graduation, so never manufacture a pool address here.
                "pool": None,
                "pool_identity": None,
            }
        if topic0 == self.POOL_GRADUATED_TOPIC:
            if len(topics) != 2 or len(words) != 3:
                raise ValueError("pons_v2_pool_graduated_abi_invalid")
            token = self._address(topics[1])
            return {
                **common,
                "event": "PoolGraduated",
                "token": token,
                "token_id": f"{self.CHAIN}:{token}",
                "position_id": int(words[0], 16),
                "token_amount": int(words[1], 16),
                "pair_token_amount": int(words[2], 16),
                "pool": None,
                "pool_identity": None,
            }
        raise ValueError("pons_v2_topic_invalid")

    def _identities(self, events: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        return list(dict.fromkeys(event["token"] for event in events)), []

    @staticmethod
    def _block_number(log: Mapping[str, Any]) -> int:
        value = log.get("blockNumber", log.get("block_number"))
        return int(str(value), 16) if str(value).startswith("0x") else int(value)

    @staticmethod
    def _indexed_log(log: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "address": log.get("address", {}).get("hash") if isinstance(log.get("address"), Mapping) else log.get("address"),
            "topics": log.get("topics"),
            "data": log.get("data"),
            "removed": False,
            "blockNumber": hex(PonsV2Observer._block_number(log)),
            "blockHash": log.get("block_hash"),
            "transactionHash": log.get("transaction_hash"),
            "logIndex": hex(int(log.get("index", log.get("log_index", 0)))),
            "source_block_timestamp": log.get("block_timestamp"),
        }

    async def observe(self, *, now: Any = None) -> dict[str, Any]:
        """Use the bounded indexed factory feed, then the existing RPC fallback."""
        del now
        requested_at = _stamp_now()
        try:
            response = await self.http.get(
                self.INDEXED_LOGS_URL, params={"items_count": self.MAX_LOGS}, ttl=0,
            )
            payload = response.json()
            logs = payload.get("items") if isinstance(payload, Mapping) else None
            if not isinstance(logs, list) or not logs or len(logs) > self.MAX_LOGS:
                raise ValueError("pons_v2_indexed_log_limit_or_shape")
            blocks = []
            for raw in logs:
                if not isinstance(raw, Mapping):
                    raise ValueError("pons_v2_indexed_log_shape")
                blocks.append(self._block_number(raw))
            indexed_head = max(blocks)
            if self._frontier is None:
                self._frontier = indexed_head
                observed_at = _stamp_now()
                result = self._result(
                    "SEEDED_NO_WINDOW", chain_id=self.CHAIN_ID, latest=indexed_head,
                    requested_at=requested_at, observed_at=observed_at,
                )
                result["confirmation_depth"] = None
                result["indexed_source"] = "blockscout_indexed"
                return result
            prior_frontier = self._frontier
            if indexed_head <= prior_frontier:
                observed_at = _stamp_now()
                result = self._result(
                    "NO_NEW_BLOCKS", chain_id=self.CHAIN_ID, latest=indexed_head,
                    requested_at=requested_at, observed_at=observed_at,
                )
                result["confirmation_depth"] = None
                result["indexed_source"] = "blockscout_indexed"
                return result
            events = []
            for raw in logs:
                block = self._block_number(raw)
                if block <= prior_frontier:
                    continue
                indexed = self._indexed_log(raw)
                topics = indexed.get("topics")
                if not isinstance(topics, list) or not topics:
                    raise ValueError("pons_v2_indexed_log_shape")
                if str(topics[0]).lower() not in self.TOPICS:
                    continue
                event = self._decode_log(indexed)
                events.append(event)
            observed_at = _stamp_now()
            for event in events:
                event["observed_at"] = observed_at
                event["recorded_at"] = observed_at
                event["source"] = "blockscout_indexed"
            self._frontier = indexed_head
            truncated = len(logs) == self.MAX_LOGS and min(blocks) > prior_frontier
            result = self._result(
                "TRUNCATED" if truncated else "OK", chain_id=self.CHAIN_ID,
                latest=indexed_head, requested_at=requested_at, observed_at=observed_at,
                events=events, from_block=prior_frontier + 1, to_block=indexed_head,
            )
            result["confirmation_depth"] = None
            result["indexed_source"] = "blockscout_indexed"
            if truncated:
                result["truncated"] = True
                result["indexed_page_limit"] = self.MAX_LOGS
            return result
        except Exception as indexed_error:
            indexed_frontier = self._frontier
            try:
                self._frontier = self._rpc_frontier
                fallback = await super().observe()
                self._rpc_frontier = self._frontier
            finally:
                self._frontier = indexed_frontier
            fallback["indexed_source"] = "rpc_fallback"
            fallback["indexed_limitation"] = (
                "Blockscout indexed logs unavailable; bounded direct RPC window used"
            )
            fallback["indexed_error"] = str(indexed_error)[:160]
            return fallback


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


__all__ = ["PonsV1Observer", "PonsV2Observer", "FourMemeObserver"]
