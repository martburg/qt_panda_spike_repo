from __future__ import annotations

from steuerung3d.apps.yellow.domain.ui_banner import derive_banner_estate_from_word
from steuerung3d.apps.yellow.engines.hip.engine import HipAttachInputs, HipBannerInputs, HipEngine


def test_hip_engine_attach_state_unattached() -> None:
    eng = HipEngine()
    st = eng.compute_attach_state(
        HipAttachInputs(attached=False, modal_locked=False, last_mode="IDLE", last_estate="IDLE")
    )
    assert st.tabs_enabled is False
    assert st.setup_enabled is False
    assert st.main_amp_reset_enabled is False
    assert st.resync_enabled is False
    assert st.estop_reset_enabled is False


def test_hip_engine_attach_state_modal_locked() -> None:
    eng = HipEngine()
    st = eng.compute_attach_state(
        HipAttachInputs(attached=True, modal_locked=True, last_mode="IDLE", last_estate="IDLE")
    )
    assert st.tabs_enabled is None
    assert st.setup_enabled is False
    assert st.main_amp_reset_enabled is False
    assert st.resync_enabled is False
    assert st.estop_reset_enabled is None


def test_hip_engine_resync_gate_requires_per_axis_estate_not_global_mode() -> None:
    eng = HipEngine()
    ok_ready = eng.compute_attach_state(
        HipAttachInputs(attached=True, modal_locked=False, last_mode="LIVE", last_estate="READY")
    )
    ok_armed = eng.compute_attach_state(
        HipAttachInputs(attached=True, modal_locked=False, last_mode="READY", last_estate="ARMED")
    )
    bad_estop = eng.compute_attach_state(
        HipAttachInputs(attached=True, modal_locked=False, last_mode="IDLE", last_estate="ESTOP")
    )
    assert ok_ready.resync_enabled is True
    assert ok_armed.resync_enabled is True
    assert bad_estop.resync_enabled is False


def test_hip_engine_banner_estate_matches_banner_helper() -> None:
    eng = HipEngine()
    word = 0
    estate = eng.compute_banner_estate(HipBannerInputs(estop_word=word, within_brake_grace=False))
    legacy = derive_banner_estate_from_word(word, within_brake_grace=lambda: False)
    assert estate == legacy
