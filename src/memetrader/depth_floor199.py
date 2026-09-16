"""First observed crossing of the existing executable pool floor."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .depth_cross191 import Tracker as DepthTracker


VERSION = "depth-floor199/v1"
ARM = "depth199_first_floor_cross_v1"
PARENT = "alpha149_wide_decorr_young_v1"


class Tracker(DepthTracker):
    def __init__(self, started_at: Any):
        super().__init__(started_at, crossing_multiplier=1.0, arm=ARM, version=VERSION)


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    from .depth_cross191 import policy as depth_policy

    result = deepcopy(depth_policy(parent))
    result.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="First executable original-pool depth",
        feature_contract=VERSION,
        feature_hypothesis="first_original_pool_floor_crossing",
        paired_opportunity_group="depth199_vs_depth191",
        excess_return_vs_arm="depth191_first_tradable_v1",
        description=(
            f"{VERSION}: first same-provider original-pool observation rising "
            "from below the existing execution floor to at least that floor "
            "within 300s, young pool, positive price and two buys plus a real sell. "
            "The shared floor, safety assessment and next-observed fill are unchanged. "
            "Existing frames only; higher missing-exit risk is measured in Paper."
        ),
    )
    result["entry_filter"] = {
        **result["entry_filter"], "direction": ARM,
    }
    return result
