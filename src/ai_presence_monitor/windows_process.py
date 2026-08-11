from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes
from typing import Any, Protocol

from .alarm_process import (
    AlarmProcessError,
    ProcessSnapshot,
    command_fingerprint,
)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class WindowsProcessApi(Protocol):
    def split_command(self, command: str) -> list[str]: ...

    def snapshot(self, pid: int) -> ProcessSnapshot | None: ...


class CtypesWindowsProcessApi:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise AlarmProcessError("A API de processos Win32 requer Windows.")
        win_dll = getattr(ctypes, "WinDLL")
        self._kernel32: Any = win_dll("kernel32", use_last_error=True)
        self._shell32: Any = win_dll("shell32", use_last_error=True)
        self._configure_signatures()

    def split_command(self, command: str) -> list[str]:
        count = ctypes.c_int()
        pointer = self._shell32.CommandLineToArgvW(command, ctypes.byref(count))
        if not pointer:
            raise AlarmProcessError(
                f"Falha ao interpretar RED_ALERT_COMMAND: erro Win32 {_last_error()}."
            )
        try:
            return [pointer[index] for index in range(count.value)]
        finally:
            self._kernel32.LocalFree(pointer)

    def snapshot(self, pid: int) -> ProcessSnapshot | None:
        handle = self._kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid,
        )
        if not handle:
            return None
        try:
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not self._kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return None
            size = wintypes.DWORD(32768)
            image = ctypes.create_unicode_buffer(size.value)
            if not self._kernel32.QueryFullProcessImageNameW(
                handle,
                0,
                image,
                ctypes.byref(size),
            ):
                return None
            start_token = str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
            fingerprint = command_fingerprint([image.value.casefold()])
            return ProcessSnapshot(start_token, fingerprint)
        finally:
            self._kernel32.CloseHandle(handle)

    def _configure_signatures(self) -> None:
        self._shell32.CommandLineToArgvW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        self._kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
        self._kernel32.LocalFree.restype = wintypes.HLOCAL
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        self._kernel32.GetProcessTimes.restype = wintypes.BOOL
        self._kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL


class WindowsAlarmProcessBackend:
    def __init__(self, api: WindowsProcessApi | None = None) -> None:
        self._api = api or CtypesWindowsProcessApi()

    def parse_command(self, command: str) -> list[str]:
        stripped = command.strip()
        return self._api.split_command(stripped) if stripped else []

    def spawn(
        self,
        argv: list[str],
        *,
        max_duration_seconds: float,
    ) -> subprocess.Popen[bytes]:
        runner_argv = [
            sys.executable,
            "-m",
            "ai_presence_monitor.alarm_runner",
            "--duration",
            f"{max_duration_seconds:g}",
            "--",
            *argv,
        ]
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            return subprocess.Popen(
                runner_argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError as exc:
            raise AlarmProcessError(f"Falha ao iniciar alarme: {exc}") from exc

    def snapshot(self, pid: int) -> ProcessSnapshot | None:
        return self._api.snapshot(pid)

    def terminate(self, pid: int, *, force: bool) -> None:
        command = ["taskkill.exe", "/PID", str(pid), "/T"]
        command.append("/F")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=creationflags,
            )
        except OSError as exc:
            raise AlarmProcessError(
                f"Falha ao interromper arvore do alarme PID {pid}: {exc}"
            ) from exc
        if result.returncode != 0 and self.snapshot(pid) is not None:
            raise AlarmProcessError(
                "taskkill.exe nao interrompeu a arvore do alarme "
                f"PID {pid} (codigo {result.returncode})."
            )


def _last_error() -> int:
    getter = getattr(ctypes, "get_last_error", None)
    return int(getter()) if getter else 0
