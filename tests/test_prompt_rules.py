from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.codex_input import CodexInputError, CodexInputResult
from ai_presence_monitor.control import ControlSettings, ControlStore
from ai_presence_monitor.prompt_rules import (
    configure_prompt_rule,
    disable_all_prompt_rules,
    process_prompt_rules,
    replace_prompt_rules,
)
from ai_presence_monitor.store import PresenceStore


class FakeClient:
    def __init__(self, *, fail: bool = False):
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


def configured_settings(*rules: object) -> ControlSettings:
    return replace_prompt_rules(
        ControlSettings(
            task_automation_enabled=True,
            native_input_enabled=True,
        ),
        list(rules),  # type: ignore[arg-type]
    )


class PromptRuleTests(unittest.TestCase):
    def test_disable_all_rules_preserves_configuration_and_clears_runtime(self) -> None:
        rule = configure_prompt_rule(
            None,
            enabled=True,
            thread_id="session-1",
            trigger="red_inactivity",
            delay_minutes=270,
            text="proceed",
            repeat_enabled=True,
            repeat_interval_minutes=30,
            max_occurrences=5,
            now=1_000.0,
            rule_id="rule-1",
        )
        rule = replace(
            rule,
            occurrence_count=2,
            next_due_at=2_000.0,
            last_state="waiting_for_confirmation",
            last_attempt_at=1_500.0,
            last_dispatch_at=1_500.0,
            awaiting_confirmation=True,
        )
        settings = configured_settings(rule)

        disabled = disable_all_prompt_rules(settings)
        saved = disabled.prompt_rules[0]

        self.assertTrue(disabled.task_automation_enabled)
        self.assertFalse(saved.enabled)
        self.assertEqual(saved.rule_id, "rule-1")
        self.assertEqual(saved.thread_id, "session-1")
        self.assertEqual(saved.trigger, "red_inactivity")
        self.assertEqual(saved.delay_minutes, 270)
        self.assertEqual(saved.text, "proceed")
        self.assertTrue(saved.repeat_enabled)
        self.assertEqual(saved.repeat_interval_minutes, 30)
        self.assertEqual(saved.max_occurrences, 5)
        self.assertEqual(saved.occurrence_count, 0)
        self.assertIsNone(saved.armed_at)
        self.assertIsNone(saved.next_due_at)
        self.assertEqual(saved.last_state, "disabled")
        self.assertIsNone(saved.last_attempt_at)
        self.assertIsNone(saved.last_dispatch_at)
        self.assertFalse(saved.awaiting_confirmation)

    def test_reenable_and_configuration_changes_restart_the_cycle(self) -> None:
        base = configure_prompt_rule(
            None,
            enabled=True,
            thread_id="session-1",
            trigger="after_delay",
            delay_minutes=210,
            text="continue",
            repeat_enabled=False,
            repeat_interval_minutes=210,
            max_occurrences=3,
            now=1_000.0,
            rule_id="rule-1",
        )
        completed = replace(
            base,
            enabled=False,
            occurrence_count=1,
            next_due_at=None,
            last_state="failed_or_uncertain",
            last_attempt_at=2_000.0,
            last_dispatch_at=1_500.0,
        )
        unchanged = configure_prompt_rule(
            base,
            enabled=True,
            thread_id="session-1",
            trigger="after_delay",
            delay_minutes=210,
            text="continue",
            repeat_enabled=False,
            repeat_interval_minutes=210,
            max_occurrences=3,
            now=9_000.0,
        )

        reenabled = configure_prompt_rule(
            completed,
            enabled=True,
            thread_id="session-1",
            trigger="after_delay",
            delay_minutes=210,
            text="continue",
            repeat_enabled=False,
            repeat_interval_minutes=210,
            max_occurrences=3,
            now=3_000.0,
        )

        self.assertIs(unchanged, base)
        self.assertEqual(reenabled.rule_id, "rule-1")
        self.assertTrue(reenabled.enabled)
        self.assertEqual(reenabled.armed_at, 3_000.0)
        self.assertEqual(reenabled.next_due_at, 15_600.0)
        self.assertEqual(reenabled.occurrence_count, 0)
        self.assertEqual(reenabled.last_state, "armed")
        self.assertIsNone(reenabled.last_attempt_at)
        self.assertIsNone(reenabled.last_dispatch_at)
        self.assertFalse(reenabled.awaiting_confirmation)

        changes = (
            {"thread_id": "session-2"},
            {"trigger": "red_inactivity"},
            {"delay_minutes": 270},
            {"text": "proceed"},
            {"repeat_enabled": True},
            {"repeat_interval_minutes": 270},
            {"max_occurrences": 4},
        )
        for change in changes:
            with self.subTest(change=change):
                configuration = {
                    "enabled": True,
                    "thread_id": "session-1",
                    "trigger": "after_delay",
                    "delay_minutes": 210,
                    "text": "continue",
                    "repeat_enabled": False,
                    "repeat_interval_minutes": 210,
                    "max_occurrences": 3,
                }
                configuration.update(change)
                changed = configure_prompt_rule(
                    replace(
                        base,
                        occurrence_count=2,
                        last_state="dispatch_started",
                        last_attempt_at=1_500.0,
                        last_dispatch_at=1_500.0,
                    ),
                    **configuration,
                    now=4_000.0,
                )
                self.assertEqual(changed.armed_at, 4_000.0)
                self.assertEqual(changed.occurrence_count, 0)
                self.assertIsNone(changed.last_attempt_at)
                self.assertIsNone(changed.last_dispatch_at)
                self.assertFalse(changed.awaiting_confirmation)

    def test_red_rule_rearm_does_not_reuse_an_old_red_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            with patch("ai_presence_monitor.store.time.time", return_value=1_000.0):
                presence.record_event(
                    worker_id="worker-1",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="start",
                    task="task",
                )
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-1",
                trigger="red_inactivity",
                delay_minutes=1,
                text="continue",
                repeat_enabled=False,
                repeat_interval_minutes=1,
                now=3_000.0,
                rule_id="red-rule",
            )
            control.save(configured_settings(rule), "worker-1")
            client = FakeClient()

            rearmed = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=3_000.0,
                client=client,  # type: ignore[arg-type]
            )
            sent = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=3_060.0,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(rearmed.state, "waiting")
            self.assertEqual(rearmed.due_at, 3_060.0)
            self.assertEqual(sent.state, "dispatch_started")
            self.assertEqual(client.calls, [("session-1", "continue")])

    def test_red_rule_cancels_initial_due_time_after_new_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            with patch("ai_presence_monitor.store.time.time", return_value=1_000.0):
                presence.record_event(
                    worker_id="worker-1",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="start",
                    task="task",
                )
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-1",
                trigger="red_inactivity",
                delay_minutes=1,
                text="continue",
                repeat_enabled=False,
                repeat_interval_minutes=1,
                now=1_000.0,
                rule_id="red-rule",
            )
            control.save(configured_settings(rule), "worker-1")
            client = FakeClient()

            armed = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=1_900.0,
                client=client,  # type: ignore[arg-type]
            )
            with patch("ai_presence_monitor.store.time.time", return_value=1_920.0):
                presence.record_event(
                    worker_id="worker-1",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="observation:codex:after_agent",
                    message="codex hook after_agent session=session-1",
                    task="task",
                )
            reset = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=1_950.0,
                client=client,  # type: ignore[arg-type]
            )
            reset_rule = control.load("worker-1").prompt_rules[0]
            rearmed = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=2_820.0,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(armed.state, "waiting")
            self.assertEqual(armed.due_at, 1_960.0)
            self.assertEqual(reset.state, "waiting_for_event")
            self.assertIsNone(reset_rule.next_due_at)
            self.assertEqual(reset_rule.last_state, "waiting_for_event")
            self.assertEqual(rearmed.state, "waiting")
            self.assertEqual(rearmed.due_at, 2_880.0)
            self.assertEqual(client.calls, [])

    def test_one_shot_dispatches_once_and_persists_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-1",
                trigger="after_delay",
                delay_minutes=1,
                text="continue",
                repeat_enabled=False,
                repeat_interval_minutes=5,
                max_occurrences=3,
                now=1_000.0,
                rule_id="rule-1",
            )
            control.save(configured_settings(rule), "worker-1")
            client = FakeClient()

            waiting = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=1_059.0,
                client=client,  # type: ignore[arg-type]
            )
            sent = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=1_060.0,
                client=client,  # type: ignore[arg-type]
            )
            repeated = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=2_000.0,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(waiting.state, "waiting")
            self.assertEqual(sent.state, "dispatch_started")
            self.assertEqual(repeated.state, "disabled")
            self.assertEqual(client.calls, [("session-1", "continue")])
            saved = control.load("worker-1").prompt_rules[0]
            self.assertFalse(saved.enabled)
            self.assertEqual(saved.occurrence_count, 1)
            self.assertEqual(saved.repeat_interval_minutes, 5)
            self.assertEqual(saved.max_occurrences, 3)

    def test_repetition_waits_for_exact_session_hook_and_stops_at_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            session_id = "11111111-1111-4111-8111-111111111111"
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id=session_id,
                trigger="after_delay",
                delay_minutes=1,
                text="continue",
                repeat_enabled=True,
                repeat_interval_minutes=1,
                max_occurrences=2,
                now=1_000.0,
                rule_id="rule-1",
            )
            control.save(configured_settings(rule), "worker-1")
            client = FakeClient()

            first = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=1_060.0,
                client=client,  # type: ignore[arg-type]
            )
            no_hook = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=2_000.0,
                client=client,  # type: ignore[arg-type]
            )
            with patch("ai_presence_monitor.store.time.time", return_value=2_010.0):
                presence.record_event(
                    worker_id="worker-1",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="observation:codex:after_agent",
                    message=f"codex hook after_agent session={session_id}",
                    task="task",
                )
            rearmed = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=2_069.0,
                client=client,  # type: ignore[arg-type]
            )
            second = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=2_070.0,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(first.state, "dispatch_started")
            self.assertEqual(no_hook.state, "waiting_for_confirmation")
            self.assertEqual(rearmed.state, "waiting")
            self.assertEqual(second.state, "dispatch_started")
            self.assertEqual(len(client.calls), 2)
            saved = control.load("worker-1").prompt_rules[0]
            self.assertFalse(saved.enabled)
            self.assertEqual(saved.occurrence_count, 2)

    def test_red_trigger_uses_protocol_event_then_configured_delay(self) -> None:
        cases = (("protocol1", 2_800.0), ("protocol2", 1_900.0))
        for protocol, red_at in cases:
            with self.subTest(protocol=protocol), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                control = ControlStore(root / "control.json", ControlSettings())
                presence = PresenceStore(root / "presence.db")
                worker_id = f"worker-{protocol}"
                with patch("ai_presence_monitor.store.time.time", return_value=1_000.0):
                    presence.record_event(
                        worker_id=worker_id,
                        computer="computer",
                        ia_name="codex",
                        protocol=protocol,
                        event_type="start",
                        task="task",
                    )
                rule = configure_prompt_rule(
                    None,
                    enabled=True,
                    thread_id="session-1",
                    trigger="red_inactivity",
                    delay_minutes=1,
                    text="continue",
                    repeat_enabled=False,
                    repeat_interval_minutes=1,
                    now=1_000.0,
                    rule_id="red-rule",
                )
                control.save(configured_settings(rule), worker_id)
                client = FakeClient()

                before = process_prompt_rules(
                    store=control,
                    profile_id=worker_id,
                    presence_store=presence,
                    now=red_at - 1,
                    client=client,  # type: ignore[arg-type]
                )
                delayed = process_prompt_rules(
                    store=control,
                    profile_id=worker_id,
                    presence_store=presence,
                    now=red_at,
                    client=client,  # type: ignore[arg-type]
                )
                sent = process_prompt_rules(
                    store=control,
                    profile_id=worker_id,
                    presence_store=presence,
                    now=red_at + 60,
                    client=client,  # type: ignore[arg-type]
                )

                self.assertEqual(before.state, "waiting_for_event")
                self.assertEqual(delayed.state, "waiting")
                self.assertEqual(sent.state, "dispatch_started")
                self.assertEqual(len(client.calls), 1)

    def test_failure_disables_rule_and_multiple_rules_dispatch_one_per_poll(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            rules = [
                configure_prompt_rule(
                    None,
                    enabled=True,
                    thread_id=f"session-{index}",
                    trigger="after_delay",
                    delay_minutes=1,
                    text=f"message-{index}",
                    repeat_enabled=False,
                    repeat_interval_minutes=1,
                    now=1_000.0,
                    rule_id=f"rule-{index}",
                )
                for index in (1, 2)
            ]
            control.save(configured_settings(*rules), "worker-1")
            failed_client = FakeClient(fail=True)

            failed = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=1_060.0,
                client=failed_client,  # type: ignore[arg-type]
            )

            self.assertEqual(failed.state, "failed_or_uncertain")
            self.assertEqual(len(failed_client.calls), 1)
            self.assertFalse(control.load("worker-1").prompt_rules[0].enabled)
            self.assertTrue(control.load("worker-1").prompt_rules[1].enabled)

            client = FakeClient()
            sent = process_prompt_rules(
                store=control,
                profile_id="worker-1",
                presence_store=presence,
                now=1_061.0,
                client=client,  # type: ignore[arg-type]
            )
            self.assertEqual(sent.rule_id, "rule-2")
            self.assertEqual(len(client.calls), 1)

    def test_profile_disable_and_profile_isolation_block_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-1",
                trigger="after_delay",
                delay_minutes=1,
                text="continue",
                repeat_enabled=False,
                repeat_interval_minutes=1,
                now=1_000.0,
                rule_id="rule-1",
            )
            disabled = replace(
                configured_settings(rule),
                task_automation_enabled=False,
            )
            control.save(disabled, "worker-disabled")
            control.save(configured_settings(rule), "worker-enabled")
            client = FakeClient()

            blocked = process_prompt_rules(
                store=control,
                profile_id="worker-disabled",
                presence_store=presence,
                now=2_000.0,
                client=client,  # type: ignore[arg-type]
            )
            sent = process_prompt_rules(
                store=control,
                profile_id="worker-enabled",
                presence_store=presence,
                now=2_000.0,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(blocked.state, "automation_disabled")
            self.assertEqual(sent.state, "dispatch_started")
            self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
