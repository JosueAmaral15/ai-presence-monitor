from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai_presence_monitor.cli import _observe_codex_limits, build_parser
from ai_presence_monitor.codex_app_server import RateLimitSnapshot
from ai_presence_monitor.codex_evidence import (
    CodexLimitObservation,
    classify_rate_limits,
    collect_codex_limit_observation,
    record_codex_hook_evidence,
)
from ai_presence_monitor.diagnostics import (
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
)
from ai_presence_monitor.store import PresenceStore


def rate_limits(**overrides: object) -> RateLimitSnapshot:
    values: dict[str, object] = {
        "ordinary_usage_allowed": True,
        "reached_type": None,
        "plan_type": "plus",
        "primary": None,
        "secondary": None,
        "has_credits": False,
        "unlimited_credits": False,
        "spend_control_reached": False,
    }
    values.update(overrides)
    return RateLimitSnapshot(**values)  # type: ignore[arg-type]


class CodexEvidenceTests(unittest.TestCase):
    def test_recognized_hook_becomes_expiring_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"

            evidence = record_codex_hook_evidence(
                db_path=db_path,
                worker_id="worker-1",
                session_id="session-1",
                event_name="PostToolUse",
                observed_at=100,
                ttl_seconds=300,
            )

            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(evidence.source, EvidenceSource.CODEX_HOOK)
            self.assertEqual(evidence.kind, EvidenceKind.ACTIVITY)
            self.assertEqual(evidence.state, "tool_completed")
            self.assertEqual(evidence.summary, "Codex completed a tool call.")
            self.assertEqual(evidence.expires_at, 400)

    def test_unknown_hook_does_not_create_diagnostic_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"

            evidence = record_codex_hook_evidence(
                db_path=db_path,
                worker_id="worker-1",
                session_id=None,
                event_name="FutureHookWithPrivatePayload",
                observed_at=100,
                ttl_seconds=300,
            )

            self.assertIsNone(evidence)
            self.assertEqual(
                DiagnosticStore(db_path).list_evidence(worker_id="worker-1"),
                [],
            )

    def test_rate_limit_classification_uses_authoritative_fields(self) -> None:
        cases = (
            (
                rate_limits(reached_type="rate_limit_reached"),
                "rate_limit_reached",
            ),
            (
                rate_limits(reached_type="workspace_member_credits_depleted"),
                "workspace_member_credits_depleted",
            ),
            (
                rate_limits(spend_control_reached=True),
                "spend_control_reached",
            ),
            (
                rate_limits(ordinary_usage_allowed=False),
                "ordinary_usage_blocked",
            ),
            (rate_limits(ordinary_usage_allowed=True), "usage_available"),
            (rate_limits(ordinary_usage_allowed=None), "usage_unknown"),
            (rate_limits(reached_type="future_private_limit"), "account_limit_reached"),
        )

        for snapshot, expected_state in cases:
            with self.subTest(expected_state=expected_state):
                state, summary = classify_rate_limits(snapshot)
                self.assertEqual(state, expected_state)
                self.assertTrue(summary.startswith("Codex "))

    def test_collection_reads_only_limits_and_sets_expiry(self) -> None:
        calls: list[dict[str, object]] = []

        def reader(**kwargs: object) -> RateLimitSnapshot:
            calls.append(kwargs)
            return rate_limits(ordinary_usage_allowed=False)

        observation = collect_codex_limit_observation(
            codex_executable="/opt/codex",
            request_timeout=3,
            ttl_seconds=60,
            observed_at=100,
            reader=reader,
        )

        self.assertEqual(observation.state, "ordinary_usage_blocked")
        self.assertEqual(observation.observed_at, 100)
        self.assertEqual(observation.expires_at, 160)
        self.assertEqual(
            calls,
            [{"codex_executable": "/opt/codex", "request_timeout": 3}],
        )

    def test_invalid_evidence_ttl_fails_before_rate_limit_read(self) -> None:
        called = False

        def reader(**kwargs: object) -> RateLimitSnapshot:
            nonlocal called
            called = True
            return rate_limits()

        with self.assertRaisesRegex(ValueError, "greater than zero"):
            collect_codex_limit_observation(ttl_seconds=0, reader=reader)

        self.assertFalse(called)


