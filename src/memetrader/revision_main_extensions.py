"""Pure policy revisions for main-path historical strategy slots.

Registration, revision numbering, history and execution stay with Store.  This
module only copies a policy and adds contracts expressible from existing L0
market fields.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping


REAWAKENING_MATURE_ACCELERATION_ARMS = frozenset({
    "canonical-0186f1e75b238e63",
    "canonical-058b868fbd1d8065",
    "canonical-18d8ce34c0112abb",
    "canonical-25cfdc3e9adf23df",
    "canonical-2634d7c52e35b317",
    "canonical-3028ef000f6df93d",
    "canonical-3093112db36e72a6",
    "canonical-3c89090af7e8cd6b",
    "canonical-427d6a31e0a2e604",
    "canonical-504d9582ca75a709",
    "canonical-5a16583de92bac39",
    "canonical-619d142075228d0e",
    "canonical-707c4491ca3caf89",
    "canonical-9e8b8ab496229059",
    "canonical-9fdcf1c1c121b928",
    "canonical-ac6059d9867697cd",
    "canonical-addb9efa1916afbf",
    "canonical-b1c6865d30e91ddd",
    "canonical-bcf4041ab4578717",
    "canonical-cca8c50b00503869",
    "canonical-e7b74ce032fcc5d3",
    "canonical-ef7bf4f71eeacb75",
    "canonical-efdc816cff3321dd",
    "canonical-fddc0b4e14f1836f",
    "dex-successor-014-1375c87c13cb1de1",
    "dex-successor-019-1d5937dec4e156d4",
    "dex-successor-038-45d45a6774225417",
    "dex-successor-070-8a6c18233b0c33fd",
    "dex-successor-074-94e2a27a7c53d44c",
    "dex-successor-106-db27127f672cbae7",
    "dex-successor-121-fa93589262a321f9",
    "dex-successor-122-fa9e8436a3a39c63",
})

BALANCED_HARVEST_FLOW_EXIT_ARMS = frozenset({
    "canonical-0df3639e1824ad0f",
    "canonical-22dbe223b3814f7f",
    "canonical-2d3874b5b4dfe162",
    "canonical-744153cee3d16c08",
    "canonical-83fdc6be4ed5e6bf",
    "canonical-d276043eb5aa27c2",
    "canonical-d785aa5181f97422",
    "canonical-eaaf188e7835376f",
})


def revise_main_extension(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copied policy with one of the bounded main-path revisions."""
    revised = copy.deepcopy(dict(policy))
    arm_id = str(revised.get("arm_id") or "")
    if arm_id in REAWAKENING_MATURE_ACCELERATION_ARMS:
        entry_filter = copy.deepcopy(revised.get("entry_filter") or {})
        entry_filter.update({
            "min_age_seconds": 3_600.0,
            "max_age_seconds_exclusive": 21_600.0,
            "min_m5_trades": 8,
            "min_m5_volume_usd": 500.0,
        })
        revised.update({
            "entry_family": "flow_burst",
            "entry_filter": entry_filter,
            "revision_equivalence_group": "main_mature_flow_acceleration_v2",
            "revision_reason": (
                "32个历史槽位共享严格6小时静默复苏入口，旧期因此只形成一个共同机会；"
                "这不是32个独立样本，也不足以持续检验四种退出"
            ),
            "revision_changes": [
                "以现有main flow_burst的三倍交易或成交额加速作为成熟再启动入口",
                "只接受池龄1至6小时且5分钟至少8笔、成交额至少500U的机会",
                "四种既有退出合同继续独立，不把同一cohort计作32个机会",
            ],
            "revision_basis": (
                "旧期32臂只命中同一cohort 10237；新入口复用已运行的main flow_burst"
                "加速和30分钟episode语义，无需新增API、历史回放或isolated dispatcher"
            ),
        })
    elif arm_id in BALANCED_HARVEST_FLOW_EXIT_ARMS:
        revised.update({
            "zero_activity_grace_minutes": 15.0,
            "flow_grace_minutes": 15.0,
            "minimum_buy_ratio": 0.45,
            "revision_equivalence_group": "broad_balanced_harvest_flow_exit_v2",
            "revision_reason": (
                "均衡收获合同可长期等待高止盈档位，原退出没有利用持仓后已有的"
                "零活跃或卖方占优L0证据回收资本"
            ),
            "revision_changes": [
                "保留Broad主入场、原硬止损、追踪止盈、分档止盈和最长持有",
                "持有15分钟后，5分钟零活跃或买入占比低于45%时触发现有L0退出",
            ],
            "revision_basis": (
                "持仓原池帧已提供volume/buys/sells；该退出与A组入场活跃门不同，"
                "不使用受污染旧收益证明优劣"
            ),
        })
    return revised


__all__ = [
    "REAWAKENING_MATURE_ACCELERATION_ARMS",
    "BALANCED_HARVEST_FLOW_EXIT_ARMS",
    "revise_main_extension",
]
