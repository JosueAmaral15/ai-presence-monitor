from __future__ import annotations

import argparse
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from test_cli import make_config

from ai_presence_monitor.agent_chat import AgentChatError
from ai_presence_monitor.cli import (
    _archive_chat,
    _current_chat_identity,
    _export_chat,
    _publish_agent_chat_message,
    _show_chat_messages,
    _show_conversations,
    build_parser,
)
from ai_presence_monitor.store import PresenceStore


class AgentChatCliTests(unittest.TestCase):
    def test_parser_exposes_chat_commands(self) -> None:
        parser = build_parser()
        publish = parser.parse_args(
            [
                "publish-agent-message",
                "--project",
                "/tmp/project",
                "--session",
                "session-1",
                "--text",
                "done",
            ]
        )
        conversations = parser.parse_args(["conversations"])
        messages = parser.parse_args(["messages", "--conversation", "abc"])
        exported = parser.parse_args(
            ["export-conversation", "--conversation", "abc", "--redact-content"]
        )

        self.assertEqual(publish.text, "done")
        self.assertEqual(conversations.limit, 50)
        self.assertEqual(messages.conversation, "abc")
        self.assertTrue(exported.redact_content)

    def test_publish_and_read_are_limited_to_current_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            config = make_config(root)
            args = argparse.Namespace(
                project=root,
                session="session-1",
                ai="codex",
                text="task completed",
                dry_run=False,
            )
            with patch("ai_presence_monitor.cli.Path.cwd", return_value=root):
                worker_id, _, _ = _current_chat_identity(args, config)
                PresenceStore(config.db_path).record_event(
                    worker_id=worker_id,
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="start",
                )
                with redirect_stdout(StringIO()):
                    self.assertEqual(_publish_agent_chat_message(args, config), 0)

                list_args = argparse.Namespace(
                    project=root,
                    session="session-1",
                    ai="codex",
                    limit=50,
                    offset=0,
                )
                with redirect_stdout(StringIO()) as output:
                    self.assertEqual(_show_conversations(list_args, config), 0)
                conversation_id = (
                    PresenceStore(config.db_path)
                    .list_conversations(worker_id=worker_id)[0]
                    .conversation_id
                )
                list_args.conversation = conversation_id
                with redirect_stdout(StringIO()) as output:
                    self.assertEqual(_show_chat_messages(list_args, config), 0)
                self.assertIn("task completed", output.getvalue())

                export_args = argparse.Namespace(
                    project=root,
                    session="session-1",
                    ai="codex",
                    conversation=conversation_id,
                    limit=200,
                    redact_content=True,
                )
                with redirect_stdout(StringIO()) as output:
                    self.assertEqual(_export_chat(export_args, config), 0)
                self.assertIn("[redacted]", output.getvalue())
                self.assertNotIn("task completed", output.getvalue())

                archive_args = argparse.Namespace(
                    project=root,
                    session="session-1",
                    ai="codex",
                    conversation=conversation_id,
                    dry_run=False,
                )
                with redirect_stdout(StringIO()):
                    self.assertEqual(_archive_chat(archive_args, config), 0)
                self.assertEqual(
                    PresenceStore(config.db_path).list_conversations(
                        worker_id=worker_id
                    ),
                    [],
                )

                outside = argparse.Namespace(
                    project=root.parent,
                    session="session-1",
                    ai="codex",
                )
                with self.assertRaisesRegex(AgentChatError, "current project"):
                    _current_chat_identity(outside, config)

    def test_publish_requires_existing_worker_and_pagination_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            config = make_config(root)
            args = argparse.Namespace(
                project=root,
                session="session-1",
                ai="codex",
                text="message",
                dry_run=False,
            )
            with patch("ai_presence_monitor.cli.Path.cwd", return_value=root):
                with self.assertRaisesRegex(AgentChatError, "Run start"):
                    _publish_agent_chat_message(args, config)
                invalid = argparse.Namespace(
                    project=root,
                    session="session-1",
                    ai="codex",
                    limit=0,
                    offset=0,
                )
                with self.assertRaisesRegex(AgentChatError, "out of range"):
                    _show_conversations(invalid, config)


if __name__ == "__main__":
    unittest.main()
