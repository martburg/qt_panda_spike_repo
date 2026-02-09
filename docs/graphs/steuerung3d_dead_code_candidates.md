# Dead code candidates (static scan)

## High confidence: modules not imported by any other module or tests

- `steuerung3d.adapters.plc.plc_device` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/adapters/plc/plc_device.py)
- `steuerung3d.adapters.plc_twincat_legacy.status_decode` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/adapters/plc_twincat_legacy/status_decode.py)
- `steuerung3d.apps.joy2intent.filters` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/apps/joy2intent/filters.py)
- `steuerung3d.config.cli_client_config` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/config/cli_client_config.py)
- `steuerung3d.config.core_service_config` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/config/core_service_config.py)
- `steuerung3d.config.dev_stack_config` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/config/dev_stack_config.py)
- `steuerung3d.config.replay_player_config` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/config/replay_player_config.py)
- `steuerung3d.core.axis_accessors` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/core/axis_accessors.py)
- `steuerung3d.core.commands` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/core/commands.py)
- `steuerung3d.core.controllers.legacy_twincat_fsm` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/core/controllers/legacy_twincat_fsm.py)
- `steuerung3d.core.generic_axis_telemetry` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/core/generic_axis_telemetry.py)
- `steuerung3d.core.inmem_bus` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/core/inmem_bus.py)
- `steuerung3d.protocol.test_protocol_import` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/protocol/test_protocol_import.py)
- `steuerung3d.protocol.udp_link` (/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/protocol/udp_link.py)

## High confidence: defs with zero inbound references (calls/refs/imports) in src+tests

- `steuerung3d.adapters.plc.line_codec.coerce` (function) @ line_codec.py:121
- `steuerung3d.adapters.plc.plc_device.PlcDevice` (class) @ plc_device.py:18
- `steuerung3d.adapters.plc_twincat_legacy.codec._split_fields` (function) @ codec.py:9
- `steuerung3d.adapters.plc_twincat_legacy.codec.parse_bool_str` (function) @ codec.py:30
- `steuerung3d.adapters.plc_twincat_legacy.status_decode.decode_enabled` (function) @ status_decode.py:12
- `steuerung3d.adapters.plc_twincat_legacy.status_decode.decode_estop_active` (function) @ status_decode.py:3
- `steuerung3d.adapters.plc_twincat_legacy.status_decode.decode_fault_active` (function) @ status_decode.py:7
- `steuerung3d.apps.joy2intent.filters.clamp` (function) @ filters.py:20
- `steuerung3d.apps.joy2intent.filters.deadzone_expo` (function) @ filters.py:4
- `steuerung3d.apps.plc_sim_ui.__main__.hline` (function) @ __main__.py:119
- `steuerung3d.apps.replay_player.__main__._plant_integrate_x` (function) @ __main__.py:87
- `steuerung3d.apps.yellow.ui_shell.parse_role` (function) @ ui_shell.py:284
- `steuerung3d.config.cli_client_config.load_cli_client_config` (function) @ cli_client_config.py:27
- `steuerung3d.config.core_service_config.load_core_service_config` (function) @ core_service_config.py:28
- `steuerung3d.config.dev_stack_config.load_dev_stack_config` (function) @ dev_stack_config.py:28
- `steuerung3d.config.replay_player_config.load_replay_player_config` (function) @ replay_player_config.py:26
- `steuerung3d.core.axis_accessors.legacy_tel_or_default` (function) @ axis_accessors.py:3
- `steuerung3d.core.controllers.legacy_twincat_fsm.LegacyTwinCATAxisFSM` (class) @ legacy_twincat_fsm.py:29
- `steuerung3d.core.inmem_bus.InMemBus` (class) @ inmem_bus.py:12
- `steuerung3d.core.ramp._clamp` (function) @ ramp.py:53
- `steuerung3d.core.rig_logic.freeze_config` (function) @ rig_logic.py:60
- `steuerung3d.core.rig_logic.rig_debug_dict` (function) @ rig_logic.py:223
- `steuerung3d.core.rig_logic.start_recover_to_last_good` (function) @ rig_logic.py:103
- `steuerung3d.core.rig_logic.start_resync_now` (function) @ rig_logic.py:116
- `steuerung3d.core.rig_logic.unfreeze_config` (function) @ rig_logic.py:74
- `steuerung3d.core.rig_logic.validate_can_freeze` (function) @ rig_logic.py:78
- `steuerung3d.core.stack_loader.merge_overrides` (function) @ stack_loader.py:216
- `steuerung3d.core.stack_meta._now_s` (function) @ stack_meta.py:20
- `steuerung3d.core.stack_meta.iter_session_dirs` (function) @ stack_meta.py:115
- `steuerung3d.core.stack_meta.resolve_session_dir` (function) @ stack_meta.py:122
- `steuerung3d.core.stack_runtime._now_ts` (function) @ stack_runtime.py:29
- `steuerung3d.legacy.drive_status_decoder.decode_drive_status` (function) @ drive_status_decoder.py:84
- `steuerung3d.legacy_program.Decoder.Decode` (class) @ Decoder.py:1
- `steuerung3d.protocol.estop_bits.checkbox_name` (function) @ estop_bits.py:116
- `steuerung3d.protocol.estop_bits.dot_name` (function) @ estop_bits.py:121
- `steuerung3d.protocol.estop_bits.get_bit` (function) @ estop_bits.py:86
- `steuerung3d.protocol.recording.LoggedTransportV2` (class) @ recording.py:142
- `steuerung3d.protocol.test_protocol_import.test_raw_controls_codec_roundtrip` (function) @ test_protocol_import.py:9
- `steuerung3d.protocol.test_protocol_import.test_udp_channels_import_smoke` (function) @ test_protocol_import.py:5
- `steuerung3d.protocol.transport.InMemTransportV2` (class) @ transport.py:94
- `steuerung3d.util.heartbeat.RateLimiter` (class) @ heartbeat.py:27
- `steuerung3d.util.log_context.child_env` (function) @ log_context.py:49

## Parse errors / non-Python-3 files

- `/mnt/data/repo/dev-chore-restructure-layout/src/steuerung3d/legacy_program/3DSteuerung0-212Mult-JWA.py`: invalid syntax (3DSteuerung0-212Mult-JWA.py, line 691)
