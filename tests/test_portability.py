from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.config import (
    load_config,
    resolve_env_path,
    user_config_dir,
    user_state_dir,
)
from ai_presence_monitor.identity import scoped_worker_id
from ai_presence_monitor.systemd_service import (
    install_reply_observer_service,
    install_user_service,
    render_user_service,
    uninstall_reply_observer_service,
    uninstall_user_service,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigPortabilityTests(unittest.TestCase):
    def test_default_control_file_uses_user_state_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / "project" / ".env"
            env_path.parent.mkdir()
            env_path.touch()
            state_home = root / "state"
            with patch.dict(
                os.environ,
                {"XDG_STATE_HOME": str(state_home)},
                clear=True,
            ):
                config = load_config(env_path, override_env=True)

            self.assertEqual(
                config.control_path,
                state_home / "ai-presence-monitor" / "control.json",
            )

    def test_user_state_directory_is_portable(self) -> None:
        with patch.dict(
            os.environ,
            {"LOCALAPPDATA": r"C:\Users\test\AppData\Local"},
            clear=True,
        ):
            self.assertEqual(
                user_state_dir("win32"),
                Path(r"C:\Users\test\AppData\Local") / "ai-presence-monitor",
            )

    def test_windows_launchers_preserve_failures_and_have_python_fallback(self) -> None:
        batch = (PROJECT_ROOT / "run_interactive.bat").read_text(encoding="utf-8")
        installer = (PROJECT_ROOT / "scripts" / "install-user-command.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("if errorlevel 1 goto python_fallback", batch)
        self.assertEqual(batch.count("exit /b %errorlevel%"), 2)
        self.assertIn("Get-Command py", installer)
        self.assertIn("Get-Command python", installer)

    def test_relative_database_is_resolved_from_env_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            config_dir.mkdir()
            env_path = config_dir / ".env"
            env_path.write_text(
                "PRESENCE_DB_PATH=./data/presence.db\n"
                "PRESENCE_CONTROL_PATH=./state/control.json\n"
                "PRESENCE_CODEX_WORKER_SCOPE=project\n"
                "PRESENCE_TASK_AUTOMATION_ENABLED=true\n"
                "PRESENCE_NATIVE_INPUT_ENABLED=false\n"
                "PRESENCE_GUI_FALLBACK_ENABLED=true\n"
                "PRESENCE_REMOTE_INPUT_ENABLED=true\n"
                "PRESENCE_QUESTION_ANSWER_TRANSPORT=gui\n"
                "PRESENCE_QUESTION_ANSWER_DESTINATION=client\n"
                "PRESENCE_QUESTION_SESSION_MAX_AGE_SECONDS=600\n"
                "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true\n"
                "PRESENCE_CONTINUE_TRANSPORT=native\n"
                "PRESENCE_CONTINUE_DESTINATION=client\n"
                "PRESENCE_CODEX_THREAD_ID=thread-1\n"
                "PRESENCE_CODEX_REMOTE=wss://client.example/app-server\n"
                "PRESENCE_CODEX_REMOTE_AUTH_TOKEN_ENV=REMOTE_TOKEN\n"
                "PRESENCE_CODEX_HOOK_EVIDENCE_TTL_SECONDS=120\n"
                "PRESENCE_CODEX_LIMIT_POLL_INTERVAL_SECONDS=180\n"
                "PRESENCE_CODEX_LIMIT_EVIDENCE_TTL_SECONDS=360\n"
                "PRESENCE_LINUX_OBSERVER_INTERVAL_SECONDS=10\n"
                "PRESENCE_LINUX_EVIDENCE_TTL_SECONDS=40\n"
                "PRESENCE_LINUX_SUSPEND_GAP_SECONDS=3.5\n"
                "PRESENCE_LINUX_SERVICE_TIMEOUT_SECONDS=2.5\n"
                "PRESENCE_LINUX_USER_SERVICES=Worker.service,monitor.service\n",
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
            self.assertEqual(
                config.control_path,
                (config_dir / "state" / "control.json").resolve(),
            )
            self.assertTrue(config.task_automation_enabled)
            self.assertFalse(config.native_input_enabled)
            self.assertTrue(config.gui_fallback_enabled)
            self.assertTrue(config.remote_input_enabled)
            self.assertEqual(config.question_answer_transport, "gui")
            self.assertEqual(config.question_answer_destination, "client")
            self.assertEqual(config.question_session_max_age_seconds, 600)
            self.assertTrue(config.experimental_windows_enabled)
            self.assertEqual(config.continue_transport, "native")
            self.assertEqual(config.continue_destination, "client")
            self.assertEqual(config.codex_thread_id, "thread-1")
            self.assertEqual(config.codex_remote, "wss://client.example/app-server")
            self.assertEqual(config.codex_remote_auth_token_env, "REMOTE_TOKEN")
            self.assertEqual(config.codex_hook_evidence_ttl_seconds, 120)
            self.assertEqual(config.codex_limit_poll_interval_seconds, 180)
            self.assertEqual(config.codex_limit_evidence_ttl_seconds, 360)
            self.assertEqual(config.linux_observer_interval_seconds, 10)
            self.assertEqual(config.linux_evidence_ttl_seconds, 40)
            self.assertEqual(config.linux_suspend_gap_seconds, 3.5)
            self.assertEqual(config.linux_service_timeout_seconds, 2.5)
            self.assertEqual(
                config.linux_user_services,
                ("Worker.service", "monitor.service"),
            )

    def test_windows_runtime_is_disabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.touch()
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(env_path, override_env=True)

            self.assertFalse(config.experimental_windows_enabled)

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
            variable = "APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"
            with patch.dict(
                os.environ,
                {variable: str(config_home)},
                clear=True,
            ):
                resolved = resolve_env_path(cwd=cwd)

            self.assertEqual(
                resolved,
                (config_home / "ai-presence-monitor" / ".env").resolve(),
            )

    def test_windows_wheel_declares_timezone_database(self) -> None:
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("tzdata>=2024.1; platform_system == 'Windows'", pyproject)

    def test_checkout_dotenv_is_supported_with_src_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / "pyproject.toml").touch()
            (cwd / "src" / "ai_presence_monitor").mkdir(parents=True)
            checkout_env = cwd / ".env"
            checkout_env.touch()

            with patch.dict(os.environ, {}, clear=True):
                resolved = resolve_env_path(cwd=cwd)

            self.assertEqual(resolved, checkout_env.resolve())

    def test_windows_configuration_uses_roaming_app_data(self) -> None:
        with patch.dict(
            os.environ,
            {"APPDATA": "C:/Users/test/AppData/Roaming"},
            clear=True,
        ):
            self.assertEqual(
                user_config_dir("win32"),
                Path("C:/Users/test/AppData/Roaming") / "ai-presence-monitor",
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
        env_file = Path("/tmp/config with spaces/.env")
        rendered = render_user_service(
            env_file=env_file,
            python_executable="python-test",
        )

        expected_env = str(env_file.resolve()).replace("\\", "\\\\")
        self.assertIn('ExecStart="python-test" -m ai_presence_monitor', rendered)
        self.assertIn(f'"{expected_env}" monitor', rendered)
        self.assertNotIn("WorkingDirectory=", rendered)
        self.assertIn("Restart=always", rendered)
        self.assertIn("RestartSec=5", rendered)
        self.assertNotIn("StartLimitIntervalSec=", rendered)
        self.assertNotIn("StartLimitBurst=", rendered)

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
            self.assertIn(
                "StartLimitIntervalSec=300",
                target.read_text(encoding="utf-8"),
            )
            self.assertIn("StartLimitBurst=3", target.read_text(encoding="utf-8"))
            self.assertIn("Restart=on-failure", target.read_text(encoding="utf-8"))
            self.assertIn("RestartSec=30", target.read_text(encoding="utf-8"))

            removed = uninstall_reply_observer_service(target_path=target)
            self.assertTrue(removed.changed)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
