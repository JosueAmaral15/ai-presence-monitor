from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.cli import main as cli_main
from ai_presence_monitor.diagnosis_engine import (
    assess_diagnosis,
    diagnose_worker,
    select_current_evidence,
)
from ai_presence_monitor.diagnostics import (
    DiagnosisConfidence,
    DiagnosisKind,
    DiagnosticEvidence,
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
    IncidentSeverity,
    IncidentStatus,
)
from ai_presence_monitor.store import PresenceStore


def make_evidence(
    evidence_id: str,
    *,
    source: EvidenceSource,
    kind: EvidenceKind,
    state: str,
    observed_at: float = 100,
    session_id: str | None = "session-a",
) -> DiagnosticEvidence:
    return DiagnosticEvidence(
        evidence_id=evidence_id,
        worker_id="worker",
        session_id=session_id,
        source=source,
        kind=kind,
        state=state,
        summary=None,
        observed_at=observed_at,
        expires_at=observed_at + 600,
    )


def start_worker(
    db_path: Path,
    *,
    last_activity_at: float,
    protocol: str = "protocol2",
) -> None:
    store = PresenceStore(db_path)
    store.record_event(
        worker_id="worker",
        computer="computer",
        ia_name="codex",
        protocol=protocol,
        event_type="start",
        task="task",
    )
    with store.session() as conn:
        conn.execute(
            """
            UPDATE workers
            SET last_signal_at = ?, last_activity_at = ?, updated_at = ?
            WHERE worker_id = 'worker'
            """,
            (last_activity_at, last_activity_at, last_activity_at),
        )


