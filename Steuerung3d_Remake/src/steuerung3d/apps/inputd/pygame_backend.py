from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def deadzone_expo(x: float, deadzone: float, expo: float) -> float:
    """Apply deadzone and optional expo (cubic blend).

    - deadzone in [0..1]
    - expo in [0..1]
    """
    if deadzone <= 0.0 and expo <= 0.0:
        return x
    if abs(x) <= deadzone:
        return 0.0
    s = 1.0 if x >= 0.0 else -1.0
    u = (abs(x) - deadzone) / max(1e-9, (1.0 - deadzone))
    # expo blend: linear -> cubic
    u2 = (1.0 - expo) * u + expo * (u * u * u)
    return s * u2


@dataclass
class DeviceInfo:
    index: int
    name: str


class PygameJoystick:
    """Small wrapper around pygame.joystick.Joystick with reconnection support."""

    def __init__(self) -> None:
        self._pg = None
        self._joy = None
        self._last_open_attempt_s = 0.0

    def init(self) -> None:
        import pygame  # lazy

        self._pg = pygame
        # Be conservative: init only what we need
        if not pygame.get_init():
            pygame.init()
        pygame.joystick.init()

    def list_devices(self) -> List[DeviceInfo]:
        if self._pg is None:
            self.init()
        pg = self._pg
        assert pg is not None

        out: List[DeviceInfo] = []
        n = pg.joystick.get_count()
        for i in range(n):
            try:
                joy = pg.joystick.Joystick(i)
                joy.init()
                out.append(DeviceInfo(i, joy.get_name()))
            except Exception:
                continue
        return out

    def open(self, *, index: Optional[int] = None, name_contains: Optional[str] = None) -> Tuple[bool, str]:
        """Try to open a joystick. Returns (ok, description)."""
        if self._pg is None:
            self.init()
        pg = self._pg
        assert pg is not None

        n = pg.joystick.get_count()
        if n <= 0:
            self._joy = None
            return False, "no joystick devices found"

        chosen: Optional[int] = None
        if index is not None:
            if 0 <= index < n:
                chosen = index
            else:
                return False, f"requested index {index} out of range (0..{n-1})"
        elif name_contains:
            want = name_contains.lower()
            for i in range(n):
                try:
                    joy = pg.joystick.Joystick(i)
                    joy.init()
                    if want in (joy.get_name() or "").lower():
                        chosen = i
                        break
                except Exception:
                    continue
            if chosen is None:
                return False, f"no joystick name contains '{name_contains}'"
        else:
            chosen = 0

        try:
            joy = pg.joystick.Joystick(chosen)
            joy.init()
            self._joy = joy
            return True, f"{chosen}: {joy.get_name()}"
        except Exception as e:
            self._joy = None
            return False, f"failed to open joystick {chosen}: {e}"

    def ensure_open(self, *, index: Optional[int], name_contains: Optional[str], retry_every_s: float = 1.0) -> Tuple[bool, str]:
        """Ensure we have an open joystick; if not, retry periodically."""
        if self._joy is not None:
            return True, "ok"

        now = time.monotonic()
        if now - self._last_open_attempt_s < retry_every_s:
            return False, "waiting to retry"

        self._last_open_attempt_s = now
        return self.open(index=index, name_contains=name_contains)

    def read(self, *, max_axes: Optional[int] = None, max_buttons: Optional[int] = None, hat_as_buttons: bool = True) -> Tuple[bool, List[float], List[int]]:
        """Read a sample. Returns (connected, axes, buttons)."""
        if self._pg is None:
            self.init()
        pg = self._pg
        assert pg is not None

        if self._joy is None:
            return False, [], []

        try:
            pg.event.pump()

            na = self._joy.get_numaxes()
            nb = self._joy.get_numbuttons()
            nh = self._joy.get_numhats()

            if max_axes is not None:
                na = min(na, int(max_axes))
            if max_buttons is not None:
                nb = min(nb, int(max_buttons))

            axes = [float(self._joy.get_axis(i)) for i in range(na)]
            buttons = [1 if self._joy.get_button(i) else 0 for i in range(nb)]

            if hat_as_buttons and nh > 0:
                for h in range(nh):
                    x, y = self._joy.get_hat(h)
                    # order: up, down, left, right
                    buttons.extend([
                        1 if y > 0 else 0,
                        1 if y < 0 else 0,
                        1 if x < 0 else 0,
                        1 if x > 0 else 0,
                    ])

            return True, axes, buttons
        except Exception:
            # treat as disconnect
            self._joy = None
            return False, [], []
