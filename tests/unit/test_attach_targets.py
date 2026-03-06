from __future__ import annotations

from steuerung3d.core.attach_targets import claim_owner_from_snapshot, list_attachable_leaf_targets
from steuerung3d.core.telemetry import DensiTelemetry, TelemetrySnapshot


def _snap() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={},
        densis={
            "Anton": DensiTelemetry(
                device_id="Anton", online=True, claimed_by_hip="", last_seen_age_ticks=0
            ),
            "Debby": DensiTelemetry(
                device_id="Debby", online=True, claimed_by_hip="hip-b", last_seen_age_ticks=0
            ),
            "Cecil": DensiTelemetry(
                device_id="Cecil", online=True, claimed_by_hip="hip-a", last_seen_age_ticks=0
            ),
            "Burt": DensiTelemetry(
                device_id="Burt", online=False, claimed_by_hip="", last_seen_age_ticks=999
            ),
        },
    )


def test_claim_owner_prefers_densi_registry_surface() -> None:
    snap = _snap()
    assert claim_owner_from_snapshot(snap, "Debby") == "hip-b"
    assert claim_owner_from_snapshot(snap, "Anton") == ""


def test_attachable_leaf_targets_show_free_and_self_owned_only() -> None:
    snap = _snap()
    assert list_attachable_leaf_targets(snap, hip_id="hip-a") == ["Anton", "Cecil"]


def test_attachable_leaf_targets_keep_selected_even_if_offline() -> None:
    snap = _snap()
    assert list_attachable_leaf_targets(snap, hip_id="hip-a", include_selected="Burt") == [
        "Anton",
        "Burt",
        "Cecil",
    ]
