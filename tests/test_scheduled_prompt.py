from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_presence_monitor.codex_input import (
    CodexInputError,
    CodexInputResult,
)
from ai_presence_monitor.control import ControlError, ControlSettings, ControlStore
from ai_presence_monitor.scheduled_prompt import (
    configure_scheduled_prompt,
    process_due_scheduled_prompt,
)


class FakeClient:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[dict[str, object]] = []

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
                "detached": detached,
            }
        )
        if self.fail:
            raise CodexInputError("resultado incerto")
        return CodexInputResult(
            thread_id=thread_id,
            remote=remote,
            state="dispatch_started",
        )


class ScheduledPromptTests(unittest.TestCase):
    def test_defaults_arm_exact_session_for_210_minutes(self) -> None:
        armed = configure_scheduled_prompt(
            ControlSettings(native_input_enabled=True),
            enabled=True,
            delay_minutes=210,
            text=" continue ",
            thread_id=" session-1 ",
            now=1_000.0,
            schedule_id="schedule-1",
        )

        self.assertTrue(armed.scheduled_prompt_enabled)
        self.assertEqual(armed.scheduled_prompt_delay_minutes, 210)
        self.assertEqual(armed.scheduled_prompt_text, "continue")
        self.assertEqual(armed.scheduled_prompt_thread_id, "session-1")
        self.assertEqual(armed.scheduled_prompt_due_at, 13_600.0)
        self.assertEqual(armed.scheduled_prompt_id, "schedule-1")
        self.assertEqual(armed.scheduled_prompt_last_state, "armed")

    def test_unchanged_preferences_do_not_postpone_active_schedule(self) -> None:
        first = configure_scheduled_prompt(
            ControlSettings(native_input_enabled=True),
            enabled=True,
            delay_minutes=210,
            text="continue",
            thread_id="session-1",
            now=1_000.0,
            schedule_id="schedule-1",
        )

        repeated = configure_scheduled_prompt(
            first,
            enabled=True,
            delay_minutes=210,
            text="continue",
            thread_id="session-1",
            now=2_000.0,
            schedule_id="schedule-2",
        )

        self.assertEqual(repeated, first)

    def test_change_rearms_and_disable_cancels(self) -> None:
        first = configure_scheduled_prompt(
            ControlSettings(native_input_enabled=True),
            enabled=True,
            delay_minutes=210,
            text="continue",
            thread_id="session-1",
            now=1_000.0,
            schedule_id="schedule-1",
        )
        changed = configure_scheduled_prompt(
            first,
            enabled=True,
            delay_minutes=30,
            text="proceed",
            thread_id="session-2",
            now=2_000.0,
            schedule_id="schedule-2",
        )
        disabled = configure_scheduled_prompt(
            changed,
            enabled=False,
            delay_minutes=30,
            text="proceed",
            thread_id="session-2",
        )

        self.assertEqual(changed.scheduled_prompt_due_at, 3_800.0)
        self.assertEqual(changed.scheduled_prompt_id, "schedule-2")
        self.assertFalse(disabled.scheduled_prompt_enabled)
        self.assertIsNone(disabled.scheduled_prompt_thread_id)
        self.assertIsNone(disabled.scheduled_prompt_due_at)
        self.assertIsNone(disabled.scheduled_prompt_id)
        self.assertEqual(disabled.scheduled_prompt_text, "proceed")

    def test_arming_requires_native_input_session_delay_and_text(self) -> None:
        cases = (
            (
                ControlSettings(native_input_enabled=False),
                210,
                "continue",
                "session",
                "entrada nativa",
            ),
            (
                ControlSettings(native_input_enabled=True),
                210,
                "continue",
                None,
                "sessao",
            ),
            (
                ControlSettings(native_input_enabled=True),
                0,
                "continue",
                "session",
                "entre 1",
            ),
            (
                ControlSettings(native_input_enabled=True),
                210,
                " ",
                "session",
                "nao pode",
            ),
        )
        for settings, delay, text, thread, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                ControlError, message
            ):
                configure_scheduled_prompt(
                    settings,
                    enabled=True,
                    delay_minutes=delay,
                    text=text,
                    thread_id=thread,
                    now=1_000.0,
                )

    def test_due_prompt_is_claimed_before_one_detached_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ControlStore(Path(tmp) / "control.json", ControlSettings())
            store.save(
                configure_scheduled_prompt(
                    ControlSettings(native_input_enabled=True),
                    enabled=True,
                    delay_minutes=1,
                    text="continue",
                    thread_id="session-1",
                    now=1_000.0,
                    schedule_id="schedule-1",
                )
            )
            client = FakeClient()

            waiting = process_due_scheduled_prompt(
                store=store,
                now=1_059.0,
                client=client,  # type: ignore[arg-type]
            )
            sent = process_due_scheduled_prompt(
                store=store,
                now=1_060.0,
                client=client,  # type: ignore[arg-type]
            )
            repeated = process_due_scheduled_prompt(
                store=store,
                now=2_000.0,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(waiting.state, "waiting")
            self.assertEqual(sent.state, "dispatch_started")
            self.assertEqual(repeated.state, "disabled")
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(client.calls[0]["thread_id"], "session-1")
            self.assertEqual(client.calls[0]["text"], "continue")
            self.assertTrue(client.calls[0]["detached"])
            saved = store.load()
            self.assertFalse(saved.scheduled_prompt_enabled)
            self.assertEqual(saved.scheduled_prompt_last_state, "dispatch_started")

    def test_failed_or_uncertain_attempt_is_never_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ControlStore(Path(tmp) / "control.json", ControlSettings())
            store.save(
                configure_scheduled_prompt(
                    ControlSettings(native_input_enabled=True),
                    enabled=True,
                    delay_minutes=1,
                    text="continue",
                    thread_id="session-1",
                    now=1_000.0,
                    schedule_id="schedule-1",
                )
            )
            client = FakeClient(fail=True)

            failed = process_due_scheduled_prompt(
                store=store,
                now=1_060.0,
                client=client,  # type: ignore[arg-type]
            )
            repeated = process_due_scheduled_prompt(
                store=store,
                now=2_000.0,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(failed.state, "failed_or_uncertain")
            self.assertEqual(repeated.state, "disabled")
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(
                store.load().scheduled_prompt_last_state,
                "failed_or_uncertain",
            )


if __name__ == "__main__":
    unittest.main()
