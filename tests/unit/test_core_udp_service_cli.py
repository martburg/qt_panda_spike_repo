from __future__ import annotations

from steuerung3d.apps.core_udp_service.__main__ import _expand_targets, _expand_dev_cmd_targets


def test_expand_targets_uses_base_host() -> None:
    targets = _expand_targets(
        [],
        base="51002",
        count=2,
        base_host="0.0.0.0",
        default_target=None,
    )
    assert targets == [("0.0.0.0", 51002), ("0.0.0.0", 51003)]


def test_expand_targets_falls_back_to_default() -> None:
    targets = _expand_targets(
        [],
        base=None,
        count=0,
        base_host="10.0.0.1",
        default_target=("127.0.0.1", 51002),
    )
    assert targets == [("127.0.0.1", 51002)]


def test_expand_dev_cmd_targets_uses_host_override() -> None:
    targets = _expand_dev_cmd_targets("52001", 3, "10.10.0.5")
    assert targets == [("10.10.0.5", 52001), ("10.10.0.5", 52002), ("10.10.0.5", 52003)]
