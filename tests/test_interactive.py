from __future__ import annotations

import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from test_cli import make_config

from ai_presence_monitor.interactive import (
    ENV_FIELDS,
    _ask_user_interactive,
    _prompt_choice,
    _prompt_event_args,
    _prompt_int,
    _prompt_nonnegative_int,
    _prompt_text,
    _prompt_yes_no,
    _read_env,
    _run_monitor_loop,
    _strip_quotes,
    _write_env,
    build_parser,
    configure_env,
    run_interactive,
)
from ai_presence_monitor.interactive import (
    main as interactive_main,
)


class InteractiveEnvironmentTests(unittest.TestCase):
    def test_prompt_helpers_handle_defaults_retries_and_clear(self) -> None:
        self.assertEqual(_strip_quotes('"value"'), "value")
        self.assertEqual(_strip_quotes("value"), "value")

        with patch("builtins.input", return_value=""):
            self.assertEqual(_prompt_text("Label", "default"), "default")
        with patch("builtins.input", return_value="-"):
            self.assertEqual(_prompt_text("Label", "default"), "")
        with patch("builtins.input", side_effect=["", "value"]), redirect_stdout(
            StringIO()
        ):
            self.assertEqual(_prompt_text("Label", required=True), "value")

        with patch("builtins.input", side_effect=["abc", "0", "7"]), redirect_stdout(
            StringIO()
        ):
            self.assertEqual(_prompt_int("Numero", 1), 7)
        with patch("builtins.input", side_effect=["-1", "0"]), redirect_stdout(
            StringIO()
        ):
            self.assertEqual(_prompt_nonnegative_int("Numero", 1), 0)
        with patch("builtins.input", side_effect=["invalid", "b"]), redirect_stdout(
            StringIO()
        ):
            self.assertEqual(_prompt_choice("Opcao", ["a", "b"], "a"), "b")
        with patch("builtins.input", side_effect=["talvez", "sim"]), redirect_stdout(
            StringIO()
        ):
            self.assertTrue(_prompt_yes_no("Confirmar"))
        with patch("builtins.input", return_value="n"):
            self.assertFalse(_prompt_yes_no("Confirmar", True))

    def test_write_and_read_preserve_every_supported_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            values = {field: "" for field in ENV_FIELDS}
            values.update(
                {
                    "PRESENCE_DB_PATH": "./data/presence.db",
                    "PRESENCE_DEFAULT_PROTOCOL": "protocol2",
                    "PRESENCE_COMPUTER_NAME": "test computer",
                    "PRESENCE_MONITOR_INTERVAL_SECONDS": "30",
                    "PRESENCE_WORK_WINDOW_ENABLED": "true",
                    "PRESENCE_WORK_WINDOW_START": "13:00",
                    "PRESENCE_WORK_WINDOW_END": "18:00",
                    "PRESENCE_WORK_WINDOW_TIMEZONE": "America/Sao_Paulo",
                    "PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR": "suppress_alerts",
                    "PRESENCE_ALERT_REPEAT_ENABLED": "true",
                    "PRESENCE_ALERT_REPEAT_SECONDS": "300",
                    "PRESENCE_ALERT_REPEAT_LEVELS": "yellow,orange,red",
                    "RED_NOTIFICATION_MODE": "none",
                    "RED_ALERT_MAX_DURATION_SECONDS": "15",
                    "PRESENCE_CODEX_AI_NAME": "codex",
                    "PRESENCE_CODEX_PROTOCOL": "protocol2",
                    "PRESENCE_CODEX_WORKER_SCOPE": "project",
                    "PRESENCE_CODEX_AUTO_START": "false",
                    "PRESENCE_CODEX_HOOK_FAIL_CLOSED": "false",
                }
            )

            _write_env(env_path, values)

            self.assertEqual(_read_env(env_path), values)
            if os.name != "nt":
                permissions = stat.S_IMODE(env_path.stat().st_mode)
                self.assertEqual(permissions, 0o600)

    def test_read_missing_env_returns_empty_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_read_env(Path(tmp) / "missing.env"), {})

    def test_configure_env_covers_optional_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"

            def prompt_text(
                label: str,
                default: str = "",
                **_: object,
            ) -> str:
                values = {
                    "Nome do computador nos alertas": "test-computer",
                    "Webhook do canal de ponto": "https://example.invalid/point",
                    "Webhook do canal de alertas": "https://example.invalid/alert",
                    "Comando local de alarme": "echo alarm",
                    "Worker ID fixo para Codex": "",
                    "Tarefa padrao do Codex": "",
                    "Webhook do canal de perguntas": "https://example.invalid/question",
                    "Token do bot Discord": "discord-token",
                    "ID do canal de perguntas": "200",
                    "IDs de usuarios autorizados, separados por virgula": "300",
                    "Padrao do titulo da janela do Codex": "Codex",
                }
                return values.get(label, default)

            def prompt_yes_no(label: str, default: bool = False) -> bool:
                if label in {
                    "Limitar alertas ao expediente",
                    "Repetir alertas enquanto houver atraso",
                    "Configurar observer de hooks do Codex",
                    "Ativar perguntas e respostas remotas",
                    "Ativar controle de mouse e teclado para entregar respostas",
                }:
                    return True
                if label == "Configurar Telegram":
                    return False
                return default

            with patch(
                "ai_presence_monitor.interactive._prompt_text",
                side_effect=prompt_text,
            ), patch(
                "ai_presence_monitor.interactive._prompt_yes_no",
                side_effect=prompt_yes_no,
            ), patch(
                "ai_presence_monitor.interactive._prompt_choice",
                side_effect=lambda _label, _choices, default: default,
            ), patch(
                "ai_presence_monitor.interactive._prompt_int",
                side_effect=lambda _label, default: default,
            ), patch(
                "ai_presence_monitor.interactive._prompt_nonnegative_int",
                side_effect=lambda _label, default: default,
            ), redirect_stdout(StringIO()):
                configure_env(env_path)

            values = _read_env(env_path)
            self.assertEqual(values["PRESENCE_WORK_WINDOW_ENABLED"], "true")
            self.assertEqual(values["PRESENCE_ALERT_REPEAT_ENABLED"], "true")
            self.assertEqual(values["PRESENCE_CODEX_WORKER_SCOPE"], "project")
            self.assertEqual(values["RED_ALERT_COMMAND"], "echo alarm")
            self.assertEqual(values["RED_ALERT_MAX_DURATION_SECONDS"], "15")
            self.assertEqual(values["PRESENCE_REMOTE_QUESTIONS_ENABLED"], "true")
            self.assertEqual(values["PRESENCE_QUESTION_ANSWER_TRANSPORT"], "native")
            self.assertEqual(values["PRESENCE_QUESTION_ANSWER_DESTINATION"], "local")
            self.assertEqual(values["PRESENCE_QUESTION_SESSION_MAX_AGE_SECONDS"], "300")
            self.assertEqual(values["PRESENCE_NATIVE_INPUT_ENABLED"], "true")
            self.assertEqual(values["PRESENCE_GUI_ANSWER_ENABLED"], "false")
            self.assertEqual(values["DISCORD_QUESTION_CHANNEL_ID"], "200")

            def second_choice(label: str, _choices: list[str], default: str) -> str:
                return "phone" if label == "Modo do alerta vermelho" else default

            def second_yes_no(label: str, default: bool = False) -> bool:
                if label == "Configurar Telegram":
                    return True
                if label == "Configurar observer de hooks do Codex":
                    return False
                return default

            with patch(
                "ai_presence_monitor.interactive._prompt_text",
                side_effect=prompt_text,
            ), patch(
                "ai_presence_monitor.interactive._prompt_yes_no",
                side_effect=second_yes_no,
            ), patch(
                "ai_presence_monitor.interactive._prompt_choice",
                side_effect=second_choice,
            ), patch(
                "ai_presence_monitor.interactive._prompt_int",
                side_effect=lambda _label, default: default,
            ), patch(
                "ai_presence_monitor.interactive._prompt_nonnegative_int",
                side_effect=lambda _label, default: default,
            ), redirect_stdout(StringIO()):
                configure_env(env_path)

            values = _read_env(env_path)
            self.assertEqual(values["RED_NOTIFICATION_MODE"], "phone")
            self.assertEqual(values["PRESENCE_CODEX_WORKER_SCOPE"], "project")
            self.assertEqual(values["PRESENCE_CODEX_AUTO_START"], "false")

    def test_prompt_event_and_monitor_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            with patch(
                "ai_presence_monitor.interactive._prompt_choice",
                return_value="protocol2",
            ), patch(
                "ai_presence_monitor.interactive._prompt_text",
                side_effect=["codex", "computer", "worker", "task", "message"],
            ), patch(
                "ai_presence_monitor.interactive._prompt_yes_no",
                return_value=True,
            ):
                args = _prompt_event_args(config, "touch", True)
            self.assertTrue(args.notify)
            self.assertEqual(args.worker, "worker")

            with patch(
                "ai_presence_monitor.interactive._load_current_config",
                return_value=config,
            ), patch(
                "ai_presence_monitor.interactive._prompt_int",
                return_value=1,
            ), patch(
                "ai_presence_monitor.interactive._run_monitor",
                side_effect=KeyboardInterrupt,
            ), redirect_stdout(StringIO()) as output:
                _run_monitor_loop(config.env_path, True)
            self.assertIn("Monitor interrompido", output.getvalue())

    def test_interactive_question_collects_native_session_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            with patch(
                "ai_presence_monitor.interactive._load_current_config",
                return_value=config,
            ), patch(
                "ai_presence_monitor.interactive._prompt_text",
                side_effect=[
                    "codex",
                    "computer",
                    "worker",
                    "Question?",
                    "session-exact",
                ],
            ), patch(
                "ai_presence_monitor.interactive._prompt_int",
                return_value=1800,
            ), patch(
                "ai_presence_monitor.interactive._prompt_choice",
                side_effect=["native", "local"],
            ), patch(
                "ai_presence_monitor.interactive._ask_user"
            ) as ask_user:
                _ask_user_interactive(root / ".env", dry_run=True)

            args, passed_config = ask_user.call_args.args
            self.assertIs(passed_config, config)
            self.assertEqual(args.answer_transport, "native")
            self.assertEqual(args.thread, "session-exact")
            self.assertEqual(args.answer_destination, "local")

    def test_menu_routes_all_options_without_external_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / ".env"
            env_path.touch()
            config = make_config(root)
            options = (
                [str(number) for number in range(1, 21)]
                + ["monitor", "21", "monitor", "0"]
            )

            with patch(
                "ai_presence_monitor.interactive._prompt_text",
                side_effect=options,
            ), patch(
                "ai_presence_monitor.interactive.configure_env"
            ) as configure, patch(
                "ai_presence_monitor.interactive._load_current_config",
                return_value=config,
            ), patch(
                "ai_presence_monitor.interactive._init_db"
            ) as init_db, patch(
                "ai_presence_monitor.interactive._run_event"
            ) as run_event, patch(
                "ai_presence_monitor.interactive._show_status"
            ) as show_status, patch(
                "ai_presence_monitor.interactive._run_monitor_once"
            ) as monitor_once, patch(
                "ai_presence_monitor.interactive._run_monitor_loop"
            ) as monitor_loop, patch(
                "ai_presence_monitor.interactive._show_protocols"
            ) as show_protocols, patch(
                "ai_presence_monitor.interactive._install_codex_hook_interactive"
            ) as install_hook, patch(
                "ai_presence_monitor.interactive._uninstall_codex_hook_interactive"
            ) as uninstall_hook, patch(
                "ai_presence_monitor.interactive._ask_user_interactive"
            ) as ask_user, patch(
                "ai_presence_monitor.interactive._observe_replies_once"
            ) as observe_replies, patch(
                "ai_presence_monitor.interactive._run_reply_observer_loop"
            ) as reply_loop, patch(
                "ai_presence_monitor.interactive._show_questions"
            ) as show_questions, patch(
                "ai_presence_monitor.interactive._continue_task_interactive"
            ) as continue_task, patch(
                "ai_presence_monitor.interactive._stop_alarm"
            ) as stop_alarm, redirect_stdout(StringIO()):
                run_interactive(env_path)

            configure.assert_called_once()
            init_db.assert_called_once()
            self.assertEqual(run_event.call_count, 4)
            show_status.assert_called_once()
            monitor_once.assert_called_once()
            monitor_loop.assert_called_once()
            show_protocols.assert_called_once()
            install_hook.assert_called_once()
            uninstall_hook.assert_called_once()
            ask_user.assert_called_once()
            observe_replies.assert_called_once()
            reply_loop.assert_called_once()
            show_questions.assert_called_once()
            continue_task.assert_called_once()
            stop_alarm.assert_called_once()

    def test_parser_uses_explicit_environment_file(self) -> None:
        args = build_parser().parse_args(["--env-file", "/tmp/test.env", "--dry-run"])
        self.assertEqual(args.env_file, "/tmp/test.env")
        self.assertTrue(args.dry_run)

    def test_interactive_entrypoint_blocks_windows_without_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=false\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True), patch(
                "ai_presence_monitor.platform_integration.sys.platform",
                "win32",
            ), patch(
                "ai_presence_monitor.interactive.run_interactive"
            ) as run, redirect_stdout(StringIO()), self.assertRaises(
                SystemExit
            ) as exit_context:
                interactive_main(["--env-file", str(env_path)])

            self.assertEqual(exit_context.exception.code, 2)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
