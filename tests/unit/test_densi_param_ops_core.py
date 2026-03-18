import sys
from typing import Mapping

sys.path.insert(0, "src")

from steuerung3d.apps.yellow.engines.densi.param_ops import apply_densi_param_ops
from steuerung3d.core.command_frame import ParamEditBeginOp, ParamWriteOp
from steuerung3d.core.state import MachineState


def test_param_ops_begin_write_ends_session_and_applies_values():
    st = MachineState()

    def norm_pos(vals: Mapping[str, float]) -> dict[str, float]:
        # simulate normalization: swap min/max if needed
        v = dict(vals)
        if "HardMin" in v and "HardMax" in v and v["HardMin"] > v["HardMax"]:
            v["HardMin"], v["HardMax"] = v["HardMax"], v["HardMin"]
        return v

    def norm_guider(vals: Mapping[str, float]) -> dict[str, float]:
        return dict(vals)

    def enf_pos(vals: Mapping[str, float]) -> dict[str, float]:
        # simulate enforcement: clamp
        v = dict(vals)
        if "HardMax" in v:
            v["HardMax"] = min(v["HardMax"], 10.0)
        return v

    def enf_guider(vals: Mapping[str, float]) -> dict[str, float]:
        return dict(vals)

    ops = [
        ParamEditBeginOp(group="pos"),
        ParamWriteOp(group="pos", values={"HardMin": 5.0, "HardMax": 12.0}),
    ]

    res = apply_densi_param_ops(
        state=st,
        param_ops=ops,
        allow=True,
        normalize_pos_chain=norm_pos,
        normalize_guider_range=norm_guider,
        enforce_pos_chain=enf_pos,
        enforce_guider_minmax=enf_guider,
    )

    assert st.param_edit_active is False
    assert st.param_edit_group == ""
    assert st.params["HardMin"] == 5.0
    assert st.params["HardMax"] == 10.0
    assert res.applied_values["HardMax"] == 10.0


def test_param_ops_rejects_mismatched_group_when_session_active():
    st = MachineState(param_edit_active=True, param_edit_group="pos")

    def ident(vals: Mapping[str, float]) -> dict[str, float]:
        return dict(vals)

    res = apply_densi_param_ops(
        state=st,
        param_ops=[ParamWriteOp(group="guider", values={"PosMin": 1.0})],
        allow=True,
        normalize_pos_chain=ident,
        normalize_guider_range=ident,
        enforce_pos_chain=ident,
        enforce_guider_minmax=ident,
    )

    assert st.params == {}
    assert res.applied_values == {}


def test_param_ops_allow_false_ignores_everything():
    st = MachineState()

    def boom(vals: Mapping[str, float]) -> dict[str, float]:
        raise AssertionError("should not be called")

    res = apply_densi_param_ops(
        state=st,
        param_ops=[ParamWriteOp(group="pos", values={"HardMax": 2.0})],
        allow=False,
        normalize_pos_chain=boom,
        normalize_guider_range=boom,
        enforce_pos_chain=boom,
        enforce_guider_minmax=boom,
    )
    assert st.params == {}
    assert res.applied_values == {}
