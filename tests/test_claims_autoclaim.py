from __future__ import annotations

import pytest

from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ClaimAxis, EnableAxis, JogAxis, ReleaseAxis, RequestAxisLease
from steuerung3d.core.state import MachineState


def test_claim_axis_idempotent_and_exclusive():
    st = MachineState()
    apply_intent(st, ClaimAxis(axis_id="Anton", hip_id="hipA", req_id="r1"))
    assert st.axis_claims["Anton"] == "hipA"
    assert "r1" in st.core_acks

    # Idempotent claim by same HIP
    apply_intent(st, ClaimAxis(axis_id="Anton", hip_id="hipA", req_id="r2"))
    assert st.axis_claims["Anton"] == "hipA"
    assert "r2" in st.core_acks

    # Deny claim by different HIP
    apply_intent(st, ClaimAxis(axis_id="Anton", hip_id="hipB", req_id="r3"))
    assert st.axis_claims["Anton"] == "hipA"
    assert "r3:deny:hipA" in st.core_acks


def test_release_axis_only_by_owner():
    st = MachineState()
    apply_intent(st, ClaimAxis(axis_id="Anton", hip_id="hipA", req_id="r1"))
    assert st.axis_claims["Anton"] == "hipA"

    # Non-owner release: should not clear
    apply_intent(st, ReleaseAxis(axis_id="Anton", hip_id="hipB", req_id="r2"))
    assert st.axis_claims["Anton"] == "hipA"

    # Owner release: clears
    apply_intent(st, ReleaseAxis(axis_id="Anton", hip_id="hipA", req_id="r3"))
    assert "Anton" not in st.axis_claims
    assert "r3" in st.core_acks


def test_claim_enforces_enable_and_jog():
    st = MachineState()

    # Enable/Jog are LIVE-gated: mark core LIVE first
    st.core_mode = CoreMode.LIVE

    apply_intent(st, ClaimAxis(axis_id="Anton", hip_id="hipA", req_id="r1"))
    apply_intent(st, RequestAxisLease(axis_id="Anton", hip_id="hipA", req_id="lease-1"))

    # Wrong HIP cannot enable (claim exists)
    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hipB"))
    assert st.axis_cmd["Anton"].enable is False
    assert abs(st.axis_cmd["Anton"].vel - 0.0) < 1e-9

    # Owner can enable
    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hipA"))
    assert st.axis_cmd["Anton"].enable is True

    # Owner can jog (when enabled)
    apply_intent(st, JogAxis(axis_id="Anton", vel=0.5, hip_id="hipA"))
    assert abs(st.axis_cmd["Anton"].vel - 0.5) < 1e-9

    # Wrong HIP cannot override jog
    apply_intent(st, JogAxis(axis_id="Anton", vel=2.0, hip_id="hipB"))
    assert abs(st.axis_cmd["Anton"].vel - 0.5) < 1e-9

    # Backward-compat: if claim exists and hip_id missing -> ignored
    apply_intent(st, JogAxis(axis_id="Anton", vel=3.0, hip_id=""))
    assert abs(st.axis_cmd["Anton"].vel - 0.5) < 1e-9


def test_claim_surface_is_mirrored_into_densi_registry_and_bulk_release() -> None:
    st = MachineState()

    st.set_axis_claim("Anton", "hipA")
    st.set_axis_claim("Debby", "hipA")
    st.set_axis_claim("Cecil", "hipB")

    assert st.densi_registry["Anton"].claimed_by_hip == "hipA"
    assert st.densi_registry["Debby"].claimed_by_hip == "hipA"
    assert st.densi_registry["Cecil"].claimed_by_hip == "hipB"

    released = st.clear_claims_for_hip("hipA")

    assert released == ["Anton", "Debby"]
    assert st.densi_registry["Anton"].claimed_by_hip == ""
    assert st.densi_registry["Debby"].claimed_by_hip == ""
    assert st.densi_registry["Cecil"].claimed_by_hip == "hipB"
    assert st.axis_claims == {"Cecil": "hipB"}