class DiagnosisAssessmentTests(unittest.TestCase):
    def test_current_evidence_keeps_latest_batch_and_session_neutral_facts(self) -> None:
        records = (
            make_evidence(
                "old-service",
                source=EvidenceSource.SERVICE,
                kind=EvidenceKind.SERVICE_STATE,
                state="failed",
                observed_at=90,
                session_id=None,
            ),
            make_evidence(
                "service-a",
                source=EvidenceSource.SERVICE,
                kind=EvidenceKind.SERVICE_STATE,
                state="active",
                observed_at=100,
                session_id=None,
            ),
            make_evidence(
                "service-b",
                source=EvidenceSource.SERVICE,
                kind=EvidenceKind.SERVICE_STATE,
                state="inactive",
                observed_at=100,
                session_id=None,
            ),
            make_evidence(
                "hook",
                source=EvidenceSource.CODEX_HOOK,
                kind=EvidenceKind.ACTIVITY,
                state="tool_started",
                observed_at=101,
            ),
        )

        selected = select_current_evidence(records)

        self.assertEqual(
            {item.evidence_id for item in selected},
            {"service-a", "service-b", "hook"},
        )

    def test_current_evidence_rejects_ambiguous_sessions_and_filters_exact_one(self) -> None:
        first = make_evidence(
            "first",
            source=EvidenceSource.CODEX_HOOK,
            kind=EvidenceKind.ACTIVITY,
            state="tool_started",
            session_id="session-a",
        )
        second = make_evidence(
            "second",
            source=EvidenceSource.CODEX_APP_SERVER,
            kind=EvidenceKind.ACCOUNT_LIMIT,
            state="usage_available",
            session_id="session-b",
        )
        neutral = make_evidence(
            "neutral",
            source=EvidenceSource.NETWORK,
            kind=EvidenceKind.NETWORK_STATE,
            state="default_route_available",
            session_id=None,
        )

        with self.assertRaisesRegex(ValueError, "multiple Codex sessions"):
            select_current_evidence((first, second, neutral))

        selected = select_current_evidence(
            (first, second, neutral),
            session_id="session-a",
        )
        self.assertEqual(
            {item.evidence_id for item in selected},
            {"first", "neutral"},
        )

    def test_direct_usage_limit_precedes_other_failures(self) -> None:
        evidence = (
            make_evidence(
                "limit",
                source=EvidenceSource.CODEX_APP_SERVER,
                kind=EvidenceKind.ACCOUNT_LIMIT,
                state="rate_limit_reached",
            ),
            make_evidence(
                "process",
                source=EvidenceSource.PROCESS,
                kind=EvidenceKind.PROCESS_STATE,
                state="zombie",
            ),
        )

        assessment = assess_diagnosis(evidence, overdue=True)

        self.assertEqual(assessment.kind, DiagnosisKind.USAGE_LIMIT_EXCEEDED)
        self.assertEqual(assessment.confidence, DiagnosisConfidence.HIGH)
        self.assertEqual(
            tuple(item.evidence_id for item in assessment.evidence),
            ("limit",),
        )

    def test_network_diagnosis_is_conservative(self) -> None:
        medium = assess_diagnosis(
            (
                make_evidence(
                    "network",
                    source=EvidenceSource.NETWORK,
                    kind=EvidenceKind.NETWORK_STATE,
                    state="no_usable_link",
                ),
            ),
            overdue=True,
        )
        low = assess_diagnosis(
            (
                make_evidence(
                    "network",
                    source=EvidenceSource.NETWORK,
                    kind=EvidenceKind.NETWORK_STATE,
                    state="link_up_no_default_route",
                ),
            ),
            overdue=True,
        )

        self.assertEqual(medium.kind, DiagnosisKind.NETWORK_UNAVAILABLE)
        self.assertEqual(medium.confidence, DiagnosisConfidence.MEDIUM)
        self.assertEqual(low.kind, DiagnosisKind.NETWORK_UNAVAILABLE)
        self.assertEqual(low.confidence, DiagnosisConfidence.LOW)

    def test_failure_cause_vocabulary_has_deterministic_mappings(self) -> None:
        cases = (
            (
                EvidenceSource.INTERACTION,
                EvidenceKind.INTERACTION_STATE,
                "waiting_for_approval",
                DiagnosisKind.WAITING_FOR_APPROVAL,
                DiagnosisConfidence.HIGH,
            ),
            (
                EvidenceSource.INTERACTION,
                EvidenceKind.INTERACTION_STATE,
                "waiting_for_user",
                DiagnosisKind.WAITING_FOR_USER,
                DiagnosisConfidence.HIGH,
            ),
            (
                EvidenceSource.CODEX_APP_SERVER,
                EvidenceKind.CODEX_ERROR,
                "context_window_exceeded",
                DiagnosisKind.CONTEXT_WINDOW_EXCEEDED,
                DiagnosisConfidence.HIGH,
            ),
            (
                EvidenceSource.PROCESS,
                EvidenceKind.PROCESS_STATE,
                "zombie",
                DiagnosisKind.CODEX_CRASHED,
                DiagnosisConfidence.HIGH,
            ),
            (
                EvidenceSource.PROCESS,
                EvidenceKind.PROCESS_STATE,
                "missing",
                DiagnosisKind.CODEX_CLOSED,
                DiagnosisConfidence.MEDIUM,
            ),
            (
                EvidenceSource.POWER,
                EvidenceKind.POWER_STATE,
                "resume_detected",
                DiagnosisKind.SYSTEM_SUSPENDED,
                DiagnosisConfidence.MEDIUM,
            ),
            (
                EvidenceSource.SERVICE,
                EvidenceKind.SERVICE_STATE,
                "failed",
                DiagnosisKind.OBSERVER_UNHEALTHY,
                DiagnosisConfidence.HIGH,
            ),
            (
                EvidenceSource.PROCESS,
                EvidenceKind.PROCESS_STATE,
                "identity_mismatch",
                DiagnosisKind.OBSERVER_UNHEALTHY,
                DiagnosisConfidence.MEDIUM,
            ),
        )
        for source, evidence_kind, state, expected_kind, expected_confidence in cases:
            with self.subTest(state=state):
                assessment = assess_diagnosis(
                    (
                        make_evidence(
                            state,
                            source=source,
                            kind=evidence_kind,
                            state=state,
                        ),
                    ),
                    overdue=True,
                )
                self.assertEqual(assessment.kind, expected_kind)
                self.assertEqual(assessment.confidence, expected_confidence)

    def test_positive_local_facts_fall_back_to_unexplained_inactivity(self) -> None:
        evidence = (
            make_evidence(
                "process",
                source=EvidenceSource.PROCESS,
                kind=EvidenceKind.PROCESS_STATE,
                state="running",
            ),
            make_evidence(
                "network",
                source=EvidenceSource.NETWORK,
                kind=EvidenceKind.NETWORK_STATE,
                state="default_route_available",
            ),
            make_evidence(
                "presence",
                source=EvidenceSource.WORKSPACE,
                kind=EvidenceKind.WORKSPACE_STATE,
                state="presence_threshold_exceeded",
            ),
        )

        assessment = assess_diagnosis(evidence, overdue=True)

        self.assertEqual(assessment.kind, DiagnosisKind.UNEXPLAINED_INACTIVITY)
        self.assertEqual(assessment.confidence, DiagnosisConfidence.LOW)
        self.assertEqual(
            tuple(item.evidence_id for item in assessment.evidence),
            ("presence",),
        )

    def test_long_running_and_current_presence_are_healthy(self) -> None:
        long_running = assess_diagnosis(
            (
                make_evidence(
                    "tool",
                    source=EvidenceSource.CODEX_HOOK,
                    kind=EvidenceKind.ACTIVITY,
                    state="tool_started",
                ),
            ),
            overdue=True,
        )
        current = assess_diagnosis(
            (
                make_evidence(
                    "presence",
                    source=EvidenceSource.WORKSPACE,
                    kind=EvidenceKind.WORKSPACE_STATE,
                    state="presence_within_threshold",
                ),
            ),
            overdue=False,
        )

        self.assertEqual(long_running.kind, DiagnosisKind.LONG_RUNNING_OPERATION)
        self.assertEqual(current.kind, DiagnosisKind.WORKING)
        self.assertEqual(current.confidence, DiagnosisConfidence.HIGH)

    def test_unrelated_inactive_state_does_not_claim_observer_failure(self) -> None:
        assessment = assess_diagnosis(
            (
                make_evidence(
                    "interaction",
                    source=EvidenceSource.INTERACTION,
                    kind=EvidenceKind.INTERACTION_STATE,
                    state="inactive",
                ),
            ),
            overdue=True,
        )

        self.assertEqual(assessment.kind, DiagnosisKind.UNEXPLAINED_INACTIVITY)


