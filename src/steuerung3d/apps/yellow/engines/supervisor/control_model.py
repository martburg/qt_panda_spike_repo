from __future__ import annotations

from .models import PairControlInputs


def default_pair_control_inputs() -> PairControlInputs:
    """Return a neutral supervisor input set.

    For this first slice these inputs are typically driven by the supervisor GUI.
    Later slices may add additional producers, such as Frederik, without changing
    the control-input model.
    """

    return PairControlInputs()
