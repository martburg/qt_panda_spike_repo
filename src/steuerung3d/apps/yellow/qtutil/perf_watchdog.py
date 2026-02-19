from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import logging
import time


@dataclass
class PerfWatchdog:
    """Lightweight UI tick watchdog.

    Purpose:
      - Detect UI loop stalls (e.g. due to expensive widget updates or logging).
      - Emit *rate-limited* warnings without changing any tick/livetick semantics.

    Notes:
      - Uses time.perf_counter() (monotonic, high-resolution).
      - Does not touch TelemetrySnapshot.tick, device_tick, or livetick delta logic.
    """

    logger: logging.Logger
    name: str

    warn_threshold_s: float = 0.060  # warn when a tick takes longer than this
    debug_threshold_s: float = 0.030  # debug when tick takes longer than this (only if logger is DEBUG)
    min_log_interval_s: float = 2.0  # rate-limit logs

    _t0: float | None = None
    _last: float | None = None
    _segments: list[tuple[str, float]] = field(default_factory=list)
    _last_log_t: float = 0.0

    @contextmanager
    def tick(self):
        self.begin()
        try:
            yield
        finally:
            self.end()

    def begin(self) -> None:
        t = time.perf_counter()
        self._t0 = t
        self._last = t
        self._segments.clear()

    def mark(self, label: str) -> None:
        """Mark the end of a logical segment within the tick."""
        if self._t0 is None or self._last is None:
            return
        t = time.perf_counter()
        dt = t - self._last
        self._last = t
        # Keep small list; labels are static strings.
        self._segments.append((label, dt))

    def end(self) -> None:
        if self._t0 is None:
            return
        t_end = time.perf_counter()
        total = t_end - self._t0

        # Fast path: not slow enough -> do nothing.
        if total < self.debug_threshold_s and total < self.warn_threshold_s:
            return

        # Rate limit (based on end timestamp).
        if (t_end - self._last_log_t) < self.min_log_interval_s:
            return
        self._last_log_t = t_end

        # Final implicit segment: from last mark to end.
        if self._last is not None:
            self._segments.append(("tail", t_end - self._last))

        # Only compute worst segment if we are going to log.
        worst_label = "tick"
        worst_dt = 0.0
        for lbl, dt in self._segments:
            if dt > worst_dt:
                worst_label, worst_dt = lbl, dt

        total_ms = total * 1000.0
        worst_ms = worst_dt * 1000.0

        if total >= self.warn_threshold_s:
            self.logger.warning(
                "ui tick slow: %s total=%.1fms worst=%s %.1fms",
                self.name,
                total_ms,
                worst_label,
                worst_ms,
            )
        else:
            # Only emit debug if debug is enabled to avoid noise.
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(
                    "ui tick: %s total=%.1fms worst=%s %.1fms",
                    self.name,
                    total_ms,
                    worst_label,
                    worst_ms,
                )
