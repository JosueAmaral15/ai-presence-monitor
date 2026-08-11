from __future__ import annotations

import subprocess
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

from ai_presence_monitor import windows_process
from ai_presence_monitor.alarm_process import ProcessSnapshot
from ai_presence_monitor.windows_process import (
    CtypesWindowsProcessApi,
    WindowsAlarmProcessBackend,
)


class FakeProcessApi:
    def split_command(self, command: str) -> list[str]:
        return ["player.exe", "alarm file.mp3"]

    def snapshot(self, pid: int) -> ProcessSnapshot | None:
        return ProcessSnapshot("created", "fingerprint") if pid == 10 else None


class WindowsAlarmProcessBackendTests(unittest.TestCase):
    def test_blank_command_is_rejected_without_calling_native_parser(self) -> None:
        api = MagicMock(spec=FakeProcessApi)
        backend = WindowsAlarmProcessBackend(api=api)

        self.assertEqual(backend.parse_command("   \t"), [])
        api.split_command.assert_not_called()

    def test_parse_snapshot_and_spawn_use_dedicated_runner(self) -> None:
        backend = WindowsAlarmProcessBackend(api=FakeProcessApi())
        process = Mock(pid=10)

        with patch(
            "ai_presence_monitor.windows_process.subprocess.Popen",
            return_value=process,
        ) as popen:
            result = backend.spawn(
                backend.parse_command('player.exe "alarm file.mp3"'),
                max_duration_seconds=15,
            )

        self.assertIs(result, process)
        command = popen.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, "-m", "ai_presence_monitor.alarm_runner"])
        self.assertEqual(command[-2:], ["player.exe", "alarm file.mp3"])
        self.assertEqual(backend.snapshot(10), ProcessSnapshot("created", "fingerprint"))

    def test_terminate_uses_taskkill_tree_with_force_when_requested(self) -> None:
        backend = WindowsAlarmProcessBackend(api=FakeProcessApi())
        completed = subprocess.CompletedProcess([], 0)

        with patch(
            "ai_presence_monitor.windows_process.subprocess.run",
            return_value=completed,
        ) as run:
            backend.terminate(10, force=True)

        self.assertEqual(
            run.call_args.args[0],
            ["taskkill.exe", "/PID", "10", "/T", "/F"],
        )

    def test_native_api_rejects_non_windows_runtime(self) -> None:
        if sys.platform != "win32":
            with self.assertRaisesRegex(RuntimeError, "requer Windows"):
                CtypesWindowsProcessApi()

    def test_native_api_reads_command_line_and_process_identity(self) -> None:
        kernel = MagicMock()
        shell = MagicMock()
        command_values = (windows_process.wintypes.LPWSTR * 2)("player.exe", "sound.mp3")

        def split_command(command, count):
            count._obj.value = 2
            return command_values

        shell.CommandLineToArgvW.side_effect = split_command
        kernel.OpenProcess.return_value = 123

        def process_times(handle, creation, exit_time, kernel_time, user_time):
            creation._obj.dwHighDateTime = 1
            creation._obj.dwLowDateTime = 2
            return True

        def process_image(handle, flags, image, size):
            image.value = "C:\\Python\\python.exe"
            return True

        kernel.GetProcessTimes.side_effect = process_times
        kernel.QueryFullProcessImageNameW.side_effect = process_image

        def load_library(name: str, **_: object):
            return kernel if name == "kernel32" else shell

        with patch.object(windows_process.sys, "platform", "win32"), patch.object(
            windows_process.ctypes,
            "WinDLL",
            side_effect=load_library,
            create=True,
        ):
            api = CtypesWindowsProcessApi()
            self.assertEqual(api.split_command("player.exe sound.mp3"), ["player.exe", "sound.mp3"])
            snapshot = api.snapshot(10)

        assert snapshot is not None
        self.assertEqual(snapshot.start_token, str((1 << 32) | 2))
        self.assertEqual(len(snapshot.command_fingerprint), 64)
        kernel.CloseHandle.assert_called_once_with(123)


if __name__ == "__main__":
    unittest.main()
