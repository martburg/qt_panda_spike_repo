Fixes the last 2 failing tests in a robust way (works even if you accidentally unzip from src/steuerung3d).

1) test_claims_autoclaim.py:
   - ArmLiveMode() before EnableAxis/JogAxis assertions (these intents are LIVE-gated).

2) test_plc_twincat_legacy_fleet_from_toml.py:
   - If repo-root configs/dev_plc.toml is missing, generate a temporary config in tmp_path.

Also ships configs/dev_plc.toml (and a copy in src/steuerung3d/configs/) for convenience.
