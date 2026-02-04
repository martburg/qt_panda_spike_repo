from __future__ import annotations

import argparse

from steuerung3d.apps.setup_stack.__main__ import build_stack_spec_from_args
from steuerung3d.core.stack_runtime import expand_processes


def _args(**kw):
    # Mirror the setup_stack CLI defaults minimally.
    base = dict(
        joy2intent="configs/joy2intent_bindings_gamepad.toml",
        inputd="configs/inputd_gamepad.toml",
        axes="Anton,Debby",
        cmd_base=52001,
        ui_telem_base=51002,
        dev_telem_in=None,
        dev_telem_out=None,
        densi_dt=0.01,
        core_dt=0.02,
        log_level="info",
        no_inputd=False,
        no_joy2intent=False,
        no_hip=False,
        single_hip=False,
        no_densi=False,
        no_core=False,
        new_console=False,
        keep_sessions=5,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_setup_stack_wrapper_expands_expected_processes(tmp_path):
    args = _args(axes="Anton,Debby,Cecil")
    spec = build_stack_spec_from_args(args)

    # Expand into concrete processes; ensure stable naming and fanout.
    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]

    assert "core" in names
    assert "inputd" in names
    assert "joy2intent" in names
    assert "hip-Anton" in names
    assert "hip-Debby" in names
    assert "hip-Cecil" in names
    assert "densi-Anton" in names
    assert "densi-Debby" in names
    assert "densi-Cecil" in names


def test_setup_stack_single_hip_mode(tmp_path):
    args = _args(axes="Anton,Debby", single_hip=True)
    spec = build_stack_spec_from_args(args)
    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]
    assert "hip" in names  # single instance uses service name
    assert "hip-Anton" not in names


def test_setup_stack_disables_services(tmp_path):
    args = _args(no_hip=True, no_densi=True)
    spec = build_stack_spec_from_args(args)
    procs = expand_processes(spec, session_dir=tmp_path)
    names = [p.name for p in procs]
    assert not any(n.startswith("hip") for n in names)
    assert not any(n.startswith("densi") for n in names)
