from __future__ import annotations

from steuerung3d.apps.core_udp_service.__main__ import _expand_targets


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
