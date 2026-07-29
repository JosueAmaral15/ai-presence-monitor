from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.config import load_config, resolve_env_path
from ai_presence_monitor.identity import scoped_worker_id
from ai_presence_monitor.systemd_service import (
    install_reply_observer_service,
    install_user_service,
    render_user_service,
    uninstall_reply_observer_service,
    uninstall_user_service,
)


class ConfigPortabilityTests(unittest.TestCase):
    def test_relative_database_is_resolved_from_env_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            env_path = config_dir / ".env"
            env_path.write_text(
                "PRESENCE_DB_PATH=./data/presence.db\n"
                "PRESENCE_CODEX_WORKER_SCOPE=project\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(env_path, override_env=True)

            self.assertEqual(config.env_path, env_path.resolve())
            self.assertEqual(
                config.db_path,
                (config_dir / "data" / "presence.db").resolve(),
            )
            self.assertEqual(config.codex_worker_scope, "project")

    def test_env_resolution_prefers_existing_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            local_env = cwd / ".ai-presence-monitor.env"
            local_env.touch()
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(resolve_env_path(cwd=cwd), local_env.resolve())

    def test_unrelated_project_dotenv_is_not_loaded_implicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / ".env").write_text("PRESENCE_DB_PATH=wrong.db\n", encoding="utf-8")
            config_home = cwd / "config"
            with patch.dict(
                os.environ,
                {"XDG_CONFIG_HOME": str(config_home)},
                clear=True,
            ):
                resolved = resolve_env_path(cwd=cwd)

            self.assertEqual(
                resolved,
                (config_home / "ai-presence-monitor" / ".env").resolve(),
            )

    def test_codex_hook_module_entrypoint_processes_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "PRESENCE_DB_PATH=./presence.db\n"
                "PRESENCE_COMPUTER_NAME=test-host\n"
                "PRESENCE_CODEX_AUTO_START=true\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_presence_monitor.codex_hook",
                    "--env-file",
                    str(env_path),
                    "--verbose",
                ],
                input='{"hook_event_name":"PostToolUse","cwd":"/tmp/project"}',
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("atividade registrada", result.stdout)
            self.assertTrue((Path(tmp) / "presence.db").exists())


class WorkerIdentityTests(unittest.TestCase):
    def test_project_scope_is_stable_and_distinct(self) -> None:
        first = scoped_worker_id("host:codex", "project", project_path="/tmp/a")
        repeated = scoped_worker_id("host:codex", "project", project_path="/tmp/a")
        second = scoped_worker_id("host:codex", "project", project_path="/tmp/b")

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second)

    def test_project_session_scope_includes_both_dimensions(self) -> None:
        worker_id = scoped_worker_id(
            "host:codex",
            "project-session",
            project_path="/tmp/a",
            session_id="session 1",
        )

        self.assertIn(":project=a-", worker_id)
        self.assertTrue(worker_id.endswith(":session=session-1"))


class SystemdServiceTests(unittest.TestCase):
    def test_render_uses_absolute_python_and_env_without_working_directory(self) -> None:
        rendered = render_user_service(
            env_file=Path("/tmp/config with spaces/.env"),
            python_executable="/opt/venv/bin/python",
        )

        self.assertIn('ExecStart="/opt/venv/bin/python" -m ai_presence_monitor', rendered)
        self.assertIn('"/tmp/config with spaces/.env" monitor', rendered)
        self.assertNotIn("WorkingDirectory=", rendered)

    def test_install_is_idempotent_and_uninstall_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "ai-presence-monitor.service"
            env_file = Path(tmp) / ".env"

            first = install_user_service(
                env_file=env_file,
                target_path=target,
                python_executable="/usr/bin/python3",
            )
            second = install_user_service(
                env_file=env_file,
                target_path=target,
                python_executable="/usr/bin/python3",
            )
            removed = uninstall_user_service(target_path=target)

            self.assertTrue(first.changed)
            self.assertFalse(second.changed)
            self.assertTrue(removed.changed)
            self.assertIsNotNone(removed.backup_path)
            self.assertFalse(target.exists())
            assert removed.backup_path is not None
            self.assertTrue(removed.backup_path.exists())

    def test_reply_observer_service_is_separate_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "ai-presence-reply-observer.service"
            env_file = Path(tmp) / ".env"

            first = install_reply_observer_service(
                env_file=env_file,
                target_path=target,
                python_executable="/usr/bin/python3",
            )
            second = install_reply_observer_service(
                env_file=env_file,
                target_path=target,
                python_executable="/usr/bin/python3",
            )

            self.assertTrue(first.changed)
            self.assertFalse(second.changed)
            self.assertIn("observe-replies", target.read_text(encoding="utf-8"))
            self.assertIn(
                "AI Presence Discord Reply Observer",
                target.read_text(encoding="utf-8"),
            )

            removed = uninstall_reply_observer_service(target_path=target)
            self.assertTrue(removed.changed)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