class DiagnosisWorkflowTests(unittest.TestCase):
    def test_overdue_worker_opens_then_updates_one_incident(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            start_worker(db_path, last_activity_at=100)
            diagnostic_store = DiagnosticStore(db_path)
            diagnostic_store.record_evidence(
                worker_id="worker",
                session_id="session-a",
                source=EvidenceSource.CODEX_APP_SERVER,
                kind=EvidenceKind.ACCOUNT_LIMIT,
                state="rate_limit_reached",
                observed_at=390,
                expires_at=1000,
            )

            yellow = diagnose_worker(
                db_path=db_path,
                worker_id="worker",
                session_id="session-a",
                now=400,
            )
            notified = diagnostic_store.mark_incident_notified(
                yellow.incident.incident_id,  # type: ignore[union-attr]
                now=410,
            )
            orange = diagnose_worker(
                db_path=db_path,
                worker_id="worker",
                session_id="session-a",
                now=700,
            )

            self.assertEqual(yellow.severity, IncidentSeverity.YELLOW)
            self.assertEqual(yellow.transition, "opened")
            self.assertIsNotNone(yellow.diagnosis)
            self.assertIsNotNone(yellow.incident)
            self.assertEqual(len(yellow.diagnosis.evidence_ids), 2)  # type: ignore[union-attr]
            self.assertEqual(orange.severity, IncidentSeverity.ORANGE)
            self.assertEqual(orange.transition, "updated")
            self.assertEqual(orange.incident.incident_id, yellow.incident.incident_id)  # type: ignore[union-attr]
            self.assertEqual(orange.incident.last_notified_at, notified.last_notified_at)  # type: ignore[union-attr]
            self.assertEqual(
                len(
                    diagnostic_store.list_incidents(
                        worker_id="worker",
                        status=IncidentStatus.OPEN,
                    )
                ),
                1,
            )

    def test_fresh_presence_resolves_existing_incident(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            start_worker(db_path, last_activity_at=100)
            opened = diagnose_worker(
                db_path=db_path,
                worker_id="worker",
                now=400,
            )
            with PresenceStore(db_path).session() as conn:
                conn.execute(
                    "UPDATE workers SET last_activity_at = 490 WHERE worker_id = 'worker'"
                )

            resolved = diagnose_worker(
                db_path=db_path,
                worker_id="worker",
                now=500,
            )

            self.assertEqual(opened.assessment.kind, DiagnosisKind.UNEXPLAINED_INACTIVITY)
            self.assertEqual(resolved.assessment.kind, DiagnosisKind.WORKING)
            self.assertEqual(resolved.severity, IncidentSeverity.INFO)
            self.assertEqual(resolved.transition, "resolved")
            self.assertEqual(resolved.incident.status, IncidentStatus.RESOLVED)  # type: ignore[union-attr]
            self.assertEqual(
                resolved.incident.incident_id,  # type: ignore[union-attr]
                opened.incident.incident_id,  # type: ignore[union-attr]
            )

    def test_healthy_worker_without_incident_records_no_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            start_worker(db_path, last_activity_at=490)

            result = diagnose_worker(
                db_path=db_path,
                worker_id="worker",
                now=500,
            )

            self.assertEqual(result.assessment.kind, DiagnosisKind.WORKING)
            self.assertEqual(result.transition, "none")
            self.assertIsNone(result.incident)

    def test_protocol1_uses_signal_clock_and_red_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            start_worker(db_path, last_activity_at=100, protocol="protocol1")
            with PresenceStore(db_path).session() as conn:
                conn.execute(
                    """
                    UPDATE workers
                    SET last_signal_at = NULL, last_activity_at = 1900
                    WHERE worker_id = 'worker'
                    """
                )

            result = diagnose_worker(
                db_path=db_path,
                worker_id="worker",
                now=2000,
                dry_run=True,
            )

            self.assertEqual(result.severity, IncidentSeverity.RED)
            self.assertEqual(result.transition, "opened")

    def test_dry_run_does_not_write_diagnostic_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            start_worker(db_path, last_activity_at=100)
            before = self._diagnostic_counts(db_path)

            result = diagnose_worker(
                db_path=db_path,
                worker_id="worker",
                now=400,
                dry_run=True,
            )

            self.assertEqual(result.transition, "opened")
            self.assertIsNone(result.diagnosis)
            self.assertIsNone(result.incident)
            self.assertEqual(self._diagnostic_counts(db_path), before)

    def test_cli_dry_run_emits_sanitized_json_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "presence.db"
            env_path = root / ".env"
            env_path.write_text("", encoding="utf-8")
            start_worker(db_path, last_activity_at=100)
            before = self._diagnostic_counts(db_path)
            output = io.StringIO()

            with (
                patch.dict(os.environ, {}, clear=True),
                redirect_stdout(output),
                self.assertRaises(SystemExit) as raised,
            ):
                cli_main(
                    [
                        "--env-file",
                        str(env_path),
                        "--db",
                        str(db_path),
                        "--dry-run",
                        "diagnose",
                        "--worker",
                        "worker",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(raised.exception.code, 0)
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["kind"], "unexplained_inactivity")
            self.assertEqual(payload["transition"], "opened")
            self.assertIsNone(payload["diagnosis_id"])
            self.assertEqual(self._diagnostic_counts(db_path), before)

    def test_conflicting_sessions_fail_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            start_worker(db_path, last_activity_at=100)
            store = DiagnosticStore(db_path)
            for session_id, observed_at in (("session-a", 200), ("session-b", 201)):
                store.record_evidence(
                    worker_id="worker",
                    session_id=session_id,
                    source=EvidenceSource.CODEX_HOOK,
                    kind=EvidenceKind.ACTIVITY,
                    state="tool_started",
                    observed_at=observed_at,
                    expires_at=800,
                )
            before = self._diagnostic_counts(db_path)

            with self.assertRaisesRegex(ValueError, "multiple Codex sessions"):
                diagnose_worker(db_path=db_path, worker_id="worker", now=400)

            self.assertEqual(self._diagnostic_counts(db_path), before)

    def test_missing_idle_and_invalid_ttl_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            with self.assertRaisesRegex(ValueError, "Worker not found"):
                diagnose_worker(db_path=db_path, worker_id="missing", now=400)

            start_worker(db_path, last_activity_at=100)
            PresenceStore(db_path).record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="finish",
            )
            with self.assertRaisesRegex(ValueError, "not active"):
                diagnose_worker(db_path=db_path, worker_id="worker", now=400)
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                diagnose_worker(
                    db_path=db_path,
                    worker_id="worker",
                    now=400,
                    presence_ttl_seconds=0,
                )

    @staticmethod
    def _diagnostic_counts(db_path: Path) -> tuple[int, int, int]:
        with sqlite3.connect(db_path) as conn:
            return tuple(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "diagnostic_evidence",
                    "diagnostic_diagnoses",
                    "diagnostic_incidents",
                )
            )  # type: ignore[return-value]


if __name__ == "__main__":
    unittest.main()
