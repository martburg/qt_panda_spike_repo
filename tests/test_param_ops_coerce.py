from __future__ import annotations

from typing import Any

from steuerung3d.core.command_frame import (
    ParamCancelOp,
    ParamEditBeginOp,
    ParamOp,
    ParamWriteOp,
    coerce_param_ops,
)
from steuerung3d.core.param_groups import coerce_param_group


def test_coerce_param_ops_none_and_nonlist() -> None:
    assert coerce_param_ops(None) == []
    assert coerce_param_ops({}) == []


def test_coerce_param_ops_dicts_to_dataclasses() -> None:
    raw_ops: list[object] = [
        {"type": "param_edit_begin", "group": "pos"},
        {"type": "param_write", "group": "pos", "values": {"UserMax": 1, "UserMin": -2.5}},
        {"type": "param_cancel", "group": "pos"},
    ]
    ops = coerce_param_ops(raw_ops)
    assert len(ops) == 3
    assert isinstance(ops[0], ParamEditBeginOp)
    assert isinstance(ops[1], ParamWriteOp)
    assert isinstance(ops[2], ParamCancelOp)
    assert ops[1].values["UserMax"] == 1.0
    assert ops[1].values["UserMin"] == -2.5


def test_coerce_param_ops_mixed_list_keeps_objects() -> None:
    in_ops: list[Any] = [
        ParamEditBeginOp(group="vel"),
        {"type": "param_write", "group": "vel", "values": {"VelMax": 3}},
    ]
    ops = coerce_param_ops(in_ops)
    assert len(ops) == 2
    assert isinstance(ops[0], ParamEditBeginOp)
    assert isinstance(ops[1], ParamWriteOp)
    assert ops[1].values["VelMax"] == 3.0


def test_coerce_param_group_unknown_defaults_to_pos() -> None:
    assert coerce_param_group("") == "pos"
    assert coerce_param_group("weird") == "pos"


def test_coerce_param_ops_normalizes_unknown_group_to_default() -> None:
    raw_ops: list[ParamOp | object] = [{"type": "param_cancel", "group": "mystery"}]
    ops = coerce_param_ops(raw_ops)
    assert len(ops) == 1
    assert isinstance(ops[0], ParamCancelOp)
    assert ops[0].group == "pos"
