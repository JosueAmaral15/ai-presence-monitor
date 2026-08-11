from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .alarm_process import AlarmProcessBackend, AlarmProcessError, ProcessSnapshot
from .config import APP_DIR_NAME

DEFAULT_ALARM_MAX_DURATION_SECONDS = 15.0


class AlarmControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class AlarmState:
    pid: int
    command_fingerprint: str
    process_start_token: str
    started_at: float


@dataclass(frozen=True)
class AlarmStartResult:
    status: str
    pid: int
    state_path: Path


@dataclass(frozen=True)
class AlarmStopResult:
    status: str
    pid: int | None
    forced: bool
    state_path: Path


def default_alarm_state_path() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / APP_DIR_NAME / "state" / "red-alarm.json"
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state_home).expanduser() if xdg_state_home else Path.home() / ".local" / "state"
    return base / APP_DIR_NAME / "red-alarm.json"


class AlarmController:
    def __init__(
        self,
        state_path: Path | None = None,
        max_duration_seconds: float = DEFAULT_ALARM_MAX_DURATION_SECONDS,
        backend: AlarmProcessBackend | None = None,
    ):
        self.state_path = (state_path or default_alarm_state_path()).expanduser()
        self.max_duration_seconds = max_duration_seconds
        if backend is None:
            from .platform_integration import get_platform_factory

            backend = get_platform_factory().create_alarm_process_backend()
        self.backend = backend

    def start(self, command: str) -> AlarmStartResult:
        try:
            argv = self.backend.parse_command(command)
        except AlarmProcessError as exc:
            raise AlarmControlError(str(exc)) from exc
        if not argv:
            raise AlarmControlError("RED_ALERT_COMMAND nao pode estar vazio.")
        duration = self.max_duration_seconds
        if not math.isfinite(duration) or duration <= 0:
            raise AlarmControlError(
                "RED_ALERT_MAX_DURATION_SECONDS precisa ser maior que zero."
            )

        current = self._load_state()
        if current is not None and self._matches(current):
            return AlarmStartResult(
                status="already_running",
                pid=current.pid,
                state_path=self.state_path,
            )
        if current is not None:
            self._remove_state(current)

        try:
            process = self.backend.spawn(
                argv,
                max_duration_seconds=duration,
            )
        except AlarmProcessError as exc:
            raise AlarmControlError(str(exc)) from exc

        snapshot = self._wait_for_snapshot(process.pid)
        if snapshot is None:
            return_code = process.poll()
            if return_code is None:
                self._terminate(process.pid, force=False)
                try:
                    return_code = process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    self._terminate(process.pid, force=True)
                    return_code = process.wait(timeout=1.0)
            raise AlarmControlError(
                "O comando de alarme terminou antes de poder ser monitorado"
                + (f" (codigo {return_code})." if return_code is not None else ".")
            )

        state = AlarmState(
            pid=process.pid,
            command_fingerprint=snapshot.command_fingerprint,
            process_start_token=snapshot.start_token,
            started_at=time.time(),
        )
        self._write_state(state)
        threading.Thread(
            target=self._reap,
            args=(process, state),
            name=f"ai-presence-alarm-{process.pid}",
            daemon=True,
        ).start()
        return AlarmStartResult(
            status="started",
            pid=process.pid,
            state_path=self.state_path,
        )

    def stop(
        self,
        *,
        timeout_seconds: float = 3.0,
        force: bool = True,
        dry_run: bool = False,
    ) -> AlarmStopResult:
        if timeout_seconds < 0:
            raise AlarmControlError("O timeout de parada nao pode ser negativo.")

        state = self._load_state()
        if state is None:
            return AlarmStopResult(
                status="not_running",
                pid=None,
                forced=False,
                state_path=self.state_path,
            )
        if not self._matches(state):
            self._remove_state(state)
            return AlarmStopResult(
                status="stale_state",
                pid=state.pid,
                forced=False,
                state_path=self.state_path,
            )
        if dry_run:
            return AlarmStopResult(
                status="would_stop",
                pid=state.pid,
                forced=False,
                state_path=self.state_path,
            )

        self._terminate(state.pid, force=False)
        if self._wait_until_stopped(state, timeout_seconds):
            self._remove_state(state)
            return AlarmStopResult(
                status="stopped",
                pid=state.pid,
                forced=False,
                state_path=self.state_path,
            )

        if not force:
            raise AlarmControlError(
                f"O alarme PID {state.pid} nao encerrou em {timeout_seconds:g}s."
            )

        self._terminate(state.pid, force=True)
        if not self._wait_until_stopped(state, 1.0):
            raise AlarmControlError(f"Nao foi possivel interromper o alarme PID {state.pid}.")
        self._remove_state(state)
        return AlarmStopResult(
            status="stopped",
            pid=state.pid,
            forced=True,
            state_path=self.state_path,
        )

    def _load_state(self) -> AlarmState | None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return AlarmState(
                pid=int(payload["pid"]),
                command_fingerprint=str(payload["command_fingerprint"]),
                process_start_token=str(payload["process_start_token"]),
                started_at=float(payload["started_at"]),
            )
        except FileNotFoundError:
            return None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AlarmControlError(
                f"Estado de alarme invalido em {self.state_path}: {exc}"
            ) from exc

    def _write_state(self, state: AlarmState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.chmod(0o700)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "pid": state.pid,
                    "command_fingerprint": state.command_fingerprint,
                    "process_start_token": state.process_start_token,
                    "started_at": state.started_at,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self.state_path)

    def _remove_state(self, expected: AlarmState) -> None:
        try:
            current = self._load_state()
        except AlarmControlError:
            current = None
        if current is not None and current != expected:
            return
        self.state_path.unlink(missing_ok=True)

    def _matches(self, state: AlarmState) -> bool:
        snapshot = self.backend.snapshot(state.pid)
        if snapshot is None:
            return False
        return (
            snapshot.start_token == state.process_start_token
            and snapshot.command_fingerprint == state.command_fingerprint
        )

    def _wait_for_snapshot(self, pid: int) -> ProcessSnapshot | None:
        for _ in range(20):
            snapshot = self.backend.snapshot(pid)
            if snapshot is not None:
                return snapshot
            time.sleep(0.01)
        return None

    def _wait_until_stopped(self, state: AlarmState, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while self._matches(state):
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
        return True

    def _terminate(self, pid: int, *, force: bool) -> None:
        try:
            self.backend.terminate(pid, force=force)
        except AlarmProcessError as exc:
            raise AlarmControlError(str(exc)) from exc

    def _reap(self, process: subprocess.Popen[bytes], state: AlarmState) -> None:
        process.wait()
        self._remove_state(state)
