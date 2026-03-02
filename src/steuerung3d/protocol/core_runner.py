from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

from steuerung3d.core.engine import CoreEngine


@dataclass
class CoreRunner:
    """
    Runs the CoreEngine in a background thread.

    pacing:
      - If realtime=True, tries to sleep to match dt_s.
      - If realtime=False, runs as fast as possible.

    stop:
      - stop() sets an event; thread exits cleanly after current tick.
    """

    engine: CoreEngine
    realtime: bool = True

    _thread: Optional[threading.Thread] = None
    _stop_evt: threading.Event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run_loop, name="CoreRunner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run_loop(self) -> None:
        dt = self.engine.timebase.dt_s
        next_t = time.perf_counter()

        while not self._stop_evt.is_set():
            self.engine.step_once()

            if not self.realtime:
                continue

            next_t += dt
            now = time.perf_counter()
            sleep_s = next_t - now
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                # if we fall behind, don't sleep; reset schedule to "now"
                next_t = now
