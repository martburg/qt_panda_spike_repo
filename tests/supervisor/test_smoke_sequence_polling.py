from __future__ import annotations

import pytest

from steuerung3d.apps.supervisor import smoke_sequence_polling as polling


def test_publish_cadence_publishes_immediately_then_waits_for_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    sleeps: list[float] = []
    published: list[str] = []

    def _monotonic() -> float:
        return now[0]

    def _sleep(delay: float) -> None:
        sleeps.append(float(delay))

    monkeypatch.setattr(polling.time, "monotonic", _monotonic)
    monkeypatch.setattr(polling.time, "sleep", _sleep)

    cadence = polling.PublishCadence(deadline=101.0, interval_s=0.25, settle_s=0.10)

    assert cadence.maybe_publish(lambda: published.append("tick"))
    assert published == ["tick"]
    assert sleeps == [0.10]

    assert not cadence.maybe_publish(lambda: published.append("too-soon"))
    assert published == ["tick"]

    now[0] = 100.30
    assert cadence.maybe_publish(lambda: published.append("tick2"))
    assert published == ["tick", "tick2"]


def test_poll_until_result_retries_until_observe_returns_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [200.0]
    checks: list[str] = []
    attempts = {"count": 0}

    def _monotonic() -> float:
        return now[0]

    monkeypatch.setattr(polling.time, "monotonic", _monotonic)

    def _sleep(delay: float) -> None:
        now[0] += float(delay)

    monkeypatch.setattr(polling.time, "sleep", _sleep)

    def _check_alive() -> None:
        checks.append("alive")

    def _observe() -> int | None:
        attempts["count"] += 1
        if attempts["count"] >= 3:
            return 7
        return None

    result = polling.poll_until_result(
        deadline=200.20,
        check_alive=_check_alive,
        observe=_observe,
        poll_s=0.05,
    )

    assert result == 7
    assert len(checks) == 3
    assert attempts["count"] == 3
