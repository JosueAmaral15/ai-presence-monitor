from __future__ import annotations

import argparse
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ai_presence_monitor.alarm import AlarmControlError
from ai_presence_monitor.background_service import BackgroundServiceResult
from ai_presence_monitor.cli import (
    _ask_user,
    _command_allowed_while_runtime_disabled,
    _continue_task,
    _control,
    _dispatch_answer,
    _identity,
    _install_background_service,
    _install_codex_hook,
    _install_reply_observer_service,
    _install_systemd_service,
    _observe_replies_once,
    _record_event,
    _run_codex_hook,
    _run_monitor,
    _run_reply_observer,
    _send_input,
    _show_protocols,
    _show_questions,
    _show_status,
    _stop_alarm,
    _timestamp,
    _uninstall_background_service,
    _uninstall_codex_hook,
    _uninstall_reply_observer_service,
    _uninstall_systemd_service,
    build_parser,
    main,
)
from ai_presence_monitor.config import AppConfig
from ai_presence_monitor.control import ControlSettings, ControlStore
from ai_presence_monitor.notify import NotificationError
from ai_presence_monitor.store import PresenceStore


def make_config(root: Path) -> AppConfig:
    return AppConfig(
        env_path=root / ".env",
        db_path=root / "presence.db",
        default_protocol="protocol2",
        computer_name="test-computer",
        monitor_interval_seconds=30,
        work_window_enabled=False,
        work_window_start="13:00",
        work_window_end="18:00",
        work_window_timezone="UTC",
        outside_work_window_behavior="suppress_alerts",
        alert_repeat_enabled=False,
        alert_repeat_seconds=300,
        alert_repeat_levels=("yellow", "orange", "red"),
        discord_point_webhook_url=None,
        discord_alert_webhook_url=None,
        discord_red_webhook_url=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        red_notification_mode="none",
        red_alert_command=None,
        phone_webhook_url=None,
        codex_worker_id=None,
        codex_ai_name="codex",
        codex_protocol="protocol2",
        codex_task=None,
        codex_worker_scope="project",
        codex_auto_start=False,
        codex_hook_fail_closed=False,
    )


