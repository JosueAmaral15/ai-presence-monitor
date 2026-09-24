from __future__ import annotations

import json
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ai_presence_monitor.alarm import AlarmControlError
from ai_presence_monitor.notify import NotificationError, Notifier


class FakeResponse:
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b""


class NotifierTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.notifier = Notifier(SimpleNamespace(), dry_run=False)  # type: ignore[arg-type]

    def test_post_json_sends_expected_payload_and_headers(self) -> None:
        with patch(
            "ai_presence_monitor.notify.urllib.request.urlopen",
            return_value=FakeResponse(),
        ) as urlopen:
            self.notifier._post_json(
                "https://example.invalid/webhook",
                {"message": "teste"},
                label="teste",
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"message": "teste"})
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(request.headers["User-agent"], "ai-presence-monitor/0.9.0")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 15)

    def test_post_json_wraps_network_error(self) -> None:
        with patch(
            "ai_presence_monitor.notify.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaisesRegex(NotificationError, "teste"):
                self.notifier._post_json(
                    "https://example.invalid/webhook",
                    {"message": "teste"},
                    label="teste",
                )

    def test_dry_run_does_not_open_network(self) -> None:
        notifier = Notifier(SimpleNamespace(), dry_run=True)  # type: ignore[arg-type]
        with patch("ai_presence_monitor.notify.urllib.request.urlopen") as urlopen:
            notifier._post_json(
                "https://example.invalid/webhook",
                {"message": "teste"},
                label="teste",
            )

        urlopen.assert_not_called()

    def test_alarm_start_reports_control_command_and_deduplicates(self) -> None:
        controller = SimpleNamespace(
            start=Mock(
                side_effect=[
                    SimpleNamespace(status="started", pid=123),
                    SimpleNamespace(status="already_running", pid=123),
                ]
            )
        )
        notifier = Notifier(
            SimpleNamespace(),  # type: ignore[arg-type]
            alarm_controller=controller,  # type: ignore[arg-type]
        )

        with patch("builtins.print") as output:
            notifier._start_alarm("player alarm.wav")
            notifier._start_alarm("player alarm.wav")

        self.assertIn("ai-presence stop-alarm", output.call_args_list[0].args[0])
        self.assertIn("encerramento automatico em 15s", output.call_args_list[0].args[0])
        self.assertIn("ja esta ativo", output.call_args_list[1].args[0])
        self.assertEqual(controller.start.call_count, 2)

    def test_alarm_control_error_becomes_notification_error(self) -> None:
        controller = SimpleNamespace(
            start=Mock(side_effect=AlarmControlError("controle indisponivel"))
        )
        notifier = Notifier(
            SimpleNamespace(),  # type: ignore[arg-type]
            alarm_controller=controller,  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(NotificationError, "controle indisponivel"):
            notifier._start_alarm("player alarm.wav")


if __name__ == "__main__":
    unittest.main()
