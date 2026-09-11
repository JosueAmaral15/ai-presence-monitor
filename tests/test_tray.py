from __future__ import annotations

import unittest

from ai_presence_monitor.codex_input import (
    CodexInputError,
    CodexInputResult,
    send_native_message,
)
from ai_presence_monitor.control import ControlSettings
from ai_presence_monitor.tray import build_parser, dispatch_tray_message


class FakeClient:
    def __init__(self):
        self.calls: list[dict[str, str | None]] = []

    def send(
        self,
        *,
        thread_id: str,
        text: str,
        remote: str | None = None,
        remote_auth_token_env: str | None = None,
        detached: bool = False,
    ) -> CodexInputResult:
        self.calls.append(
            {
                "thread_id": thread_id,
                "text": text,
                "remote": remote,
                "remote_auth_token_env": remote_auth_token_env,
                "detached": str(detached),
            }
        )
        return CodexInputResult(
            thread_id=thread_id,
            remote=remote,
            state="dispatch_started" if detached else "input_emitted",
        )


class TrayMessageTests(unittest.TestCase):
    def test_tray_parser_supports_check_without_loading_qt(self) -> None:
        args = build_parser().parse_args(["--env-file", "/tmp/test.env", "--check"])
        self.assertEqual(args.env_file, "/tmp/test.env")
        self.assertTrue(args.check)

    def test_local_message_ignores_remote_target(self) -> None:
        client = FakeClient()
        settings = ControlSettings(
            native_input_enabled=True,
            remote_input_enabled=True,
            codex_thread_id="thread",
            codex_remote="wss://client",
            remote_auth_token_env="TOKEN",
        )

        result = send_native_message(
            settings=settings,
            message="continue",
            destination="local",
            client=client,  # type: ignore[arg-type]
        )

        self.assertIsNone(result.remote)
        self.assertIsNone(client.calls[0]["remote"])

    def test_tray_message_is_always_dispatched_without_blocking_ui(self) -> None:
        client = FakeClient()
        settings = ControlSettings(
            native_input_enabled=True,
            codex_thread_id="thread",
        )

        result = dispatch_tray_message(
            settings=settings,
            message="continue",
            destination="local",
            thread_id=None,
            client=client,  # type: ignore[arg-type]
        )

        self.assertEqual(result.state, "dispatch_started")
        self.assertEqual(client.calls[0]["detached"], "True")

    def test_remote_message_uses_configured_client(self) -> None:
        client = FakeClient()
        settings = ControlSettings(
            native_input_enabled=True,
            remote_input_enabled=True,
            codex_thread_id="thread",
            codex_remote="wss://client",
            remote_auth_token_env="TOKEN",
        )

        send_native_message(
            settings=settings,
            message="answer",
            destination="remote",
            client=client,  # type: ignore[arg-type]
        )

        self.assertEqual(client.calls[0]["remote"], "wss://client")
        self.assertEqual(client.calls[0]["remote_auth_token_env"], "TOKEN")

    def test_disabled_or_incomplete_controls_fail_before_send(self) -> None:
        client = FakeClient()
        with self.assertRaisesRegex(CodexInputError, "nativo"):
            send_native_message(
                settings=ControlSettings(native_input_enabled=False),
                message="answer",
                destination="local",
                thread_id="thread",
                client=client,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(CodexInputError, "cliente"):
            send_native_message(
                settings=ControlSettings(
                    native_input_enabled=True,
                    remote_input_enabled=False,
                    codex_thread_id="thread",
                ),
                message="answer",
                destination="remote",
                client=client,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(CodexInputError, "nome da variavel"):
            send_native_message(
                settings=ControlSettings(
                    native_input_enabled=True,
                    remote_input_enabled=True,
                    codex_thread_id="thread",
                    codex_remote="wss://client",
                ),
                message="answer",
                destination="remote",
                client=client,  # type: ignore[arg-type]
            )
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
