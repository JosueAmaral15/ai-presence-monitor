from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from ai_presence_monitor.discord_questions import (
    DiscordQuestionClient,
    DiscordQuestionError,
)


class FakeResponse:
    def __init__(self, payload: object):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class DiscordQuestionClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = DiscordQuestionClient(
            webhook_url="https://discord.com/api/webhooks/1/token?thread_id=7",
            bot_token="secret",
            channel_id="200",
        )

    def test_post_question_requests_wait_and_disables_mentions(self) -> None:
        with patch(
            "ai_presence_monitor.discord_questions.urllib.request.urlopen",
            return_value=FakeResponse({"id": "100", "channel_id": "200"}),
        ) as urlopen:
            posted = self.client.post_question(
                question_id="question-id",
                worker_id="worker",
                prompt="@everyone escolha B",
            )

        self.assertEqual(posted.message_id, "100")
        request = urlopen.call_args.args[0]
        self.assertIn("wait=true", request.full_url)
        self.assertIn("thread_id=7", request.full_url)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertIn("@everyone escolha B", payload["content"])
        self.assertEqual(request.headers["User-agent"], "ai-presence-monitor/0.3.0")

    def test_fetch_messages_uses_bot_authorization_and_orders_snowflakes(self) -> None:
        with patch(
            "ai_presence_monitor.discord_questions.urllib.request.urlopen",
            return_value=FakeResponse(
                [
                    {"id": "12", "channel_id": "200"},
                    {"id": "10", "channel_id": "200"},
                ]
            ),
        ) as urlopen:
            messages = self.client.fetch_messages(after="9")

        self.assertEqual([item["id"] for item in messages], ["10", "12"])
        request = urlopen.call_args.args[0]
        self.assertIn("after=9", request.full_url)
        self.assertEqual(request.headers["Authorization"], "Bot secret")
        self.assertIsNone(request.data)

    def test_full_page_paginates_back_toward_cursor_without_skipping(self) -> None:
        newest = [{"id": str(value), "channel_id": "200"} for value in range(201, 301)]
        older = [{"id": str(value), "channel_id": "200"} for value in range(101, 201)]
        boundary = [{"id": "100", "channel_id": "200"}]
        with patch(
            "ai_presence_monitor.discord_questions.urllib.request.urlopen",
            side_effect=[
                FakeResponse(newest),
                FakeResponse(older),
                FakeResponse(boundary),
            ],
        ) as urlopen:
            messages = self.client.fetch_messages(after="100")

        ids = [int(item["id"]) for item in messages]
        self.assertEqual(ids[0], 101)
        self.assertEqual(ids[-1], 300)
        self.assertEqual(len(ids), 200)
        second_request = urlopen.call_args_list[1].args[0]
        self.assertIn("before=201", second_request.full_url)

    def test_invalid_ids_payload_and_network_errors_are_rejected(self) -> None:
        with self.assertRaisesRegex(DiscordQuestionError, "numerico"):
            DiscordQuestionClient(
                webhook_url="https://example.invalid",
                bot_token="secret",
                channel_id="not-an-id",
            )

        with patch(
            "ai_presence_monitor.discord_questions.urllib.request.urlopen",
            return_value=FakeResponse({"id": "100", "channel_id": "999"}),
        ):
            with self.assertRaisesRegex(DiscordQuestionError, "canal diferente"):
                self.client.post_question(
                    question_id="id",
                    worker_id="worker",
                    prompt="Pergunta",
                )

        with patch(
            "ai_presence_monitor.discord_questions.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaisesRegex(DiscordQuestionError, "offline"):
                self.client.fetch_messages()


if __name__ == "__main__":
    unittest.main()
