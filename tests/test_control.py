from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from test_cli import make_config

from ai_presence_monitor.control import ControlError, ControlSettings, ControlStore


class ControlStoreTests(unittest.TestCase):
    def test_missing_file_uses_config_defaults_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            store = ControlStore.from_config(config)

            settings = store.load()

            self.assertFalse(settings.task_automation_enabled)
            self.assertTrue(settings.native_input_enabled)
            self.assertFalse(settings.scheduled_prompt_enabled)
            self.assertEqual(settings.scheduled_prompt_delay_minutes, 210)
            self.assertEqual(settings.scheduled_prompt_text, "continue")
            self.assertFalse(store.path.exists())

    def test_save_is_atomic_restricted_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config" / "control.json"
            store = ControlStore(path, ControlSettings())
            settings = ControlSettings(
                task_automation_enabled=True,
                native_input_enabled=True,
                gui_fallback_enabled=True,
                remote_input_enabled=True,
                sync_activity_enabled=False,
                codex_thread_id="thread-1",
                codex_remote="wss://client.example/app-server",
                remote_auth_token_env="CODEX_REMOTE_TOKEN",
                scheduled_prompt_enabled=True,
                scheduled_prompt_delay_minutes=210,
                scheduled_prompt_text="continue",
                scheduled_prompt_thread_id="thread-1",
                scheduled_prompt_due_at=13_600.0,
                scheduled_prompt_id="schedule-1",
                scheduled_prompt_last_state="armed",
            )

            store.save(settings)

            self.assertEqual(store.load(), settings)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)
            self.assertNotIn("token", payload)

    def test_legacy_control_file_receives_scheduled_prompt_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "settings": {
                            "task_automation_enabled": True,
                            "native_input_enabled": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            settings = ControlStore(path, ControlSettings()).load()

            self.assertTrue(settings.task_automation_enabled)
            self.assertFalse(settings.scheduled_prompt_enabled)
            self.assertEqual(settings.scheduled_prompt_delay_minutes, 210)
            self.assertEqual(settings.scheduled_prompt_text, "continue")

    def test_controls_and_target_are_immutable_updates(self) -> None:
        settings = ControlSettings()

        enabled = settings.with_control("task-automation", True)
        targeted = enabled.with_target(
            thread_id=" session ",
            remote=" wss://client ",
            remote_auth_token_env=" TOKEN_ENV ",
        )

        self.assertFalse(settings.task_automation_enabled)
        self.assertTrue(enabled.task_automation_enabled)
        self.assertEqual(targeted.codex_thread_id, "session")
        self.assertEqual(targeted.codex_remote, "wss://client")
        self.assertEqual(targeted.remote_auth_token_env, "TOKEN_ENV")
        with self.assertRaisesRegex(ControlError, "desconhecido"):
            settings.with_control("invalid", True)

    def test_invalid_json_and_types_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.json"
            store = ControlStore(path, ControlSettings())
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ControlError, "Nao foi possivel ler"):
                store.load()

            path.write_text(
                json.dumps({"settings": {"native_input_enabled": "yes"}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ControlError, "booleano"):
                store.load()

            path.write_text(
                json.dumps(
                    {
                        "settings": {
                            "scheduled_prompt_enabled": True,
                            "scheduled_prompt_thread_id": "thread",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ControlError, "vencimento"):
                store.load()

            with self.assertRaisesRegex(ControlError, "entrada nativa"):
                store.save(
                    ControlSettings(
                        native_input_enabled=False,
                        scheduled_prompt_enabled=True,
                        scheduled_prompt_thread_id="thread",
                        scheduled_prompt_due_at=100.0,
                        scheduled_prompt_id="schedule",
                        scheduled_prompt_last_state="armed",
                    )
                )

            with self.assertRaisesRegex(ControlError, "texto"):
                store.save(replace(ControlSettings(), scheduled_prompt_text=" "))

    def test_write_failure_is_reported_as_control_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.json"
            store = ControlStore(path, ControlSettings())
            with patch(
                "ai_presence_monitor.control.os.replace",
                side_effect=OSError("denied"),
            ), self.assertRaisesRegex(ControlError, "Nao foi possivel gravar"):
                store.save(ControlSettings())

            self.assertFalse(path.exists())

    @unittest.skipIf(os.name == "nt", "POSIX mode assertion is Linux-specific")
    def test_parent_directory_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private" / "control.json"
            ControlStore(path, ControlSettings()).save(ControlSettings())
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    @unittest.skipIf(os.name == "nt", "POSIX mode assertion is Linux-specific")
    def test_existing_parent_permissions_are_not_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "existing"
            parent.mkdir(mode=0o755)
            parent.chmod(0o755)

            ControlStore(
                parent / "control.json",
                ControlSettings(),
            ).save(ControlSettings())

            self.assertEqual(parent.stat().st_mode & 0o777, 0o755)


if __name__ == "__main__":
    unittest.main()
