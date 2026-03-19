from __future__ import annotations

from steuerung3d.apps.inputd_sim.config import PreparedInputdSimScenario, PreparedInputdSimStep
from steuerung3d.apps.inputd_sim.control import InputdSimControl
from steuerung3d.apps.inputd_sim.runtime import InputdSimRunner, _apply_control


def _prepared() -> PreparedInputdSimScenario:
    return PreparedInputdSimScenario(
        initial_axes=(0.0, 0.0),
        initial_buttons=(0, 0, 0, 0, 0, 0),
        steps=(
            PreparedInputdSimStep(
                name="drive",
                hold_s=1.0,
                ramp_s=0.2,
                start_axes=(0.0, 0.0),
                target_axes=(0.0, 0.3),
                target_buttons=(0, 0, 0, 0, 0, 1),
            ),
            PreparedInputdSimStep(
                name="release",
                hold_s=0.5,
                ramp_s=0.1,
                start_axes=(0.0, 0.3),
                target_axes=(0.0, 0.0),
                target_buttons=(0, 0, 0, 0, 0, 0),
            ),
        ),
    )


def test_inputd_sim_runner_holds_idle_until_started() -> None:
    runner = InputdSimRunner(prepared=_prepared())

    sample = runner.sample(now=0.0)

    assert sample.active is False
    assert sample.step_name == "idle"
    assert sample.axes == (0.0, 0.0)
    assert sample.buttons[-1] == 0


def test_inputd_sim_runner_progresses_and_holds_final_state() -> None:
    runner = InputdSimRunner(prepared=_prepared())
    runner.start(now=0.0, restart=True)

    drive_sample = runner.sample(now=0.1)
    release_sample = runner.sample(now=1.05)
    done_sample = runner.sample(now=1.60)
    held_sample = runner.sample(now=2.20)

    assert drive_sample.active is True
    assert drive_sample.step_name == "drive"
    assert drive_sample.axes[1] > 0.0
    assert release_sample.step_name == "release"
    assert release_sample.buttons[-1] == 0
    assert done_sample.active is False
    assert done_sample.step_name == "release:done"
    assert held_sample.active is False
    assert held_sample.axes == (0.0, 0.0)
    assert held_sample.buttons[-1] == 0


def test_apply_control_start_is_idempotent_and_restart_resets() -> None:
    runner = InputdSimRunner(prepared=_prepared())

    assert (
        _apply_control(runner=runner, command=InputdSimControl(action="start"), now=1.0) == "start"
    )
    assert (
        _apply_control(runner=runner, command=InputdSimControl(action="start"), now=1.5)
        == "start_ignored"
    )
    assert (
        _apply_control(runner=runner, command=InputdSimControl(action="restart"), now=2.0)
        == "restart"
    )
    assert runner.start_t == 2.0
    assert _apply_control(runner=runner, command=InputdSimControl(action="idle"), now=3.0) == "idle"
    assert runner.active is False
