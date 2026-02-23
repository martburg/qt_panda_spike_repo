"""Rig workflow tests (SYNC/RECOVER) are deferred.

This repo currently targets the milestone:
  - UDP telemetry discovery -> axes appear
  - HiP auto-claims an axis on cmb selection
  - manual jog is enforced by claims

The full rig workflow (participating set, anchors, arm/enter sync, recover/resync)
will be implemented later. When that lands, this test module should be re-enabled.
"""

from __future__ import annotations

import pytest

try:
    from steuerung3d.core.intents import (
        SetRigMode,
        SetDensiParticipating,
        SetDensiAnchor,
        ArmSync,
        EnterSync,
        RecoverToLastGood,
        ResyncNow,
    )
    from steuerung3d.core.rig_types import RigMode
    from steuerung3d.core.rig_logic import enforce_rig_invariants, note_densi_seen
except Exception as e:  # noqa: BLE001
    pytest.skip(
        "Rig workflow not available in this milestone (deferred). "
        "Re-enable once rig intents + rig_logic are implemented.",
        allow_module_level=True,
    )

import math

from steuerung3d.core.state import MachineState
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.intent_handler import apply_intent


def test_arm_sync_and_enter_sync() -> None:
    st = MachineState()
    st.core_mode = CoreMode.LIVE

    # Two densis online
    st.ensure_axis('A').pos = 1.0
    st.ensure_axis('B').pos = 2.0
    note_densi_seen(st, 'A')
    note_densi_seen(st, 'B')

    apply_intent(st, SetRigMode(rig_mode='SETUP_MANUAL'))
    apply_intent(st, SetDensiParticipating(device_id='A', participating=True))
    apply_intent(st, SetDensiParticipating(device_id='B', participating=True))
    apply_intent(st, SetDensiAnchor(device_id='A', x=0, y=0, z=0))
    apply_intent(st, SetDensiAnchor(device_id='B', x=1, y=0, z=0))

    apply_intent(st, ArmSync())
    assert st.rig_mode == RigMode.ARMED_SYNC

    apply_intent(st, EnterSync())
    assert st.rig_mode == RigMode.SYNC_ACTIVE
