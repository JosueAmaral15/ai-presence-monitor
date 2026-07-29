from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from test_cli import make_config

from ai_presence_monitor.discord_questions import (
    DiscordQuestionError,
    PostedDiscordQuestion,
)
from ai_presence_monitor.gui_answer import GuiDispatchError, WindowTarget
from ai_presence_monitor.remote_questions import (
    CURSOR_KEY_PREFIX,
    RemoteQuestionError,
    ask_remote_question,
    observe_discord_replies_once,
    retry_gui_dispatch,
    validate_remote_question_config,
)
from ai_presence_monitor.store import PresenceStore


class FakeDiscordClient:
    def __init__(
        self,
        messages: list[dict[str, object]] | None = None,
        *,
        post_error: Exception | None = None,
    ):
        self.messages = messages or []
        self.post_error = post_error
        self.posted: list[dict[str, str]] = []
        self.after: str | None = None

    def post_question(
        self,
        *,
        question_id: str,
        worker_id: str,
        prompt: str,
    ) -> PostedDiscordQuestion:
        if self.post_error:
            raise self.post_error
        self.posted.append(
            {
                "question_id": question_id,
                "worker_id": worker_id,
                "prompt": prompt,
            }
        )
        return PostedDiscordQuestion(message_id="100", channel_id="200")

    def fetch_messages(self, *, after: str | None = None) -> list[dict[str, object]]:
        self.after = after
        return self.messages


class FakeDispatcher:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.dispatched: list[str] = []

    def capture_target(
        self,
        *,
        title_pattern: str,
        window_id: str | None = None,
    ) -> WindowTarget:
        return WindowTarget(
            window_id=window_id or "900",
            title="Codex - project",
            pattern=title_pattern,
        )

    def dispatch(self, question: object) -> None:
        if self.fail:
            raise GuiDispatchError("janela ausente")
        self.dispatched.append(question.question_id)  # type: ignore[attr-defined]


def remote_config(root: Path, *, gui: bool = True):
    return replace(
        make_config(root),
        remote_questions_enabled=True,
        discord_question_webhook_url="https://example.invalid/webhook",
        discord_bot_token="secret-token",
        discord_question_channel_id="200",
        discord_allowed_user_ids=("300",),
        question_poll_interval_seconds=5,
        question_timeout_seconds=1800,
        gui_answer_enabled=gui,
        codex_gui_window_title="Codex",
        codex_gui_click_x_ratio=0.5,
        codex_gui_click_y_ratio=0.9,
        gui_confirmation_timeout_seconds=120,
    )


def reply_message(
    *,
    message_id: str,
    author_id: str = "300",
    reply_to: str | None = "100",
    content: str = "Use a opcao B.",
    bot: bool = False,
) -> dict[str, object]:
    message: dict[str, object] = {
        "id": message_id,
        "channel_id": "200",
        "author": {"id": author_id, "bot": bot},
        "content": content,
    }
    if reply_to is not None:
        message["message_reference"] = {"message_id": reply_to}
    return message


