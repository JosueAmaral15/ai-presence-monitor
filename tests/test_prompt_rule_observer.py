from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.codex_evidence import CodexLimitObservation
from ai_presence_monitor.codex_input import CodexInputResult
from ai_presence_monitor.control import ControlSettings, ControlStore
from ai_presence_monitor.prompt_rule_observer import (
    due_usage_rule_targets,
    observe_prompt_rules_once,
)
from ai_presence_monitor.prompt_rules import (
    configure_prompt_rule,
    process_prompt_rules,
    replace_prompt_rules,
)
from ai_presence_monitor.store import PresenceStore


class FakeClient:
    def __init__(self) -> None:
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
        return CodexInputResult(
            thread_id=thread_id, remote=remote, state="dispatch_started"
        )


class PromptRuleObserverTests(unittest.TestCase):
    def test_52_minute_usage_rule_requires_observer_then_dispatches_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controls = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            with patch("ai_presence_monitor.store.time.time", return_value=900.0):
                presence.record_event(
                    worker_id="worker-52",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="start",
                )
                presence.record_event(
                    worker_id="worker-52",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="finish",
                )
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-52",
                trigger="after_delay",
                delay_minutes=52,
                text="continue after usage recovery",
                require_usage_available=True,
                repeat_enabled=False,
                repeat_interval_minutes=52,
                now=1_000.0,
                rule_id="reported-52-minute-rule",
            )
            controls.save(
                replace_prompt_rules(
                    ControlSettings(
                        task_automation_enabled=True,
                        native_input_enabled=True,
                    ),
                    [rule],
                ),
                "worker-52",
            )
            client = FakeClient()

            tray_result = process_prompt_rules(
                store=controls,
                profile_id="worker-52",
                presence_store=presence,
                now=4_120.0,
                client=client,  # type: ignore[arg-type]
                usage_gated_only=False,
            )
            observer_result = observe_prompt_rules_once(
                control_store=controls,
                presence_store=presence,
                evidence_ttl_seconds=600,
                now=4_120.0,
                collector=lambda **_: CodexLimitObservation(
                    "usage_available", "available", 4_120.0, 4_720.0
                ),
                client=client,  # type: ignore[arg-type]
            )
            second_cycle = observe_prompt_rules_once(
                control_store=controls,
                presence_store=presence,
                evidence_ttl_seconds=600,
                now=4_121.0,
                collector=lambda **_: CodexLimitObservation(
                    "usage_available", "available", 4_121.0, 4_721.0
                ),
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(tray_result.state, "disabled")
            self.assertEqual(observer_result.rule_results[0].state, "dispatch_started")
            self.assertEqual(second_cycle.targets, ())
            self.assertEqual(
                client.calls,
                [("session-52", "continue after usage recovery")],
            )

    def test_inactive_worker_resumes_when_usage_becomes_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controls = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            with patch("ai_presence_monitor.store.time.time", return_value=900.0):
                presence.record_event(
                    worker_id="worker-1",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="start",
                    task="task",
                )
                presence.record_event(
                    worker_id="worker-1",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="finish",
                )
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-1",
                trigger="after_delay",
                delay_minutes=1,
                text="continue",
                require_usage_available=True,
                repeat_enabled=False,
                repeat_interval_minutes=1,
                now=1_000.0,
                rule_id="usage-recovery",
            )
            controls.save(
                replace_prompt_rules(
                    ControlSettings(
                        task_automation_enabled=True,
                        native_input_enabled=True,
                    ),
                    [rule],
                ),
                "worker-1",
            )
            client = FakeClient()

            blocked = observe_prompt_rules_once(
                control_store=controls,
                presence_store=presence,
                evidence_ttl_seconds=600,
                now=1_060.0,
                collector=lambda **_: CodexLimitObservation(
                    "rate_limit_reached", "blocked", 1_060.0, 1_660.0
                ),
                client=client,  # type: ignore[arg-type]
            )
            available = observe_prompt_rules_once(
                control_store=controls,
                presence_store=presence,
                evidence_ttl_seconds=600,
                now=1_360.0,
                collector=lambda **_: CodexLimitObservation(
                    "usage_available", "available", 1_360.0, 1_960.0
                ),
                client=client,  # type: ignore[arg-type]
            )

            worker = presence.get_worker("worker-1")
            self.assertIsNotNone(worker)
            assert worker is not None
            self.assertEqual(worker.status, "idle")
            self.assertEqual(blocked.rule_results[0].state, "waiting_for_usage")
            self.assertEqual(available.rule_results[0].state, "dispatch_started")
            self.assertEqual(client.calls, [("session-1", "continue")])
            self.assertFalse(controls.load("worker-1").prompt_rules[0].enabled)

    def test_only_due_enabled_usage_rules_are_observed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controls = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            with patch("ai_presence_monitor.store.time.time", return_value=900.0):
                presence.record_event(
                    worker_id="worker-1",
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    event_type="start",
                )
            rule = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-1",
                trigger="after_delay",
                delay_minutes=5,
                text="continue",
                require_usage_available=True,
                repeat_enabled=False,
                repeat_interval_minutes=5,
                now=1_000.0,
            )
            controls.save(
                replace_prompt_rules(
                    replace(ControlSettings(), task_automation_enabled=True),
                    [rule],
                ),
                "worker-1",
            )

            self.assertEqual(
                due_usage_rule_targets(
                    control_store=controls,
                    presence_store=presence,
                    now=1_299.0,
                ),
                (),
            )
            self.assertEqual(
                due_usage_rule_targets(
                    control_store=controls,
                    presence_store=presence,
                    now=1_300.0,
                )[0].session_id,
                "session-1",
            )


if __name__ == "__main__":
    unittest.main()
