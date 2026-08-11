from __future__ import annotations

import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

from ai_presence_monitor import alarm_runner
from ai_presence_monitor.alarm_runner import main, run


class AlarmRunnerTests(unittest.TestCase):
    def test_taskkill_failure_falls_back_to_direct_child_kill(self) -> None:
        process = Mock(pid=10)
        failed = subprocess.CompletedProcess([], 1)

        with patch(
            "ai_presence_monitor.alarm_runner.subprocess.run",
            return_value=failed,
        ):
            alarm_runner._terminate_tree(process)

        process.kill.assert_called_once_with()

    def test_runner_bounds_long_process(self) -> None:
        started = time.monotonic()
        result = run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            0.1,
        )

        self.assertNotEqual(result, 0)
        self.assertLess(time.monotonic() - started, 3)

    def test_invalid_duration_and_missing_command_are_rejected(self) -> None:
        self.assertEqual(run([sys.executable, "-c", "pass"], 0), 2)
        self.assertEqual(main(["--duration", "1", "--"]), 2)


if __name__ == "__main__":
    unittest.main()
