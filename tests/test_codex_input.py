from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.codex_input import (
    CodexInputError,
    CodexQueueClient,
    is_current_codex_session,
)


class FakeRunner:
    def __init__(self, result: subprocess.CompletedProcess[str] | Exception):
        self.result = result
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(
        self,
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeProcess:
    pid = 4321


class FakeLauncher:
    def __init__(self, result: FakeProcess | Exception):
        self.result = result
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, command: list[str], **kwargs: object) -> FakeProcess:
        self.calls.append((command, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class CodexQueueClientTests(unittest.TestCase):
    def test_local_send_uses_argument_list_without_shell(self) -> None:
        runner = FakeRunner(subprocess.CompletedProcess([], 0, "queued", ""))
        with patch("ai_presence_monitor.codex_input.shutil.which", return_value="/bin/codex"):
            result = CodexQueueClient(runner=runner).send(
                thread_id="thread-1",
                text=" continue ",
            )

        command, kwargs = runner.calls[0]
        self.assertEqual(
            command,
            [
                "/bin/codex",
                "queue",
                "--thread",
                "thread-1",
                "--message",
                "continue",
            ],
        )
        self.assertNotIn("shell", kwargs)
        self.assertEqual(result.thread_id, "thread-1")
        self.assertIsNone(result.remote)
        self.assertEqual(result.state, "input_emitted")

    def test_detached_send_starts_one_background_process(self) -> None:
        runner = FakeRunner(AssertionError("runner must not be called"))
        launcher = FakeLauncher(FakeProcess())
        with patch(
            "ai_presence_monitor.codex_input.shutil.which",
            return_value="/bin/codex",
        ):
            result = CodexQueueClient(
                runner=runner,
                launcher=launcher,  # type: ignore[arg-type]
            ).send(
                thread_id="thread-1",
                text="continue",
                detached=True,
            )

        command, kwargs = launcher.calls[0]
        self.assertEqual(command[0:2], ["/bin/codex", "queue"])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        self.assertTrue(kwargs["close_fds"])
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(result.state, "dispatch_started")
        self.assertEqual(result.process_id, 4321)
        self.assertEqual(runner.calls, [])

    def test_detached_windows_send_uses_process_group_without_session_flag(self) -> None:
        launcher = FakeLauncher(FakeProcess())
        with patch(
            "ai_presence_monitor.codex_input.shutil.which",
            return_value=r"C:\\Codex\\codex.exe",
        ), patch(
            "ai_presence_monitor.codex_input.sys.platform",
            "win32",
        ), patch.object(
            subprocess,
            "CREATE_NO_WINDOW",
            0x08000000,
            create=True,
        ), patch.object(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0x00000200,
            create=True,
        ):
            CodexQueueClient(
                launcher=launcher,  # type: ignore[arg-type]
            ).send(thread_id="thread-1", text="continue", detached=True)

        _, kwargs = launcher.calls[0]
        self.assertEqual(kwargs["creationflags"], 0x08000200)
        self.assertNotIn("start_new_session", kwargs)

    def test_current_session_detection_uses_codex_environment(self) -> None:
        with patch.dict(
            os.environ,
            {"CODEX_SESSION_ID": "session-current"},
            clear=True,
        ):
            self.assertTrue(is_current_codex_session("session-current"))
            self.assertFalse(is_current_codex_session("session-other"))

    def test_remote_send_requires_defined_token_environment(self) -> None:
        runner = FakeRunner(subprocess.CompletedProcess([], 0, "", ""))
        client = CodexQueueClient(runner=runner)
        with patch("ai_presence_monitor.codex_input.shutil.which", return_value="codex"):
            with self.assertRaisesRegex(CodexInputError, "exige o nome"):
                client.send(
                    thread_id="thread",
                    text="answer",
                    remote="wss://client.example/app-server",
                )
            with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
                CodexInputError,
                "nao esta definida",
            ):
                client.send(
                    thread_id="thread",
                    text="answer",
                    remote="wss://client.example/app-server",
                    remote_auth_token_env="CODEX_REMOTE_TOKEN",
                )
            with self.assertRaisesRegex(CodexInputError, "invalido"):
                client.send(
                    thread_id="thread",
                    text="answer",
                    remote="wss://client.example/app-server",
                    remote_auth_token_env="BAD=TOKEN",
                )

        self.assertEqual(runner.calls, [])

    def test_remote_send_rejects_unsupported_endpoint_scheme(self) -> None:
        runner = FakeRunner(subprocess.CompletedProcess([], 0, "", ""))
        with patch(
            "ai_presence_monitor.codex_input.shutil.which",
            return_value="codex",
        ), self.assertRaisesRegex(CodexInputError, "Endpoint remoto invalido"):
            CodexQueueClient(runner=runner).send(
                thread_id="thread",
                text="answer",
                remote="https://client.example/app-server",
                remote_auth_token_env="CODEX_REMOTE_TOKEN",
            )

        self.assertEqual(runner.calls, [])

    def test_remote_send_passes_variable_name_not_token_value(self) -> None:
        runner = FakeRunner(subprocess.CompletedProcess([], 0, "", ""))
        with patch("ai_presence_monitor.codex_input.shutil.which", return_value="codex"), patch.dict(
            os.environ,
            {"CODEX_REMOTE_TOKEN": "do-not-copy"},
            clear=True,
        ):
            CodexQueueClient(runner=runner).send(
                thread_id="thread",
                text="answer",
                remote="wss://client.example/app-server",
                remote_auth_token_env="CODEX_REMOTE_TOKEN",
            )

        command, _ = runner.calls[0]
        self.assertIn("CODEX_REMOTE_TOKEN", command)
        self.assertNotIn("do-not-copy", command)

    def test_failure_and_timeout_are_uncertain_and_not_retried(self) -> None:
        cases: tuple[subprocess.CompletedProcess[str] | Exception, str] = (
            (subprocess.CompletedProcess([], 2, "", "refused"), "incerto"),
            (subprocess.TimeoutExpired("codex", 15), "expirou"),
        )
        for result, message in cases:
            with self.subTest(message=message):
                runner = FakeRunner(result)
                with patch(
                    "ai_presence_monitor.codex_input.shutil.which",
                    return_value="codex",
                ), self.assertRaisesRegex(CodexInputError, message):
                    CodexQueueClient(runner=runner).send(
                        thread_id="thread",
                        text="continue",
                    )
                self.assertEqual(len(runner.calls), 1)

    def test_detached_launch_failure_is_reported_without_retry(self) -> None:
        launcher = FakeLauncher(OSError("denied"))
        with patch(
            "ai_presence_monitor.codex_input.shutil.which",
            return_value="codex",
        ), self.assertRaisesRegex(CodexInputError, "Falha ao iniciar"):
            CodexQueueClient(
                launcher=launcher,  # type: ignore[arg-type]
            ).send(
                thread_id="thread",
                text="continue",
                detached=True,
            )

        self.assertEqual(len(launcher.calls), 1)

    def test_cli_failure_redacts_message_from_error(self) -> None:
        runner = FakeRunner(
            subprocess.CompletedProcess([], 2, "", "failed for private answer")
        )
        with patch(
            "ai_presence_monitor.codex_input.shutil.which",
            return_value="codex",
        ), self.assertRaises(CodexInputError) as context:
            CodexQueueClient(runner=runner).send(
                thread_id="thread",
                text="private answer",
            )
        self.assertNotIn("private answer", str(context.exception))
        self.assertIn("<message>", str(context.exception))

    def test_absolute_missing_executable_and_multiline_thread_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = CodexQueueClient(executable=str(Path(tmp) / "missing"))
            with self.assertRaisesRegex(CodexInputError, "nao encontrado"):
                client.send(thread_id="thread", text="continue")
        with self.assertRaisesRegex(CodexInputError, "unica linha"):
            CodexQueueClient().send(thread_id="bad\nthread", text="continue")


if __name__ == "__main__":
    unittest.main()
