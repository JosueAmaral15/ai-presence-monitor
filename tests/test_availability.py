from __future__ import annotations

import unittest
from unittest.mock import patch

from ai_presence_monitor.availability import (
    CodexAvailabilityProvider,
    DefaultAvailabilityProviderFactory,
    UnsupportedAvailabilityProvider,
)
from ai_presence_monitor.codex_app_server import (
    CodexAppServerError,
    RateLimitSnapshot,
    RateLimitWindowSnapshot,
    ThreadSnapshot,
)


def snapshot(
    *,
    allowed: bool | None,
    primary: int | None,
    secondary: int | None,
) -> RateLimitSnapshot:
    return RateLimitSnapshot(
        ordinary_usage_allowed=allowed,
        reached_type=None,
        plan_type="plus",
        primary=RateLimitWindowSnapshot(primary, None, 300),
        secondary=RateLimitWindowSnapshot(secondary, None, 10_080),
        has_credits=False,
        unlimited_credits=False,
        spend_control_reached=False,
    )


class AvailabilityProviderTests(unittest.TestCase):
    def test_codex_prefers_account_level_availability(self) -> None:
        provider = CodexAvailabilityProvider()

        self.assertEqual(
            provider.classify(snapshot(allowed=True, primary=100, secondary=100)),
            "available",
        )
        self.assertEqual(
            provider.classify(snapshot(allowed=False, primary=0, secondary=0)),
            "unavailable",
        )

    def test_codex_fallback_fails_closed_for_partial_window_data(self) -> None:
        provider = CodexAvailabilityProvider()

        self.assertEqual(
            provider.classify(snapshot(allowed=None, primary=10, secondary=None)),
            "unknown",
        )
        self.assertEqual(
            provider.classify(snapshot(allowed=None, primary=100, secondary=None)),
            "unavailable",
        )

    def test_factory_rejects_uninstalled_provider(self) -> None:
        factory = DefaultAvailabilityProviderFactory()

        self.assertEqual(factory.create("codex").provider_id, "codex")
        with self.assertRaises(UnsupportedAvailabilityProvider):
            factory.create("gemini")

    def test_exact_session_validation_is_read_only_and_fail_closed(self) -> None:
        provider = CodexAvailabilityProvider()
        with patch(
            "ai_presence_monitor.availability.read_codex_thread",
            return_value=ThreadSnapshot("session-1", "idle", ()),
        ):
            self.assertEqual(provider.validate_session("session-1"), "available")
        with patch(
            "ai_presence_monitor.availability.read_codex_thread",
            side_effect=CodexAppServerError("missing"),
        ):
            self.assertEqual(provider.validate_session("session-1"), "unknown")


if __name__ == "__main__":
    unittest.main()
