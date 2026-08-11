from __future__ import annotations

import sys
import time
import unittest

from ai_presence_monitor.alarm_runner import main, run


class AlarmRunnerTests(unittest.TestCase):
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
