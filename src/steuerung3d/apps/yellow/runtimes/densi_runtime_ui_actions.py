from __future__ import annotations

from ..engines.densi.inputs import DensiInputs
from .densi_runtime_types import DensiRuntimeUiActionsLike


def apply_ui_actions(rt: DensiRuntimeUiActionsLike, inputs: DensiInputs) -> None:
    ui = inputs.ui
    if ui is None:
        return

    if ui.es_start_clicked:
        try:
            rt.engine.press_es_start()
            rt._log.info("ESStart pressed")
            rt._force_refresh_checkboxes = True
        except Exception:
            pass

    if ui.estop_reset_clicked:
        try:
            _word0, reset_able, _ready_for_sollvel = rt.engine.derive_estop_inputs()
            if bool(reset_able):
                rt.engine.apply_post_reset_state()
                rt._log.info("EStop reset pressed")
                rt._force_refresh_checkboxes = True
        except Exception:
            pass

    if ui.estop_all_set_clicked:
        try:
            rt.engine.set_all_estop_bits()
            rt._log.info("inject: SET ALL bits (word=0x%08X)", int(rt.engine.inj_estop_word))
            rt._force_refresh_checkboxes = True
        except Exception:
            pass

    if ui.estop_all_clear_clicked:
        try:
            rt.engine.apply_go_state()
            rt._log.info("inject: GO state (word=0x%08X)", int(rt.engine.inj_estop_word))
            rt._force_refresh_checkboxes = True
        except Exception:
            pass

    for t in list(ui.estop_bit_toggles or []):
        try:
            rt.engine.inject_estop_bit(str(t.key), bool(t.checked))
            rt._log.info(
                "inject estop %s=%s (word=0x%08X)",
                t.key,
                t.checked,
                int(rt.engine.inj_estop_word),
            )
            rt._force_refresh_checkboxes = True
        except Exception:
            pass

    if ui.diag_resync_clicked:
        try:
            rt.engine.clear_cut_markers(reset_prev=True)
        except Exception:
            pass
