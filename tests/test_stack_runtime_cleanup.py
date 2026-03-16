from __future__ import annotations

from pathlib import Path

from steuerung3d.core.stack_runtime_boot import start_runtime
from steuerung3d.core.stack_runtime_supervisor import stop_runtime
from steuerung3d.core.stack_spec import ProcessSpec, ServiceSpec, StackSpec


class _FakeProc:
    def __init__(self, alive: bool = True) -> None:
        self._alive = alive
        self.terminated = 0
        self.killed = 0
        self.wait_calls = 0

    def poll(self):
        return None if self._alive else 0

    def terminate(self) -> None:
        self.terminated += 1

    def kill(self) -> None:
        self.killed += 1
        self._alive = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self._alive:
            raise TimeoutError()
        return 0


class _FakeSock:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeStatus:
    def __init__(self) -> None:
        self.sock = _FakeSock()


class _FakeRT:
    def __init__(self) -> None:
        self.run_base = Path(".run")
        self.spec = StackSpec(
            name="test_stack",
            base_dir=Path("."),
            axes=["Anton"],
            rig={},
            net={},
            services={"core": ServiceSpec(enabled=True, module="x")},
        )
        self.keep_last_sessions = 1
        self.session_dir = None
        self.processes = []
        self.tailers = {}
        self.status = None

    @staticmethod
    def expand_processes_static(spec: StackSpec, *, session_dir: Path) -> list[ProcessSpec]:
        raise AssertionError("patched per test")

    def _spawn(self, p: ProcessSpec) -> None:
        return None


class _RP:
    def __init__(self, spec: ProcessSpec, popen: _FakeProc) -> None:
        self.spec = spec
        self.popen = popen


def test_start_runtime_cleans_residual_bind_ports(monkeypatch, tmp_path: Path) -> None:
    proc = ProcessSpec(
        name="core",
        argv=["python", "-m", "core", "--intent-in", "127.0.0.1:51001"],
        log_path=tmp_path / "core.log",
    )
    rt = _FakeRT()
    cleaned: list[list[int]] = []

    monkeypatch.setattr(
        "steuerung3d.core.stack_runtime_boot.make_session_dir", lambda base, keep_last: tmp_path
    )
    monkeypatch.setattr(
        "steuerung3d.core.stack_runtime_boot.write_runtime_meta", lambda rt, stopped_at_s=None: None
    )
    monkeypatch.setattr(
        _FakeRT, "expand_processes_static", staticmethod(lambda spec, session_dir: [proc])
    )
    monkeypatch.setattr(
        "steuerung3d.core.stack_runtime_boot.cleanup_residual_bind_ports",
        lambda ports: cleaned.append(list(ports)) or [],
    )

    start_runtime(rt)

    assert cleaned == [[51001]]


def test_stop_runtime_force_kills_and_closes_status(monkeypatch) -> None:
    proc_spec = ProcessSpec(
        name="core",
        argv=["python", "-m", "core", "--intent-in", "127.0.0.1:51001"],
        log_path=Path("core.log"),
    )
    fake_proc = _FakeProc(alive=True)
    rt = _FakeRT()
    rt.processes = [_RP(proc_spec, fake_proc)]
    rt.status = _FakeStatus()

    cleaned: list[list[int]] = []
    monkeypatch.setattr(
        "steuerung3d.core.stack_runtime_supervisor.cleanup_residual_bind_ports",
        lambda ports: cleaned.append(list(ports)) or [],
    )
    monkeypatch.setattr(
        "steuerung3d.core.stack_runtime_supervisor.write_runtime_meta",
        lambda rt, stopped_at_s=None: None,
    )

    stop_runtime(rt)

    assert fake_proc.terminated == 1
    assert fake_proc.killed == 1
    assert rt.status.sock.closed is True
    assert cleaned == [[51001]]
