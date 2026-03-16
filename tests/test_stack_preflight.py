from __future__ import annotations

from pathlib import Path

from steuerung3d.core.stack_preflight import extract_bind_ports
from steuerung3d.core.stack_spec import ProcessSpec


def test_extract_bind_ports_reads_known_bind_flags() -> None:
    procs = [
        ProcessSpec(
            name="core",
            argv=[
                "python",
                "-m",
                "core",
                "--intent-in",
                "127.0.0.1:51001",
                "--dev-telem-in",
                "127.0.0.1:52020",
            ],
            log_path=Path("core.log"),
        ),
        ProcessSpec(
            name="densi-Anton",
            argv=[
                "python",
                "-m",
                "den",
                "--cmd-in",
                "127.0.0.1:52011",
                "--action-in",
                "127.0.0.1:53001",
            ],
            log_path=Path("densi.log"),
        ),
    ]
    assert extract_bind_ports(procs) == [51001, 52020, 52011, 53001]


def test_extract_bind_ports_ignores_out_targets() -> None:
    procs = [
        ProcessSpec(
            name="hip",
            argv=[
                "python",
                "-m",
                "hip",
                "--telem-in",
                "127.0.0.1:51003",
                "--intent-out",
                "127.0.0.1:51001",
                "--telem-out",
                "127.0.0.1:52020",
            ],
            log_path=Path("hip.log"),
        )
    ]
    assert extract_bind_ports(procs) == [51003]


def test_extract_bind_ports_reads_generic_in_suffix_flags() -> None:
    procs = [
        ProcessSpec(
            name="custom",
            argv=["python", "-m", "svc", "--status-in", "127.0.0.1:55001"],
            log_path=Path("custom.log"),
        )
    ]
    assert extract_bind_ports(procs) == [55001]


def test_extract_bind_ports_reads_bind_ports_from_config_io_in_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "joy2intent.toml"
    cfg.write_text(
        '[io]\nraw_in = "127.0.0.1:50100"\nintent_out = "127.0.0.1:51001"\ncontext_in = "127.0.0.1:51010"\n',
        encoding="utf-8",
    )
    procs = [
        ProcessSpec(
            name="joy2intent",
            argv=["python", "-m", "joy", "--config", str(cfg)],
            log_path=Path("joy.log"),
        )
    ]
    assert extract_bind_ports(procs) == [50100, 51010]
