from qt_panda_spike.app import _build_parser


def test_parser_defaults_disable_debug_features() -> None:
    parser = _build_parser()
    ns = parser.parse_args([])

    assert ns.pick_debug is False
    assert ns.show_dome is False
    assert ns.pick_log == "pick_diagnostics.jsonl"


def test_parser_accepts_debug_flags() -> None:
    parser = _build_parser()
    ns = parser.parse_args(["--pick-debug", "--show-dome", "--pick-log", "logs/out.jsonl"])

    assert ns.pick_debug is True
    assert ns.show_dome is True
    assert ns.pick_log == "logs/out.jsonl"
