from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from dataclasses import replace
from pathlib import Path

from ai_presence_monitor.cli import _identity
from ai_presence_monitor.codex_hook import (
    build_observation,
    load_hook_payload,
    record_codex_hook_payload,
    run_from_stdin,
)
from ai_presence_monitor.config import AppConfig
from ai_presence_monitor.store import PresenceStore


def make_config(db_path: Path, *, auto_start: bool = False) -> AppConfig:
    return AppConfig(
        env_path=db_path.parent / ".env",
        db_path=db_path,
        default_protocol="protocol2",
        computer_name="test-computer",
        monitor_interval_seconds=30,
        work_window_enabled=False,
        work_window_start="13:00",
        work_window_end="18:00",
        work_window_timezone="America/Sao_Paulo",
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
        codex_protocol=None,
        codex_task=None,
        codex_worker_scope="global",
        codex_auto_start=auto_start,
        codex_hook_fail_closed=False,
    )


class CodexHookTests(unittest.TestCase):
    def test_load_hook_payload_requires_json_object(self) -> None:
        self.assertEqual(load_hook_payload("{}"), {})
        with self.assertRaises(ValueError):
            load_hook_payload("[]")

    def test_build_observation_accepts_camel_case_event_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db")
            payload = {
                "hookEventName": "PostToolUse",
                "toolName": "Bash",
                "session_id": "session-1",
                "cwd": "/tmp/example-project",
                "model": "gpt-test",
            }

            observation = build_observation(payload, config)

            self.assertEqual(observation.event_name, "PostToolUse")
            self.assertEqual(observation.worker_id, "test-computer:codex")
            self.assertEqual(observation.protocol, "protocol2")
            self.assertEqual(observation.task, "example-project")
            self.assertIn("tool=Bash", observation.message)
            self.assertIn("session=session-1", observation.message)

    def test_observation_without_auto_start_ignores_missing_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db", auto_start=False)
            payload = {"hook_event_name": "PostToolUse", "cwd": "/tmp/project"}

            worker = record_codex_hook_payload(payload=payload, config=config)

            self.assertIsNone(worker)
            self.assertEqual(PresenceStore(config.db_path).list_workers(), [])

    def test_observation_updates_active_worker_without_public_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db", auto_start=False)
            store = PresenceStore(config.db_path)
            initial = store.record_event(
                worker_id="test-computer:codex",
                computer="test-computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
                message="inicio",
                task="project",
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "cwd": "/tmp/project",
            }

            worker = record_codex_hook_payload(payload=payload, config=config)

            self.assertIsNotNone(worker)
            updated = store.get_worker("test-computer:codex")
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.last_signal_at, initial.last_signal_at)
            self.assertGreater(updated.last_activity_at or 0, initial.last_activity_at or 0)
            self.assertIn("PreToolUse", updated.last_message or "")

    def test_hook_confirms_recent_gui_input_for_same_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db", auto_start=False)
            store = PresenceStore(config.db_path)
            store.record_event(
                worker_id="test-computer:codex",
                computer="test-computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
                task="project",
            )
            question = store.create_question(
                worker_id="test-computer:codex",
                prompt="Pergunta",
                timeout_seconds=60,
                target_window_id="10",
                target_window_title="Codex",
                target_window_pattern="Codex",
            )
            store.mark_question_published(
                question.question_id,
                channel_id="200",
                external_message_id="100",
            )
            answered = store.record_question_answer(
                external_message_id="100",
                channel_id="200",
                reply_message_id="101",
                answered_by="300",
                answer="Resposta",
            )
            assert answered is not None
            store.mark_input_emitted(question.question_id)

            record_codex_hook_payload(
                payload={"hook_event_name": "UserPromptSubmit", "cwd": "/tmp/project"},
                config=config,
            )

            confirmed = store.require_question(question.question_id)
            self.assertEqual(confirmed.status, "delivery_confirmed")
            self.assertIsNotNone(confirmed.delivery_confirmed_at)

    def test_invalid_json_is_fail_open_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db")

            exit_code = run_from_stdin(config=config, stdin_text="{", quiet=True)

            self.assertEqual(exit_code, 0)

    def test_invalid_json_can_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db")

            exit_code = run_from_stdin(
                config=config,
                stdin_text="{",
                quiet=True,
                fail_closed=True,
            )

            self.assertEqual(exit_code, 1)

    def test_auto_start_can_create_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db", auto_start=True)
            payload = json.dumps({"hook_event_name": "SessionStart", "cwd": "/tmp/project"})

            exit_code = run_from_stdin(config=config, stdin_text=payload, quiet=True)

            self.assertEqual(exit_code, 0)
            workers = PresenceStore(config.db_path).list_workers()
            self.assertEqual(len(workers), 1)
            self.assertEqual(workers[0].worker_id, "test-computer:codex")
            self.assertEqual(workers[0].status, "active")

    def test_project_scope_separates_same_ai_between_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp) / "presence.db")
            config = replace(config, codex_worker_scope="project")

            first = build_observation(
                {"hook_event_name": "PostToolUse", "cwd": "/tmp/project-a"},
                config,
            )
            second = build_observation(
                {"hook_event_name": "PostToolUse", "cwd": "/tmp/project-b"},
                config,
            )

            self.assertNotEqual(first.worker_id, second.worker_id)
            self.assertIn(":project=project-a-", first.worker_id)
            self.assertIn(":project=project-b-", second.worker_id)

    def test_manual_cli_and_hook_derive_same_project_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            config = replace(
                make_config(Path(tmp) / "presence.db"),
                codex_worker_scope="project",
            )
            args = Namespace(
                worker=None,
                computer=None,
                ai="codex",
                protocol="protocol2",
                scope=None,
                project=project,
                session=None,
            )

            manual_worker, _, _, _ = _identity(args, config)
            observation = build_observation(
                {"hook_event_name": "PostToolUse", "cwd": str(project)},
                config,
            )

            self.assertEqual(manual_worker, observation.worker_id)


if __name__ == "__main__":
    unittest.main()