def event_args(root: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "worker": None,
        "computer": None,
        "ai": "codex",
        "protocol": "protocol2",
        "scope": "project",
        "project": root,
        "session": None,
        "task": "task",
        "message": "message",
        "notify": False,
        "dry_run": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CliBehaviorTests(unittest.TestCase):
    def test_parser_builds_every_command_and_parses_identity_options(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--dry-run",
                "start",
                "--scope",
                "project-session",
                "--project",
                "/tmp/project",
                "--session",
                "session-1",
            ]
        )

        self.assertEqual(args.command, "start")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.scope, "project-session")

        continue_args = parser.parse_args(
            [
                "--dry-run",
                "continue",
                "--message",
                "continue",
                "--delay",
                "60",
                "--window-title",
                "Codex",
                "--allow-title-change",
                "--no-sync-activity",
                "--detach",
            ]
        )
        self.assertEqual(continue_args.command, "continue")
        self.assertTrue(continue_args.allow_title_change)
        self.assertFalse(continue_args.sync_activity)
        self.assertIsNone(continue_args.destination)
        self.assertTrue(continue_args.detach)

        control_args = parser.parse_args(
            ["control", "enable", "task-automation", "--json"]
        )
        self.assertEqual(control_args.action, "enable")
        self.assertEqual(control_args.control_name, "task-automation")

        input_args = parser.parse_args(
            [
                "--dry-run",
                "send-input",
                "--message",
                "continue",
                "--thread",
                "thread-1",
                "--no-detach",
            ]
        )
        self.assertEqual(input_args.destination, "local")
        self.assertFalse(input_args.detach)

        stop_alarm_args = parser.parse_args(
            ["--dry-run", "stop-alarm", "--timeout", "1", "--no-force"]
        )
        self.assertEqual(stop_alarm_args.command, "stop-alarm")
        self.assertEqual(stop_alarm_args.timeout, 1)
        self.assertTrue(stop_alarm_args.no_force)

        background_args = parser.parse_args(
            ["--dry-run", "install-background-service", "--component", "reply-observer"]
        )
        self.assertEqual(background_args.component, "reply-observer")
        self.assertTrue(background_args.dry_run)

    def test_identity_respects_explicit_worker_and_rejects_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            args = event_args(
                Path(tmp),
                worker="exact-worker",
                computer="computer",
                ai="agent",
            )
            worker_id, computer, ai_name, protocol = _identity(args, config)

            self.assertEqual(worker_id, "exact-worker")
            self.assertEqual((computer, ai_name, protocol), ("computer", "agent", "protocol2"))

            args.protocol = "invalid"
            with self.assertRaises(ValueError):
                _identity(args, config)

    def test_record_event_covers_public_touch_and_notification_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            args = event_args(root)

            with redirect_stdout(StringIO()):
                self.assertEqual(_record_event(args, config, "start"), 0)
            worker = PresenceStore(config.db_path).list_workers()[0]
            self.assertEqual(worker.status, "active")

            with patch(
                "ai_presence_monitor.cli.Notifier.send_point",
                side_effect=NotificationError("offline"),
            ), redirect_stderr(StringIO()) as stderr:
                self.assertEqual(_record_event(args, config, "heartbeat"), 2)
            self.assertIn("offline", stderr.getvalue())

            with patch("ai_presence_monitor.cli.Notifier.send_point") as send_point:
                with redirect_stdout(StringIO()):
                    self.assertEqual(_record_event(args, config, "touch"), 0)
                send_point.assert_not_called()

            args.notify = True
            with patch("ai_presence_monitor.cli.Notifier.send_point") as send_point:
                with redirect_stdout(StringIO()):
                    self.assertEqual(_record_event(args, config, "touch"), 0)
                send_point.assert_called_once()

    def test_monitor_once_and_continuous_interrupt(self) -> None:
        args = argparse.Namespace(once=True, interval=None, dry_run=True)
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            with patch("ai_presence_monitor.cli._check_once", return_value=0) as check:
                self.assertEqual(_run_monitor(args, config), 0)
                check.assert_called_once()

            args.once = False
            args.interval = 2
            with patch("ai_presence_monitor.cli._check_once"), patch(
                "ai_presence_monitor.cli.time.sleep",
                side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    _run_monitor(args, config)

    def test_status_protocols_and_timestamp_outputs(self) -> None:
        self.assertEqual(_timestamp(None), "sem registro")
        self.assertNotEqual(_timestamp(0), "sem registro")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_show_status(config), 0)
            self.assertIn("Nenhum worker", output.getvalue())

            PresenceStore(config.db_path).record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
                task="task",
            )
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_show_status(config), 0)
            self.assertIn("worker | active", output.getvalue())

        with redirect_stdout(StringIO()) as output:
            self.assertEqual(_show_protocols(), 0)
        self.assertIn("protocol1", output.getvalue())
        self.assertIn("protocol2", output.getvalue())

    def test_codex_and_service_install_helpers_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            hooks_target = root / "hooks.json"
            hook_args = argparse.Namespace(
                target=hooks_target,
                hook_script=None,
                python=None,
                timeout=5,
                dry_run=False,
                no_backup=False,
            )
            with redirect_stdout(StringIO()):
                self.assertEqual(_install_codex_hook(hook_args, config), 0)
                self.assertEqual(_install_codex_hook(hook_args, config), 0)
                self.assertEqual(_uninstall_codex_hook(hook_args, config), 0)

            service_target = root / "monitor.service"
            service_args = argparse.Namespace(
                target=service_target,
                python="/usr/bin/python3",
                dry_run=False,
                no_backup=False,
            )
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_install_systemd_service(service_args, config), 0)
            self.assertIn("daemon-reload", output.getvalue())
            with redirect_stdout(StringIO()):
                self.assertEqual(_uninstall_systemd_service(service_args, config), 0)

            reply_target = root / "reply.service"
            service_args.target = reply_target
            with redirect_stdout(StringIO()):
                self.assertEqual(
                    _install_reply_observer_service(service_args, config),
                    0,
                )
                self.assertEqual(
                    _uninstall_reply_observer_service(service_args, config),
                    0,
                )

    def test_portable_background_service_helpers_use_platform_factory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            result = BackgroundServiceResult(
                action="install",
                component="monitor",
                target_path=root / "service.xml",
                changed=True,
                backup_path=None,
                rendered_definition="definition\n",
                follow_up_commands=(),
            )
            manager = SimpleNamespace(
                install=Mock(return_value=result),
                uninstall=Mock(
                    return_value=replace(result, action="uninstall")
                ),
            )
            factory = SimpleNamespace(
                create_background_service_manager=lambda: manager,
            )
            args = argparse.Namespace(
                component="monitor",
                target=None,
                python=None,
                dry_run=True,
                no_backup=False,
            )
            with patch(
                "ai_presence_monitor.cli.get_platform_factory",
                return_value=factory,
            ), redirect_stdout(StringIO()):
                self.assertEqual(_install_background_service(args, config), 0)
                self.assertEqual(_uninstall_background_service(args, config), 0)

            manager.install.assert_called_once()
            manager.uninstall.assert_called_once()

    def test_remote_question_cli_helpers_are_safe_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            args = event_args(
                root,
                question="Qual opcao?",
                timeout=None,
                window_id=None,
                window_title=None,
            )

            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_ask_user(args, config), 0)
            self.assertIn("[dry-run:pergunta]", output.getvalue())
            self.assertFalse(config.db_path.exists())

            args.timeout = 0
            with self.assertRaisesRegex(ValueError, "maior que zero"):
                _ask_user(args, config)

            observer_args = argparse.Namespace(once=True, interval=None, dry_run=True)
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_run_reply_observer(observer_args, config), 0)
            self.assertIn("nao foram acessados", output.getvalue())

            dispatch_args = argparse.Namespace(
                question_id="question-id",
                dry_run=True,
            )
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_dispatch_answer(dispatch_args, config), 0)
            self.assertIn("mouse, teclado e banco", output.getvalue())

            list_args = argparse.Namespace(status=None, limit=50)
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_show_questions(list_args, config), 0)
            self.assertIn("Nenhuma pergunta", output.getvalue())

            with redirect_stdout(StringIO()):
                self.assertEqual(_observe_replies_once(config, dry_run=True), 0)

    def test_continue_cli_dry_run_does_not_use_gui_or_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                make_config(root),
                continue_transport="gui",
                gui_fallback_enabled=True,
            )
            args = event_args(
                root,
                message=None,
                delay=None,
                window_id=None,
                window_title="Codex",
                allow_title_change=False,
                sync_activity=None,
            )

            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_continue_task(args, config), 0)

            self.assertIn("[dry-run:continue]", output.getvalue())
            self.assertIn("atraso=60s", output.getvalue())
            self.assertFalse(config.db_path.exists())

    def test_continue_cli_fails_closed_when_automation_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                make_config(root),
                control_path=root / "control.json",
                continue_transport="native",
                codex_thread_id="thread",
            )
            args = event_args(
                root,
                dry_run=False,
                message=None,
                delay=0,
                window_id=None,
                window_title=None,
                allow_title_change=False,
                sync_activity=None,
                transport=None,
                thread=None,
                remote=None,
                remote_auth_token_env=None,
                destination=None,
                authorize_once=False,
            )

            with redirect_stderr(StringIO()) as error:
                self.assertEqual(_continue_task(args, config), 2)

            self.assertIn("automacao de tarefas desativada", error.getvalue())

    def test_control_and_send_input_dry_run_share_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(make_config(root), control_path=root / "control.json")
            enable_args = argparse.Namespace(
                action="enable",
                control_name="task-automation",
                clear_thread=False,
                clear_remote=False,
                thread=None,
                remote=None,
                remote_auth_token_env=None,
                json=False,
            )
            with redirect_stdout(StringIO()):
                self.assertEqual(_control(enable_args, config), 0)
            saved = ControlStore.from_config(config).load()
            self.assertTrue(saved.task_automation_enabled)

            ControlStore.from_config(config).save(
                ControlSettings(
                    task_automation_enabled=True,
                    native_input_enabled=True,
                    codex_thread_id="thread-1",
                )
            )
            input_args = argparse.Namespace(
                destination="local",
                thread=None,
                message="answer",
                dry_run=True,
            )
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_send_input(input_args, config), 0)
            self.assertIn("sessao=thread-1", output.getvalue())

            dry_control = argparse.Namespace(
                action="disable",
                control_name="task-automation",
                clear_thread=False,
                clear_remote=False,
                thread=None,
                remote=None,
                remote_auth_token_env=None,
                json=False,
                dry_run=True,
            )
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(_control(dry_control, config), 0)
            self.assertIn("alteracao nao persistida", output.getvalue())
            self.assertTrue(
                ControlStore.from_config(config).load().task_automation_enabled
            )

            input_args.message = " "
            with redirect_stderr(StringIO()) as error:
                self.assertEqual(_send_input(input_args, config), 2)
            self.assertIn("nao pode ficar vazia", error.getvalue())

    def test_stop_alarm_reports_each_outcome_and_errors(self) -> None:
        args = argparse.Namespace(timeout=3.0, no_force=False, dry_run=False)
        outcomes = (
            ("stopped", "alarme interrompido"),
            ("stale_state", "estado obsoleto removido"),
            ("not_running", "nenhum alarme controlado"),
        )
        for status, expected in outcomes:
            with self.subTest(status=status), patch(
                "ai_presence_monitor.cli.AlarmController.stop",
                return_value=SimpleNamespace(
                    status=status,
                    pid=123 if status != "not_running" else None,
                    forced=False,
                ),
            ), redirect_stdout(StringIO()) as output:
                self.assertEqual(_stop_alarm(args), 0)
                self.assertIn(expected, output.getvalue())

        args.dry_run = True
        with patch(
            "ai_presence_monitor.cli.AlarmController.stop",
            return_value=SimpleNamespace(
                status="would_stop",
                pid=123,
                forced=False,
            ),
        ), redirect_stdout(StringIO()) as output:
            self.assertEqual(_stop_alarm(args), 0)
        self.assertIn("interromperia PID 123", output.getvalue())

        with patch(
            "ai_presence_monitor.cli.AlarmController.stop",
            side_effect=AlarmControlError("falha"),
        ), redirect_stderr(StringIO()) as error:
            self.assertEqual(_stop_alarm(args), 2)
        self.assertIn("falha", error.getvalue())

    def test_run_codex_hook_reads_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            args = argparse.Namespace(
                dry_run=True,
                verbose=True,
                fail_closed=False,
                auto_start=False,
                no_auto_start=False,
            )
            payload = '{"hook_event_name":"PostToolUse","cwd":"/tmp/project"}'
            with patch("ai_presence_monitor.cli.sys.stdin", StringIO(payload)):
                self.assertEqual(_run_codex_hook(args, config), 0)

    def test_main_success_db_override_and_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / ".env"
            env_path.write_text(
                "PRESENCE_DB_PATH=./presence.db\n"
                "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as exit_context:
                main(["--env-file", str(env_path), "protocols"])
            self.assertEqual(exit_context.exception.code, 0)

            override_db = root / "override.db"
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as exit_context:
                main(
                    [
                        "--env-file",
                        str(env_path),
                        "--db",
                        str(override_db),
                        "init",
                    ]
                )
            self.assertEqual(exit_context.exception.code, 0)
            self.assertTrue(override_db.exists())

            invalid_env = root / "invalid.env"
            invalid_env.write_text("PRESENCE_CODEX_WORKER_SCOPE=invalid\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False), redirect_stderr(
                StringIO()
            ) as stderr, self.assertRaises(SystemExit) as exit_context:
                main(["--env-file", str(invalid_env), "status"])
            self.assertEqual(exit_context.exception.code, 1)
            self.assertIn("Escopo de worker invalido", stderr.getvalue())

    def test_main_blocks_windows_operations_without_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / ".env"
            env_path.write_text(
                "PRESENCE_DB_PATH=./presence.db\n"
                "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=false\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True), patch(
                "ai_presence_monitor.platform_integration.sys.platform",
                "win32",
            ), redirect_stderr(StringIO()) as error, self.assertRaises(
                SystemExit
            ) as exit_context:
                main(["--env-file", str(env_path), "init"])

            self.assertEqual(exit_context.exception.code, 1)
            self.assertIn("Windows e experimental", error.getvalue())
            self.assertFalse((root / "presence.db").exists())

    def test_main_allows_explicit_windows_opt_in_and_safe_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            enabled_env = root / "enabled.env"
            enabled_env.write_text(
                "PRESENCE_DB_PATH=./enabled.db\n"
                "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true\n",
                encoding="utf-8",
            )
            disabled_env = root / "disabled.env"
            disabled_env.write_text(
                "PRESENCE_DB_PATH=./disabled.db\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True), patch(
                "ai_presence_monitor.platform_integration.sys.platform",
                "win32",
            ):
                with redirect_stdout(StringIO()), self.assertRaises(
                    SystemExit
                ) as enabled_exit:
                    main(["--env-file", str(enabled_env), "init"])
                with redirect_stdout(StringIO()), self.assertRaises(
                    SystemExit
                ) as status_exit:
                    main(["--env-file", str(disabled_env), "status"])

            self.assertEqual(enabled_exit.exception.code, 0)
            self.assertEqual(status_exit.exception.code, 0)
            self.assertTrue((root / "enabled.db").exists())

    def test_main_does_not_let_dry_run_bypass_windows_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / ".env"
            env_path.write_text("PRESENCE_DB_PATH=./presence.db\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch(
                "ai_presence_monitor.platform_integration.sys.platform",
                "win32",
            ), redirect_stderr(StringIO()) as error, self.assertRaises(
                SystemExit
            ) as exit_context:
                main(
                    [
                        "--env-file",
                        str(env_path),
                        "--dry-run",
                        "start",
                        "--project",
                        str(root),
                    ]
                )

            self.assertEqual(exit_context.exception.code, 1)
            self.assertIn("Windows e experimental", error.getvalue())
            self.assertFalse((root / "presence.db").exists())

    def test_disabled_runtime_preserves_only_diagnostics_and_recovery(self) -> None:
        for command in (
            "finish",
            "protocols",
            "questions",
            "status",
            "stop-alarm",
            "uninstall-background-service",
            "uninstall-codex-hook",
            "uninstall-reply-observer-service",
            "uninstall-systemd-service",
        ):
            with self.subTest(command=command):
                self.assertTrue(
                    _command_allowed_while_runtime_disabled(
                        argparse.Namespace(command=command)
                    )
                )

        self.assertTrue(
            _command_allowed_while_runtime_disabled(
                argparse.Namespace(command="control", action="show")
            )
        )
        self.assertTrue(
            _command_allowed_while_runtime_disabled(
                argparse.Namespace(command="control", action="disable")
            )
        )
        self.assertFalse(
            _command_allowed_while_runtime_disabled(
                argparse.Namespace(command="control", action="enable")
            )
        )


if __name__ == "__main__":
    unittest.main()
