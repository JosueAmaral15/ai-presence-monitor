from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from ai_presence_monitor.codex_app_server import (
    RateLimitSnapshot,
    RateLimitWindowSnapshot,
)
from ai_presence_monitor.codex_input import CodexInputError, CodexInputResult
from ai_presence_monitor.control import ControlSettings, ControlStore
from ai_presence_monitor.quota_recovery import (
    classify_quota_windows,
    configure_quota_recovery_rule,
    observe_quota_recovery_once,
    replace_quota_recovery_rules,
)
from ai_presence_monitor.store import PresenceStore


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


def snapshot(
    *,
    five_hour: int | None,
    weekly: int | None,
    reverse: bool = False,
) -> RateLimitSnapshot:
    five = RateLimitWindowSnapshot(five_hour, 10_000, 300)
    week = RateLimitWindowSnapshot(weekly, 20_000, 10_080)
    primary, secondary = (week, five) if reverse else (five, week)
    return RateLimitSnapshot(
        ordinary_usage_allowed=True,
        reached_type=None,
        plan_type="plus",
        primary=primary,
        secondary=secondary,
        has_credits=False,
        unlimited_credits=False,
        spend_control_reached=False,
    )


class QuotaRecoveryTests(unittest.TestCase):
    def make_stores(self, root: Path) -> tuple[ControlStore, PresenceStore]:
        controls = ControlStore(root / "control.json", ControlSettings())
        presence = PresenceStore(root / "presence.db")
        presence.record_event(
            worker_id="worker-1",
            computer="computer",
            ia_name="codex",
            protocol="protocol2",
            event_type="start",
        )
        return controls, presence

    def test_classifies_windows_by_duration_not_position(self) -> None:
        states = classify_quota_windows(
            snapshot(five_hour=100, weekly=42, reverse=True)
        )

        self.assertEqual(states, {"five_hour": "exhausted", "weekly": "available"})

    def test_initial_availability_never_dispatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controls, presence = self.make_stores(Path(tmp))
            rule = configure_quota_recovery_rule(
                None,
                window="five_hour",
                enabled=True,
                thread_id="session-1",
                text="resume five-hour work",
            )
            controls.save(
                replace_quota_recovery_rules(
                    ControlSettings(
                        task_automation_enabled=True,
                        native_input_enabled=True,
                    ),
                    [rule],
                ),
                "worker-1",
            )
            client = FakeClient()

            result = observe_quota_recovery_once(
                control_store=controls,
                presence_store=presence,
                now=1_000.0,
                reader=lambda **_: snapshot(five_hour=20, weekly=30),
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(result.rule_results[0].state, "armed")
            self.assertEqual(client.calls, [])

    def test_exhausted_to_available_dispatches_once_then_rearms_next_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controls, presence = self.make_stores(Path(tmp))
            rule = configure_quota_recovery_rule(
                None,
                window="weekly",
                enabled=True,
                thread_id="session-weekly",
                text="resume weekly work",
            )
            controls.save(
                replace_quota_recovery_rules(
                    ControlSettings(
                        task_automation_enabled=True,
                        native_input_enabled=True,
                    ),
                    [rule],
                ),
                "worker-1",
            )
            client = FakeClient()

            blocked = observe_quota_recovery_once(
                control_store=controls,
                presence_store=presence,
                now=1_000.0,
                reader=lambda **_: snapshot(five_hour=10, weekly=100),
                client=client,  # type: ignore[arg-type]
            )
            available = observe_quota_recovery_once(
                control_store=controls,
                presence_store=presence,
                now=2_000.0,
                reader=lambda **_: snapshot(five_hour=10, weekly=0),
                client=client,  # type: ignore[arg-type]
            )
            repeated = observe_quota_recovery_once(
                control_store=controls,
                presence_store=presence,
                now=2_100.0,
                reader=lambda **_: snapshot(five_hour=10, weekly=0),
                client=client,  # type: ignore[arg-type]
            )
            rearmed = observe_quota_recovery_once(
                control_store=controls,
                presence_store=presence,
                now=3_000.0,
                reader=lambda **_: snapshot(five_hour=10, weekly=100),
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(blocked.rule_results[0].state, "waiting_for_availability")
            self.assertEqual(available.rule_results[0].state, "dispatch_started")
            self.assertEqual(repeated.rule_results[0].state, "armed")
            self.assertEqual(rearmed.rule_results[0].state, "waiting_for_availability")
            self.assertEqual(client.calls, [("session-weekly", "resume weekly work")])

    def test_uncertain_dispatch_is_not_retried_until_new_exhaustion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controls, presence = self.make_stores(Path(tmp))
            rule = configure_quota_recovery_rule(
                None,
                window="five_hour",
                enabled=True,
                thread_id="session-1",
                text="resume",
            )
            rule = replace(rule, last_state="waiting_for_availability")
            controls.save(
                replace_quota_recovery_rules(
                    ControlSettings(
                        task_automation_enabled=True,
                        native_input_enabled=True,
                    ),
                    [rule],
                ),
                "worker-1",
            )
            client = FakeClient(fail=True)

            failed = observe_quota_recovery_once(
                control_store=controls,
                presence_store=presence,
                now=2_000.0,
                reader=lambda **_: snapshot(five_hour=0, weekly=0),
                client=client,  # type: ignore[arg-type]
            )
            repeated = observe_quota_recovery_once(
                control_store=controls,
                presence_store=presence,
                now=2_100.0,
                reader=lambda **_: snapshot(five_hour=0, weekly=0),
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(failed.rule_results[0].state, "failed_or_uncertain")
            self.assertEqual(repeated.rule_results[0].state, "armed")
            self.assertEqual(len(client.calls), 1)

    def test_profile_settings_remain_isolated_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.json"
            controls = ControlStore(path, ControlSettings())
            rule = configure_quota_recovery_rule(
                None,
                window="five_hour",
                enabled=True,
                thread_id="session-a",
                text="resume a",
            )
            controls.save(
                replace_quota_recovery_rules(
                    ControlSettings(native_input_enabled=True),
                    [rule],
                ),
                "worker-a",
            )

            reopened = ControlStore(path, ControlSettings())

            self.assertEqual(
                reopened.load("worker-a").quota_recovery_rules[0],
                rule,
            )
            self.assertEqual(reopened.load("worker-b").quota_recovery_rules, ())


if __name__ == "__main__":
    unittest.main()
