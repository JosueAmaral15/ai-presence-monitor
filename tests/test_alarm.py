from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.alarm import (
    AlarmControlError,
    AlarmController,
    default_alarm_state_path,
)
from ai_presence_monitor.alarm_process import (
    AlarmProcessError,
    LinuxAlarmProcessBackend,
)


class AlarmControllerTests(unittest.TestCase):
    def _sleep_command(self) -> str:
        argv = [sys.executable, "-c", "import time; time.sleep(30)"]
        return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)

    def test_start_deduplicates_and_stop_terminates_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "alarm.json"
            controller = AlarmController(state_path)

            started = controller.start(self._sleep_command())
            self.assertEqual(started.status, "started")
            self.assertTrue(state_path.exists())
            if os.name != "nt":
                self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)

            duplicate = controller.start(self._sleep_command())
            self.assertEqual(duplicate.status, "already_running")
            self.assertEqual(duplicate.pid, started.pid)

            stopped = controller.stop()
            self.assertEqual(stopped.status, "stopped")
            self.assertFalse(stopped.forced)
            for _ in range(50):
                if not state_path.exists():
                    break
                time.sleep(0.01)
            self.assertFalse(state_path.exists())

    def test_dry_run_and_no_force_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controller = AlarmController(Path(tmp) / "alarm.json")
            started = controller.start(self._sleep_command())
            try:
                preview = controller.stop(dry_run=True)
                self.assertEqual(preview.status, "would_stop")
                self.assertEqual(preview.pid, started.pid)

                with patch.object(controller, "_wait_until_stopped", return_value=False):
                    with self.assertRaisesRegex(AlarmControlError, "nao encerrou"):
                        controller.stop(timeout_seconds=0, force=False)
            finally:
                controller.stop(timeout_seconds=0, force=True)

    def test_continuous_command_stops_at_maximum_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "alarm.json"
            controller = AlarmController(
                state_path,
                max_duration_seconds=0.2,
            )

            started = controller.start(self._sleep_command())
            deadline = time.monotonic() + 3
            while state_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)

            self.assertFalse(state_path.exists())
            self.assertIsNone(controller.backend.snapshot(started.pid))

    def test_stale_and_missing_state_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "alarm.json"
            controller = AlarmController(state_path)
            self.assertEqual(controller.stop().status, "not_running")

            state_path.write_text(
                json.dumps(
                    {
                        "pid": 999_999_999,
                        "command_fingerprint": "missing",
                        "process_start_token": "missing",
                        "started_at": 1,
                    }
                ),
                encoding="utf-8",
            )
            result = controller.stop()
            self.assertEqual(result.status, "stale_state")
            self.assertFalse(state_path.exists())

    def test_invalid_state_and_timeout_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "alarm.json"
            state_path.write_text("{invalid", encoding="utf-8")
            controller = AlarmController(state_path)
            with self.assertRaisesRegex(AlarmControlError, "Estado de alarme invalido"):
                controller.stop()
            with self.assertRaisesRegex(AlarmControlError, "nao pode ser negativo"):
                AlarmController(Path(tmp) / "other.json").stop(timeout_seconds=-1)

    def test_backend_failure_refuses_start_before_state_is_written(self) -> None:
        class FailingBackend:
            def parse_command(self, command: str) -> list[str]:
                return [command]

            def spawn(self, argv: list[str], *, max_duration_seconds: float):
                raise AlarmProcessError("plataforma indisponivel")

            def snapshot(self, pid: int):
                return None

            def terminate(self, pid: int, *, force: bool) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "alarm.json"
            controller = AlarmController(state_path, backend=FailingBackend())  # type: ignore[arg-type]

            with self.assertRaisesRegex(AlarmControlError, "plataforma indisponivel"):
                controller.start(self._sleep_command())

            self.assertFalse(state_path.exists())

    def test_invalid_duration_or_missing_timeout_refuses_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "ai_presence_monitor.alarm.subprocess.Popen"
        ) as popen:
            controller = AlarmController(
                Path(tmp) / "alarm.json",
                max_duration_seconds=0,
            )
            with self.assertRaisesRegex(AlarmControlError, "maior que zero"):
                controller.start(self._sleep_command())

            controller = AlarmController(
                Path(tmp) / "other.json",
                backend=LinuxAlarmProcessBackend(),
            )
            with patch("ai_presence_monitor.alarm_process.shutil.which", return_value=None):
                with self.assertRaisesRegex(AlarmControlError, "nao foi encontrado"):
                    controller.start(self._sleep_command())

            popen.assert_not_called()

    def test_default_state_path_respects_xdg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            if os.name == "nt":
                with patch.dict("os.environ", {"LOCALAPPDATA": tmp}):
                    expected = Path(tmp) / "ai-presence-monitor" / "state" / "red-alarm.json"
                    self.assertEqual(default_alarm_state_path(), expected)
            else:
                with patch.dict("os.environ", {"XDG_STATE_HOME": tmp}):
                    expected = Path(tmp) / "ai-presence-monitor" / "red-alarm.json"
                    self.assertEqual(default_alarm_state_path(), expected)


if __name__ == "__main__":
    unittest.main()
