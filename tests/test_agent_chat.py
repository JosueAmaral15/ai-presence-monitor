from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ai_presence_monitor.agent_chat import (
    AgentChatError,
    AgentChatPartialDeliveryError,
    append_message,
    ensure_conversation,
    project_remote_questions,
    publish_agent_message,
    send_human_message,
)
from ai_presence_monitor.codex_input import CodexInputError, CodexInputResult
from ai_presence_monitor.control import ControlSettings
from ai_presence_monitor.discord_questions import (
    DiscordQuestionError,
    PostedDiscordQuestion,
)
from ai_presence_monitor.store import SCHEMA_VERSION, PresenceStore, inspect_schema


class FakeClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def send(
        self,
        *,
        thread_id: str,
        text: str,
        remote: str | None = None,
        remote_auth_token_env: str | None = None,
        detached: bool = False,
    ) -> CodexInputResult:
        self.calls.append((thread_id, text))
        if self.fail:
            raise CodexInputError("uncertain")
        return CodexInputResult(
            thread_id=thread_id,
            remote=remote,
            state="dispatch_started",
        )


class FakeDiscordClient:
    def __init__(self, error: DiscordQuestionError | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, str]] = []

    def post_chat_message(self, **values: str) -> PostedDiscordQuestion:
        self.calls.append(values)
        if self.error is not None:
            raise self.error
        return PostedDiscordQuestion(message_id="900", channel_id="200")


