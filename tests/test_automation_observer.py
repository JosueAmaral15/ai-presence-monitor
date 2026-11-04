from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from ai_presence_monitor.automation_observer import observe_automations_once
from ai_presence_monitor.codex_app_server import (
    RateLimitSnapshot,
    RateLimitWindowSnapshot,
)
from ai_presence_monitor.codex_input import CodexInputResult
from ai_presence_monitor.control import ControlSettings, ControlStore
from ai_presence_monitor.prompt_rules import (
    configure_prompt_rule,
    replace_prompt_rules,
)
from ai_presence_monitor.quota_recovery import (
    configure_quota_recovery_rule,
    replace_quota_recovery_rules,
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
        return CodexInputResult(thread_id, remote, "dispatch_started")


class AutomationObserverTests(unittest.TestCase):
    def test_one_account_read_drives_prompt_and_quota_observers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controls = ControlStore(root / "control.json", ControlSettings())
            presence = PresenceStore(root / "presence.db")
            presence.record_event(
                worker_id="worker-1",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            prompt = configure_prompt_rule(
                None,
                enabled=True,
                thread_id="session-prompt",
                trigger="after_delay",
                delay_minutes=1,
                text="prompt recovery",
                require_usage_available=True,
                repeat_enabled=False,
                repeat_interval_minutes=1,
                now=1_000.0,
            )
            quota = configure_quota_recovery_rule(
                None,
                window="five_hour",
                enabled=True,
                thread_id="session-quota",
                text="quota recovery",
            )
            quota = replace(
                quota,
                last_state="waiting_for_availability",
                exhausted_observed_at=900.0,
            )
            settings = ControlSettings(
                task_automation_enabled=True,
                native_input_enabled=True,
            )
            settings = replace_prompt_rules(settings, [prompt])
            settings = replace_quota_recovery_rules(settings, [quota])
            controls.save(settings, "worker-1")
            reads = 0

            def reader(**_: object) -> RateLimitSnapshot:
                nonlocal reads
                reads += 1
                return RateLimitSnapshot(
                    ordinary_usage_allowed=True,
                    reached_type=None,
                    plan_type="plus",
                    primary=RateLimitWindowSnapshot(0, 2_000, 300),
                    secondary=RateLimitWindowSnapshot(50, 3_000, 10_080),
                    has_credits=False,
                    unlimited_credits=False,
                    spend_control_reached=False,
                )

            client = FakeClient()
            result = observe_automations_once(
                control_store=controls,
                presence_store=presence,
                evidence_ttl_seconds=600,
                now=1_060.0,
                reader=reader,
                client=client,  # type: ignore[arg-type]
            )

            self.assertEqual(reads, 1)
            self.assertEqual(
                result.prompt_rules.rule_results[0].state,
                "dispatch_started",
            )
            self.assertEqual(
                result.quota_recovery.rule_results[0].state,
                "dispatch_started",
            )
            self.assertEqual(
                client.calls,
                [
                    ("session-prompt", "prompt recovery"),
                    ("session-quota", "quota recovery"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
