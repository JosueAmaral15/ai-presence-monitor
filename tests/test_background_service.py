from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from ai_presence_monitor.background_service import (
    BackgroundServiceError,
    LinuxBackgroundServiceManager,
    print_background_service_result,
)


class LinuxBackgroundServiceManagerTests(unittest.TestCase):
    def test_monitor_and_reply_components_wrap_systemd_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = LinuxBackgroundServiceManager()

            monitor = manager.install(
                component="monitor",
                env_file=root / ".env",
                target_path=root / "monitor.service",
                python_executable="/usr/bin/python3",
                dry_run=True,
            )
            reply = manager.install(
                component="reply-observer",
                env_file=root / ".env",
                target_path=root / "reply.service",
                python_executable="/usr/bin/python3",
                dry_run=True,
            )

            self.assertIn(" monitor", monitor.rendered_definition)
            self.assertIn("observe-replies", reply.rendered_definition)
            self.assertIn("ai-presence-monitor.service", monitor.follow_up_commands[-1])

    def test_install_uninstall_and_output_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "monitor.service"
            manager = LinuxBackgroundServiceManager()
            installed = manager.install(
                component="monitor",
                env_file=root / ".env",
                target_path=target,
            )
            removed = manager.uninstall(component="monitor", target_path=target)

            self.assertTrue(installed.changed)
            self.assertTrue(removed.changed)
            self.assertFalse(target.exists())
            with redirect_stdout(StringIO()) as output:
                print_background_service_result(installed, dry_run=False)
            self.assertIn("component=monitor", output.getvalue())
            self.assertIn("systemctl", output.getvalue())

    def test_invalid_component_is_rejected(self) -> None:
        with self.assertRaisesRegex(BackgroundServiceError, "invalido"):
            LinuxBackgroundServiceManager().uninstall(component="invalid")


if __name__ == "__main__":
    unittest.main()
