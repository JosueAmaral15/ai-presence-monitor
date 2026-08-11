from __future__ import annotations

import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.background_service import BackgroundServiceError
from ai_presence_monitor.windows_task import (
    TASK_NAMES,
    WindowsTaskSchedulerService,
    render_task_definition,
)


class WindowsTaskSchedulerServiceTests(unittest.TestCase):
    def test_render_uses_interactive_user_and_escapes_paths(self) -> None:
        rendered = render_task_definition(
            component="monitor",
            env_file=Path("C:/Config & Data/.env"),
            python_executable="C:/Python/python.exe",
            user_id="DOMAIN\\worker",
        )

        self.assertIn("InteractiveToken", rendered)
        self.assertIn("LeastPrivilege", rendered)
        self.assertEqual(rendered.count("<UserId>DOMAIN\\worker</UserId>"), 2)
        self.assertIn("Config &amp; Data", rendered)
        self.assertIn("ai_presence_monitor", rendered)
        self.assertIn(" monitor</Arguments>", rendered)
        self.assertNotIn("DISCORD_", rendered)
        root = ET.fromstring(rendered)
        self.assertTrue(root.tag.endswith("Task"))

    def test_dry_run_does_not_write_or_call_schtasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "monitor.xml"
            manager = WindowsTaskSchedulerService()
            with patch.object(manager, "_run") as run:
                result = manager.install(
                    component="monitor",
                    env_file=Path(tmp) / ".env",
                    target_path=target,
                    dry_run=True,
                )

            self.assertTrue(result.changed)
            self.assertFalse(target.exists())
            run.assert_not_called()

    def test_install_and_uninstall_manage_only_named_task_and_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "reply.xml"
            manager = WindowsTaskSchedulerService()
            with patch(
                "ai_presence_monitor.windows_task.shutil.which",
                return_value="C:/Windows/System32/schtasks.exe",
            ), patch.object(manager, "_task_exists", side_effect=[False, True]), patch.object(
                manager,
                "_run",
            ) as run:
                installed = manager.install(
                    component="reply-observer",
                    env_file=Path(tmp) / ".env",
                    target_path=target,
                    python_executable="C:/Python/python.exe",
                )
                removed = manager.uninstall(
                    component="reply-observer",
                    target_path=target,
                )

            self.assertTrue(installed.changed)
            self.assertFalse(target.exists())
            self.assertIsNotNone(removed.backup_path)
            create = run.call_args_list[0].args[0]
            delete = run.call_args_list[1].args[0]
            self.assertIn(TASK_NAMES["reply-observer"], create)
            self.assertEqual(delete[:2], ["schtasks.exe", "/Delete"])

    def test_missing_schtasks_fails_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "ai_presence_monitor.windows_task.shutil.which",
            return_value=None,
        ):
            target = Path(tmp) / "monitor.xml"
            with self.assertRaisesRegex(BackgroundServiceError, "nao foi encontrado"):
                WindowsTaskSchedulerService().install(
                    component="monitor",
                    env_file=Path(tmp) / ".env",
                    target_path=target,
                )
            self.assertFalse(target.exists())

    def test_task_query_and_command_failure_are_interpreted(self) -> None:
        with patch(
            "ai_presence_monitor.windows_task.shutil.which",
            return_value="schtasks.exe",
        ), patch(
            "ai_presence_monitor.windows_task.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ):
            self.assertTrue(WindowsTaskSchedulerService._task_exists("Task"))

        failed = subprocess.CompletedProcess([], 1, "", "access denied")
        with patch(
            "ai_presence_monitor.windows_task.subprocess.run",
            return_value=failed,
        ):
            with self.assertRaisesRegex(BackgroundServiceError, "access denied"):
                WindowsTaskSchedulerService._run(["schtasks.exe", "/Create"])


if __name__ == "__main__":
    unittest.main()
