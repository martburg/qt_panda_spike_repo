"""Rig workflow tests are deferred for this milestone.

The current repo scope stops short of the older rig-intent API that this test
module targeted. We keep the module as an explicit deferred placeholder, but we
skip it at import time so static checkers do not need stale intent symbols.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "Rig workflow not available in this milestone (deferred). "
    "Re-enable once rig intents + rig_logic workflow API are implemented.",
    allow_module_level=True,
)
