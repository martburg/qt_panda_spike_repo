from __future__ import annotations

from .profile_loader import load_profile
from .runtime import run_app


def run_supervisor(ns) -> int:
    profile = load_profile(ns.profile)
    return run_app(profile)