class CodexLimitObserverCliTests(unittest.TestCase):
    def test_parser_defaults_to_one_read_and_accepts_worker_scope(self) -> None:
        args = build_parser().parse_args(
            [
                "observe-codex-limits",
                "--project",
                "/tmp/project",
                "--session",
                "session-1",
                "--interval",
                "120",
                "--evidence-ttl",
                "240",
            ]
        )

        self.assertFalse(args.watch)
        self.assertEqual(args.project, Path("/tmp/project"))
        self.assertEqual(args.session, "session-1")
        self.assertEqual(args.interval, 120)
        self.assertEqual(args.evidence_ttl, 240)

    @patch("ai_presence_monitor.cli.collect_codex_limit_observation")
    def test_one_shot_observer_requires_worker_and_records_evidence(
        self,
        collect: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store = PresenceStore(db_path)
            store.record_event(
                worker_id="worker-1",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            worker_before = store.get_worker("worker-1")
            collect.return_value = CodexLimitObservation(  # type: ignore[attr-defined]
                state="usage_available",
                summary="Codex reported ordinary usage as available.",
                observed_at=100,
                expires_at=700,
            )
            args = Namespace(
                interval=None,
                evidence_ttl=None,
                dry_run=False,
                codex_executable="codex",
                request_timeout=10,
                session="session-1",
                watch=False,
            )
            config = SimpleNamespace(
                db_path=db_path,
                codex_limit_poll_interval_seconds=300,
                codex_limit_evidence_ttl_seconds=600,
            )

            with patch(
                "ai_presence_monitor.cli._identity",
                return_value=("worker-1", "computer", "codex", "protocol2"),
            ):
                with redirect_stdout(StringIO()):
                    result = _observe_codex_limits(args, config)  # type: ignore[arg-type]

            self.assertEqual(result, 0)
            evidence = DiagnosticStore(db_path).list_evidence(worker_id="worker-1")
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].kind, EvidenceKind.ACCOUNT_LIMIT)
            self.assertEqual(evidence[0].state, "usage_available")
            self.assertEqual(evidence[0].session_id, "session-1")
            worker_after = store.get_worker("worker-1")
            self.assertEqual(worker_after, worker_before)

    @patch("ai_presence_monitor.cli.collect_codex_limit_observation")
    def test_observer_rejects_missing_worker_before_app_server_read(
        self,
        collect: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = Namespace(
                interval=None,
                evidence_ttl=None,
                dry_run=False,
                codex_executable="codex",
                request_timeout=10,
                session=None,
                watch=False,
            )
            config = SimpleNamespace(
                db_path=Path(tmp) / "presence.db",
                codex_limit_poll_interval_seconds=300,
                codex_limit_evidence_ttl_seconds=600,
            )

            with patch(
                "ai_presence_monitor.cli._identity",
                return_value=("missing-worker", "computer", "codex", "protocol2"),
            ):
                with self.assertRaisesRegex(ValueError, "Run start"):
                    _observe_codex_limits(args, config)  # type: ignore[arg-type]

            self.assertFalse(collect.called)  # type: ignore[attr-defined]

    @patch("ai_presence_monitor.cli.collect_codex_limit_observation")
    def test_dry_run_reads_but_does_not_create_database(self, collect: object) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "missing" / "presence.db"
            collect.return_value = CodexLimitObservation(  # type: ignore[attr-defined]
                state="usage_unknown",
                summary="Codex did not report ordinary usage availability.",
                observed_at=100,
                expires_at=700,
            )
            args = Namespace(
                interval=None,
                evidence_ttl=None,
                dry_run=True,
                codex_executable="codex",
                request_timeout=10,
                session=None,
                watch=False,
            )
            config = SimpleNamespace(
                db_path=db_path,
                codex_limit_poll_interval_seconds=300,
                codex_limit_evidence_ttl_seconds=600,
            )

            with patch(
                "ai_presence_monitor.cli._identity",
                return_value=("worker-1", "computer", "codex", "protocol2"),
            ):
                with redirect_stdout(StringIO()) as output:
                    result = _observe_codex_limits(args, config)  # type: ignore[arg-type]

            self.assertEqual(result, 0)
            self.assertIn("[dry-run:codex-limit]", output.getvalue())
            self.assertFalse(db_path.exists())

    @patch("ai_presence_monitor.cli.time.sleep")
    @patch("ai_presence_monitor.cli.collect_codex_limit_observation")
    def test_dry_run_watch_performs_one_read_without_sleeping(
        self,
        collect: object,
        sleep: object,
    ) -> None:
        collect.return_value = CodexLimitObservation(  # type: ignore[attr-defined]
            state="usage_unknown",
            summary="Codex did not report ordinary usage availability.",
            observed_at=100,
            expires_at=700,
        )
        args = Namespace(
            interval=1,
            evidence_ttl=2,
            dry_run=True,
            codex_executable="codex",
            request_timeout=10,
            session=None,
            watch=True,
        )
        config = SimpleNamespace(
            db_path=Path("/tmp/not-used.db"),
            codex_limit_poll_interval_seconds=300,
            codex_limit_evidence_ttl_seconds=600,
        )

        with patch(
            "ai_presence_monitor.cli._identity",
            return_value=("worker-1", "computer", "codex", "protocol2"),
        ):
            with redirect_stdout(StringIO()):
                result = _observe_codex_limits(args, config)  # type: ignore[arg-type]

        self.assertEqual(result, 0)
        self.assertEqual(collect.call_count, 1)  # type: ignore[attr-defined]
        self.assertFalse(sleep.called)  # type: ignore[attr-defined]

    @patch("ai_presence_monitor.cli.time.sleep")
    @patch("ai_presence_monitor.cli.record_codex_limit_observation")
    @patch("ai_presence_monitor.cli.collect_codex_limit_observation")
    @patch("ai_presence_monitor.cli.PresenceStore")
    def test_watch_stops_cleanly_when_worker_becomes_idle(
        self,
        presence_store: object,
        collect: object,
        record: object,
        sleep: object,
    ) -> None:
        presence_store.return_value.get_worker.side_effect = [  # type: ignore[attr-defined]
            SimpleNamespace(status="active"),
            SimpleNamespace(status="active"),
            SimpleNamespace(status="idle"),
        ]
        collect.return_value = CodexLimitObservation(  # type: ignore[attr-defined]
            state="usage_available",
            summary="Codex reported ordinary usage as available.",
            observed_at=100,
            expires_at=700,
        )
        record.return_value = SimpleNamespace(  # type: ignore[attr-defined]
            state="usage_available",
            evidence_id="evidence-1",
        )
        args = Namespace(
            interval=1,
            evidence_ttl=2,
            dry_run=False,
            codex_executable="codex",
            request_timeout=10,
            session=None,
            watch=True,
        )
        config = SimpleNamespace(
            db_path=Path("/tmp/not-used.db"),
            codex_limit_poll_interval_seconds=300,
            codex_limit_evidence_ttl_seconds=600,
        )

        with patch(
            "ai_presence_monitor.cli._identity",
            return_value=("worker-1", "computer", "codex", "protocol2"),
        ):
            with redirect_stdout(StringIO()) as output:
                result = _observe_codex_limits(args, config)  # type: ignore[arg-type]

        self.assertEqual(result, 0)
        self.assertEqual(collect.call_count, 1)  # type: ignore[attr-defined]
        self.assertEqual(record.call_count, 1)  # type: ignore[attr-defined]
        self.assertEqual(sleep.call_count, 1)  # type: ignore[attr-defined]
        self.assertIn("observer encerrado", output.getvalue())


if __name__ == "__main__":
    unittest.main()
