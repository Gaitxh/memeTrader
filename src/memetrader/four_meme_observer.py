"""Pure decoder for the bounded native Four.meme discovery events."""
from __future__ import annotations

from typing import Any, Mapping


TOKEN_MANAGER2 = "0x5c952063c7fc8610ffdb798152d69f0b9550762b"
EVENT_SIGNATURES = {
    "TokenCreate": "TokenCreate(address,address,uint256,string,string,uint256,uint256,uint256)",
    "LiquidityAdded": "LiquidityAdded(address,uint256,address,uint256)",
}
EVENT_TOPICS = {
    "TokenCreate": "0x396d5e902b675b032348d3d2e9517ee8f0c4a926603fbc075d3d282ff00cad20",
    "LiquidityAdded": "0xc18aa71171b358b706fe3dd345299685ba21a5316c66ffa9e319268b033c44b0",
}


def _address(word: str) -> str:
    if len(word) != 64 or any(char not in "0123456789abcdefABCDEF" for char in word) or word[:24] != "0" * 24:
        raise ValueError("four_meme_address_word_invalid")
    return "0x" + word[-40:].lower()


def _word(data: str, index: int) -> str:
    start = 2 + index * 64
    if len(data) < start + 64:
        raise ValueError("four_meme_data_truncated")
    return data[start:start + 64]


def _dynamic_string(data: str, offset_word: str) -> str:
    offset = int(offset_word, 16)
    if offset < 256 or offset % 32:
        raise ValueError("four_meme_string_offset_invalid")
    start = 2 + offset * 2
    if start + 64 > len(data):
        raise ValueError("four_meme_string_offset_invalid")
    length = int(data[start:start + 64], 16)
    end = start + 64 + length * 2
    if length > 512 or end > len(data):
        raise ValueError("four_meme_string_bounds_invalid")
    try:
        return bytes.fromhex(data[start + 64:end]).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("four_meme_string_invalid") from exc


def decode_four_meme_log(log: Mapping[str, Any]) -> dict[str, Any]:
    """Decode only TokenCreate/LiquidityAdded; no price, pool or trade claim."""
    if str(log.get("address") or "").lower() != TOKEN_MANAGER2:
        raise ValueError("four_meme_contract_identity_invalid")
    topics = log.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("four_meme_topics_missing")
    event_name = str(log.get("event_name") or "")
    topic = str(topics[0] or "").lower()
    event_name = next((name for name, value in EVENT_TOPICS.items() if value == topic), None)
    if event_name is None:
        raise ValueError("four_meme_topic_invalid")
    supplied_name = str(log.get("event_name") or "")
    if supplied_name and supplied_name != event_name:
        raise ValueError("four_meme_event_name_mismatch")
    data = str(log.get("data") or "")
    if not data.startswith("0x") or len(data) % 2:
        raise ValueError("four_meme_data_invalid")
    out: dict[str, Any] = {"event": event_name, "contract": TOKEN_MANAGER2,
        "chain": "bsc", "raw_data": data,
        "block_number": int(str(log.get("blockNumber") or "0x0"), 16),
        "block_hash": str(log.get("blockHash") or ""),
        "transaction_hash": str(log.get("transactionHash") or ""),
        "log_index": int(str(log.get("logIndex") or "0x0"), 16)}
    if log.get("removed") is True:
        raise ValueError("four_meme_removed_log")
    if not out["block_hash"] or not out["transaction_hash"]:
        raise ValueError("four_meme_receipt_identity_missing")
    if event_name == "TokenCreate":
        if len(data) < 2 + 64 * 8:
            raise ValueError("four_meme_token_create_truncated")
        out.update({"creator": _address(_word(data, 0)), "token": _address(_word(data, 1)),
                    "request_id": int(_word(data, 2), 16),
                    "name": _dynamic_string(data, _word(data, 3)),
                    "symbol": _dynamic_string(data, _word(data, 4)),
                    "total_supply": int(_word(data, 5), 16),
                    "launch_time": int(_word(data, 6), 16),
                    "launch_fee": int(_word(data, 7), 16)})
        return out
    if len(data) != 2 + 64 * 4:
        raise ValueError("four_meme_liquidity_data_invalid")
    out.update({"base": _address(_word(data, 0)), "offers": int(_word(data, 1), 16),
                "quote": _address(_word(data, 2)), "funds": int(_word(data, 3), 16)})
    return out
