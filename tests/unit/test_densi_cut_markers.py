from __future__ import annotations

from steuerung3d.apps.yellow.engines.densi.cut_markers import clear_cut_markers, maybe_latch_cut_markers
from steuerung3d.core.state import MachineState


def test_clear_cut_markers_resets_params_and_prev_state() -> None:
    st = MachineState()
    st.ensure_axis("A")
    st.estop = True
    st.params["CutPos"] = 1.0
    st.params["CutVel"] = 2.0
    st.params["CutTime"] = 3.0
    st.params["PosDiffFor"] = 4.0

    res = clear_cut_markers(state=st, reset_prev=True, prev_estop_state=False)
    cut_valid, cut_pos, cut_vel, cut_time, tok, prev_estop = res

    assert cut_valid is False
    assert cut_pos == 0.0
    assert cut_vel == 0.0
    assert cut_time == 0.0
    assert tok == ""
    assert prev_estop is True
    assert st.params["CutPos"] == 0.0
    assert st.params["CutVel"] == 0.0
    assert st.params["CutTime"] == 0.0
    assert st.params["PosDiffFor"] == 0.0


def test_maybe_latch_cut_markers_latches_on_edge() -> None:
    st = MachineState()
    st.ensure_axis("A")
    st.axes["A"].pos = 1.25
    st.axes["A"].vel = -0.5
    st.t_s = 12.5

    res = maybe_latch_cut_markers(
        state=st,
        axis_ids=["A"],
        estop_edge=True,
        cut_valid=False,
        now_token=lambda: "TOK",
        cut_pos_m=0.0,
        cut_vel_mps=0.0,
        cut_time_s=0.0,
        systemtime_tok="",
    )
    cut_valid, cut_pos, cut_vel, cut_time, tok = res

    assert cut_valid is True
    assert cut_pos == 1.25
    assert cut_vel == -0.5
    assert cut_time == 12.5
    assert tok == "TOK"
    assert st.params["SystemTime"] == "TOK"
    assert st.params["CutPos"] == 1.25
    assert st.params["CutVel"] == -0.5
    assert st.params["CutTime"] == 12.5
    assert st.params["PosDiffFor"] == 0.0
