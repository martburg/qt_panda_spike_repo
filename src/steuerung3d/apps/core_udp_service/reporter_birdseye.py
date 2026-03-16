from __future__ import annotations

from collections.abc import Sequence

from .birds_eye_facts import build_motion_facts, compute_age_facts, compute_level
from .birds_eye_fields import build_fields, build_summary
from .birds_eye_types import (
    BirdsEyeSnapLike,
    BirdsEyeStateLike,
    BirdsEyeStatusLike,
    LastIntentsMetaLike,
    LastSeenLike,
)


def emit_birds_eye_status(
    *,
    status: BirdsEyeStatusLike | None,
    snap: BirdsEyeSnapLike,
    state: BirdsEyeStateLike,
    router: object,
    axis_ids: Sequence[str],
    last_intents_meta: LastIntentsMetaLike,
    last_seen: LastSeenLike,
) -> None:
    if status is None:
        return

    try:
        age_facts = compute_age_facts(last_seen=last_seen)
        level, estop_v, fault_v, mode_v = compute_level(snap=snap, age_facts=age_facts)
        motion_facts = build_motion_facts(
            snap=snap,
            state=state,
            router=router,
            axis_ids=axis_ids,
            last_intents_meta=last_intents_meta,
        )
        status.emit_every(
            level=level,
            summary=build_summary(
                mode_v=mode_v,
                state=state,
                motion_facts=motion_facts,
                last_intents_meta=last_intents_meta,
            ),
            fields=build_fields(
                snap=snap,
                state=state,
                mode_v=mode_v,
                estop_v=estop_v,
                fault_v=fault_v,
                age_facts=age_facts,
                motion_facts=motion_facts,
                last_intents_meta=last_intents_meta,
            ),
        )
    except Exception:
        return