class AgentChatTests(unittest.TestCase):
    def test_schema_one_migrates_additively_to_current_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.db"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE legacy_marker (value TEXT NOT NULL)")
                conn.execute("INSERT INTO legacy_marker VALUES ('preserved')")
                conn.execute("PRAGMA user_version = 1")

            PresenceStore(path)

            self.assertEqual(SCHEMA_VERSION, 3)
            self.assertTrue(inspect_schema(path).healthy)
            with sqlite3.connect(path) as conn:
                value = conn.execute("SELECT value FROM legacy_marker").fetchone()[0]
            self.assertEqual(value, "preserved")

    def test_schema_two_adds_discord_delivery_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.db"
            PresenceStore(path)
            with sqlite3.connect(path) as conn:
                conn.execute("PRAGMA user_version = 2")
                for column in (
                    "discord_channel_id",
                    "discord_message_id",
                    "discord_state",
                    "discord_error_code",
                ):
                    conn.execute(f"ALTER TABLE agent_messages DROP COLUMN {column}")

            PresenceStore(path)

            with sqlite3.connect(path) as conn:
                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(agent_messages)")
                }
            self.assertTrue(
                {
                    "discord_channel_id",
                    "discord_message_id",
                    "discord_state",
                    "discord_error_code",
                }.issubset(columns)
            )
            self.assertTrue(inspect_schema(path).healthy)

    def test_conversations_are_isolated_and_correlation_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            first = ensure_conversation(
                store,
                worker_id="worker-a",
                agent_name="codex",
                session_id="session-1",
            )
            same = ensure_conversation(
                store,
                worker_id="worker-a",
                agent_name="codex",
                session_id="session-1",
            )
            other = ensure_conversation(
                store,
                worker_id="worker-b",
                agent_name="codex",
                session_id="session-1",
            )
            one = append_message(
                store,
                conversation_id=first.conversation_id,
                role="agent",
                direction="from_agent",
                transport="discord",
                content="Question",
                state="received",
                correlation_kind="discord_question",
                correlation_id="123",
            )
            duplicate = append_message(
                store,
                conversation_id=first.conversation_id,
                role="agent",
                direction="from_agent",
                transport="discord",
                content="Question duplicated",
                state="received",
                correlation_kind="discord_question",
                correlation_id="123",
            )

            self.assertEqual(first.conversation_id, same.conversation_id)
            self.assertNotEqual(first.conversation_id, other.conversation_id)
            self.assertEqual(one.message_id, duplicate.message_id)
            self.assertEqual(duplicate.content, "Question")
            self.assertEqual(len(store.list_conversations(worker_id="worker-a")), 1)
            self.assertEqual(len(store.list_conversations(worker_id="worker-b")), 1)

    def test_pagination_is_chronological_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            conversation = store.get_or_create_conversation(
                worker_id="worker",
                agent_name="codex",
                session_id="session",
                now=1.0,
            )
            messages = [
                store.append_agent_message(
                    conversation_id=conversation.conversation_id,
                    role="agent",
                    direction="from_agent",
                    transport="local",
                    content=f"message-{index}",
                    state="published",
                    now=float(index),
                )
                for index in range(1, 6)
            ]

            newest = store.list_agent_messages(
                conversation_id=conversation.conversation_id,
                limit=2,
            )
            older = store.list_agent_messages(
                conversation_id=conversation.conversation_id,
                limit=2,
                before=(newest[0].created_at, newest[0].message_id),
            )

            self.assertEqual(
                [item.content for item in newest], ["message-4", "message-5"]
            )
            self.assertEqual(
                [item.content for item in older], ["message-2", "message-3"]
            )
            self.assertEqual(messages[0].content, "message-1")

    def test_human_dispatch_persists_state_and_later_hook_confirms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            client = FakeClient()
            result = send_human_message(
                store,
                settings=ControlSettings(
                    native_input_enabled=True,
                    codex_thread_id="session-1",
                ),
                worker_id="worker",
                agent_name="codex",
                session_id="session-1",
                content="continue",
                client=client,  # type: ignore[arg-type]
            )
            confirmed = store.confirm_deliveries(
                worker_id="worker",
                session_id="session-1",
                observed_at=result.message.updated_at + 1,
                timeout_seconds=30,
            )

            self.assertEqual(result.message.state, "dispatch_started")
            self.assertEqual(client.calls, [("session-1", "continue")])
            self.assertEqual(confirmed, 1)
            saved = store.get_agent_message(result.message.message_id)
            self.assertIsNotNone(saved)
            assert saved is not None
            self.assertEqual(saved.state, "delivery_confirmed")

    def test_explicit_agent_message_is_mirrored_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            discord = FakeDiscordClient()

            result = publish_agent_message(
                store,
                worker_id="worker",
                agent_name="codex",
                session_id="session-1",
                content="Task completed.",
                discord_client=discord,  # type: ignore[arg-type]
            )

            self.assertEqual(result.message.discord_state, "published")
            self.assertEqual(result.message.discord_channel_id, "200")
            self.assertEqual(result.message.discord_message_id, "900")
            self.assertEqual(discord.calls[0]["role"], "agent")
            messages = store.list_agent_messages(
                conversation_id=result.conversation.conversation_id
            )
            self.assertEqual(len(messages), 1)

    def test_human_native_success_and_uncertain_discord_are_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            native = FakeClient()
            discord = FakeDiscordClient(
                DiscordQuestionError("timeout", retryable=True)
            )

            with self.assertRaises(AgentChatPartialDeliveryError):
                send_human_message(
                    store,
                    settings=ControlSettings(native_input_enabled=True),
                    worker_id="worker",
                    agent_name="codex",
                    session_id="session-1",
                    content="Proceed.",
                    client=native,  # type: ignore[arg-type]
                    discord_client=discord,  # type: ignore[arg-type]
                )

            conversation = store.list_conversations(worker_id="worker")[0]
            message = store.list_agent_messages(
                conversation_id=conversation.conversation_id
            )[0]
            self.assertEqual(message.state, "dispatch_started")
            self.assertEqual(message.discord_state, "uncertain")
            self.assertEqual(
                message.discord_error_code,
                "discord_delivery_uncertain",
            )
            self.assertEqual(native.calls, [("session-1", "Proceed.")])

    def test_transport_failure_and_validation_remain_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            with self.assertRaisesRegex(AgentChatError, "transporte falhou"):
                send_human_message(
                    store,
                    settings=ControlSettings(
                        native_input_enabled=True,
                        codex_thread_id="session-1",
                    ),
                    worker_id="worker",
                    agent_name="codex",
                    session_id="session-1",
                    content="answer",
                    client=FakeClient(fail=True),  # type: ignore[arg-type]
                )
            conversation = store.list_conversations(worker_id="worker")[0]
            failed = store.list_agent_messages(
                conversation_id=conversation.conversation_id
            )[0]
            self.assertEqual(failed.state, "failed")
            self.assertEqual(failed.error_code, "transport_error")

            with self.assertRaisesRegex(AgentChatError, "cannot be empty"):
                publish_agent_message(
                    store,
                    worker_id="worker",
                    agent_name="codex",
                    session_id="session-1",
                    content="  ",
                )
            with self.assertRaisesRegex(AgentChatError, "provided together"):
                append_message(
                    store,
                    conversation_id=conversation.conversation_id,
                    role="agent",
                    direction="from_agent",
                    transport="local",
                    content="message",
                    state="published",
                    correlation_kind="kind",
                )

    def test_discord_question_and_answer_projection_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            question = store.create_question(
                worker_id="worker",
                prompt="Which option?",
                timeout_seconds=600,
                answer_transport="native",
                target_session_id="session-1",
                now=1_000.0,
            )
            store.mark_question_published(
                question.question_id,
                channel_id="channel",
                external_message_id="question-message",
                now=1_001.0,
            )
            store.record_question_answer(
                external_message_id="question-message",
                channel_id="channel",
                reply_message_id="answer-message",
                answered_by="user",
                answer="Option A",
                now=1_100.0,
            )

            first = project_remote_questions(
                store,
                worker_id="worker",
                agent_name="codex",
            )
            second = project_remote_questions(
                store,
                worker_id="worker",
                agent_name="codex",
            )
            conversation = store.list_conversations(worker_id="worker")[0]
            messages = store.list_agent_messages(
                conversation_id=conversation.conversation_id
            )

            self.assertEqual(first, 2)
            self.assertEqual(second, 2)
            self.assertEqual(len(messages), 2)
            self.assertEqual(
                [item.content for item in messages],
                ["Which option?", "Option A"],
            )
            self.assertEqual(messages[0].created_at, 1_000.0)
            self.assertEqual(messages[1].created_at, 1_100.0)


if __name__ == "__main__":
    unittest.main()