class RemoteQuestionFlowTests(unittest.TestCase):
    def test_config_is_fail_closed_and_requires_all_discord_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            with self.assertRaisesRegex(RemoteQuestionError, "desativadas"):
                validate_remote_question_config(config)

            incomplete = replace(config, remote_questions_enabled=True)
            with self.assertRaisesRegex(RemoteQuestionError, "DISCORD_BOT_TOKEN"):
                validate_remote_question_config(incomplete)

            with self.assertRaisesRegex(RemoteQuestionError, "maior que zero"):
                ask_remote_question(
                    config=remote_config(Path(tmp), gui=False),
                    store=PresenceStore(Path(tmp) / "questions.db"),
                    worker_id="worker",
                    prompt="Pergunta",
                    timeout_seconds=0,
                    client=FakeDiscordClient(),  # type: ignore[arg-type]
                )

    def test_ask_persists_discord_and_exact_window_correlation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PresenceStore(root / "presence.db")
            client = FakeDiscordClient()
            dispatcher = FakeDispatcher()

            question = ask_remote_question(
                config=remote_config(root),
                store=store,
                worker_id="worker",
                prompt=" Qual caminho devo seguir? ",
                timeout_seconds=60,
                window_id="901",
                client=client,  # type: ignore[arg-type]
                dispatcher=dispatcher,  # type: ignore[arg-type]
                now=1000,
            )

            self.assertEqual(question.status, "pending")
            self.assertEqual(question.external_message_id, "100")
            self.assertEqual(question.channel_id, "200")
            self.assertEqual(question.target_window_id, "901")
            self.assertEqual(question.target_window_title, "Codex - project")
            self.assertEqual(question.expires_at, 1060)
            self.assertEqual(client.posted[0]["prompt"], "Qual caminho devo seguir?")

    def test_publish_failure_is_auditable_and_not_left_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PresenceStore(root / "presence.db")
            client = FakeDiscordClient(
                post_error=DiscordQuestionError("offline"),
            )
            with self.assertRaisesRegex(RemoteQuestionError, "offline"):
                ask_remote_question(
                    config=remote_config(root, gui=False),
                    store=store,
                    worker_id="worker",
                    prompt="Pergunta",
                    client=client,  # type: ignore[arg-type]
                    now=1000,
                )

            questions = store.list_questions()
            self.assertEqual(len(questions), 1)
            self.assertEqual(questions[0].status, "publish_failed")
            self.assertEqual(questions[0].last_error, "offline")

    def test_observer_accepts_only_authorized_direct_reply_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = remote_config(root)
            store = PresenceStore(root / "presence.db")
            question = store.create_question(
                worker_id="worker",
                prompt="Pergunta",
                timeout_seconds=100,
                target_window_id="900",
                target_window_title="Codex",
                target_window_pattern="Codex",
                now=1000,
            )
            store.mark_question_published(
                question.question_id,
                channel_id="200",
                external_message_id="100",
                now=1000,
            )
            client = FakeDiscordClient(
                [
                    reply_message(message_id="101", author_id="999"),
                    reply_message(message_id="102", reply_to=None),
                    reply_message(message_id="103", bot=True),
                    reply_message(message_id="104"),
                ]
            )
            dispatcher = FakeDispatcher()

            result = observe_discord_replies_once(
                config=config,
                store=store,
                client=client,  # type: ignore[arg-type]
                dispatcher=dispatcher,  # type: ignore[arg-type]
                now=1010,
            )

            self.assertEqual(result.fetched, 4)
            self.assertEqual(result.accepted, 1)
            self.assertEqual(result.dispatched, 1)
            self.assertEqual(client.after, "100")
            saved = store.require_question(question.question_id)
            self.assertEqual(saved.status, "input_emitted")
            self.assertEqual(saved.answer, "Use a opcao B.")
            self.assertEqual(saved.answered_by, "300")
            self.assertEqual(dispatcher.dispatched, [question.question_id])
            cursor_key = CURSOR_KEY_PREFIX + "200"
            self.assertEqual(store.get_observer_state(cursor_key), "104")

            duplicate = observe_discord_replies_once(
                config=config,
                store=store,
                client=FakeDiscordClient([reply_message(message_id="104")]),  # type: ignore[arg-type]
                dispatcher=dispatcher,  # type: ignore[arg-type]
                now=1020,
            )
            self.assertEqual(duplicate.accepted, 0)
            self.assertEqual(len(dispatcher.dispatched), 1)

    def test_gui_failure_stops_automatic_retry_and_manual_retry_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = remote_config(root)
            store = PresenceStore(root / "presence.db")
            question = store.create_question(
                worker_id="worker",
                prompt="Pergunta",
                timeout_seconds=100,
                target_window_id="900",
                target_window_title="Codex",
                target_window_pattern="Codex",
                now=1000,
            )
            store.mark_question_published(
                question.question_id,
                channel_id="200",
                external_message_id="100",
                now=1000,
            )

            result = observe_discord_replies_once(
                config=config,
                store=store,
                client=FakeDiscordClient([reply_message(message_id="101")]),  # type: ignore[arg-type]
                dispatcher=FakeDispatcher(fail=True),  # type: ignore[arg-type]
                now=1010,
            )
            self.assertEqual(result.dispatch_failed, 1)
            failed = store.require_question(question.question_id)
            self.assertEqual(failed.status, "dispatch_failed")

            retried = retry_gui_dispatch(
                config=config,
                store=store,
                question_id=question.question_id,
                dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
                now=1020,
            )
            self.assertEqual(retried.status, "input_emitted")

    def test_expired_question_does_not_accept_late_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            question = store.create_question(
                worker_id="worker",
                prompt="Pergunta",
                timeout_seconds=5,
                now=1000,
            )
            store.mark_question_published(
                question.question_id,
                channel_id="200",
                external_message_id="100",
                now=1000,
            )

            accepted = store.record_question_answer(
                external_message_id="100",
                channel_id="200",
                reply_message_id="101",
                answered_by="300",
                answer="tarde",
                now=1010,
            )
            self.assertIsNone(accepted)
            self.assertEqual(
                store.require_question(question.question_id).status,
                "expired",
            )


if __name__ == "__main__":
    unittest.main()
