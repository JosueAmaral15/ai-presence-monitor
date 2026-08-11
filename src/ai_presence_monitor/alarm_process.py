from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import signal
import subprocess
from dataclasses import dataclass
from typing import Protocol


class AlarmProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessSnapshot:
    start_token: str
    command_fingerprint: str


class AlarmProcessBackend(Protocol):
    def parse_command(self, command: str) -> list[str]: ...

    def spawn(
        self,
        argv: list[str],
        *,
        max_duration_seconds: float,
    ) -> subprocess.Popen[bytes]: ...

    def snapshot(self, pid: int) -> ProcessSnapshot | None: ...

    def terminate(self, pid: int, *, force: bool) -> None: ...


def command_fingerprint(argv: list[str] | tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for item in argv:
        digest.update(item.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
    return digest.hexdigest()


class LinuxAlarmProcessBackend:
    def parse_command(self, command: str) -> list[str]:
        return shlex.split(command)

    def spawn(
        self,
        argv: list[str],
        *,
        max_duration_seconds: float,
    ) -> subprocess.Popen[bytes]:
        timeout_command = shutil.which("timeout")
        if timeout_command is None:
            raise AlarmProcessError(
                "GNU timeout nao foi encontrado; o alarme nao sera iniciado sem limite."
            )
        controlled_argv = [
            timeout_command,
            "--signal=TERM",
            "--kill-after=1s",
            f"{max_duration_seconds:g}s",
            *argv,
        ]
        try:
            return subprocess.Popen(
                controlled_argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise AlarmProcessError(f"Falha ao iniciar alarme: {exc}") from exc

    def snapshot(self, pid: int) -> ProcessSnapshot | None:
        stat_path = os.path.join("/proc", str(pid), "stat")
        cmdline_path = os.path.join("/proc", str(pid), "cmdline")
        try:
            with open(stat_path, encoding="utf-8") as stat_file:
                stat_text = stat_file.read()
            _, fields_text = stat_text.rsplit(")", 1)
            fields = fields_text.split()
            process_state = fields[0]
            start_token = fields[19]
            with open(cmdline_path, "rb") as cmdline_file:
                cmdline = cmdline_file.read()
        except (FileNotFoundError, IndexError, OSError, ValueError):
            return None
        if process_state == "Z" or not cmdline:
            return None
        argv = [
            item.decode("utf-8", errors="surrogateescape")
            for item in cmdline.split(b"\0")
            if item
        ]
        return ProcessSnapshot(start_token, command_fingerprint(argv))

    def terminate(self, pid: int, *, force: bool) -> None:
        signum = signal.SIGKILL if force else signal.SIGTERM
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, signum)
            else:
                os.kill(pid, signum)
        except ProcessLookupError:
            return
        except OSError as exc:
            raise AlarmProcessError(
                f"Falha ao sinalizar alarme PID {pid}: {exc}"
            ) from exc
