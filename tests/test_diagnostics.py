from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ai_presence_monitor.diagnostics import (
    DiagnosisConfidence,
    DiagnosisKind,
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
    IncidentSeverity,
    IncidentStatus,
)
from ai_presence_monitor.store import PresenceStore


class DiagnosticStoreTests(unittest.TestCase):
    def test_presence_store_adds_diagnostic_schema_to_existing_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE legacy_marker (value TEXT NOT NULL)")
                conn.execute("INSERT INTO legacy_marker (value) VALUES ('preserved')")

            PresenceStore(db_path)

            with sqlite3.connect(db_path) as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                marker = conn.execute("SELECT value FROM legacy_marker").fetchone()
            self.assertEqual(marker, ("preserved",))
            self.assertTrue(
                {
                    "diagnostic_evidence",
                    "diagnostic_diagnoses",
                    "diagnostic_diagnosis_evidence",
                    "diagnostic_incidents",
                    "diagnostic_notifications",
                }.issubset(tables)
            )

    def test_evidence_is_typed_sanitized_and_filterable_by_validity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiagnosticStore(Path(tmp) / "presence.db")
            expired = store.record_evidence(
                worker_id="worker",
                session_id="session-a",
                source=EvidenceSource.NETWORK,
                kind=EvidenceKind.NETWORK_STATE,
                state="unavailable",
                summary="  DNS   lookup failed  ",
                observed_at=100,
                expires_at=110,
            )
            current = store.record_evidence(
                worker_id="worker",
                session_id="session-a",
                source="codex_app_server",
                kind="codex_error",
                state="UsageLimitExceeded",
                observed_at=120,
            )

            self.assertEqual(expired.summary, "DNS lookup failed")
            self.assertEqual(current.source, EvidenceSource.CODEX_APP_SERVER)
            self.assertEqual(current.kind, EvidenceKind.CODEX_ERROR)
            self.assertEqual(
                store.list_evidence(worker_id="worker", valid_at=115),
                [current],
            )
            self.assertEqual(store.get_evidence(expired.evidence_id), expired)

    def test_evidence_rejects_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiagnosticStore(Path(tmp) / "presence.db")
            with self.assertRaisesRegex(ValueError, "Unknown evidence source"):
                store.record_evidence(
                    worker_id="worker",
                    source="unknown",
                    kind=EvidenceKind.ACTIVITY,
                    state="active",
                )
            with self.assertRaisesRegex(ValueError, "earlier than observed_at"):
                store.record_evidence(
                    worker_id="worker",
                    source=EvidenceSource.CODEX_HOOK,
                    kind=EvidenceKind.ACTIVITY,
                    state="active",
                    observed_at=20,
                    expires_at=10,
                )
            with self.assertRaisesRegex(ValueError, "single line"):
                store.record_evidence(
                    worker_id="worker\nother",
                    source=EvidenceSource.CODEX_HOOK,
                    kind=EvidenceKind.ACTIVITY,
                    state="active",
                )

    def test_diagnosis_links_ordered_evidence_and_infers_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiagnosticStore(Path(tmp) / "presence.db")
            first = store.record_evidence(
                worker_id="worker",
                session_id="session-a",
                source=EvidenceSource.CODEX_APP_SERVER,
                kind=EvidenceKind.CODEX_ERROR,
                state="UsageLimitExceeded",
                observed_at=100,
            )
            second = store.record_evidence(
                worker_id="worker",
                source=EvidenceSource.NETWORK,
                kind=EvidenceKind.NETWORK_STATE,
                state="available",
                observed_at=101,
            )

            diagnosis = store.record_diagnosis(
                worker_id="worker",
                kind=DiagnosisKind.USAGE_LIMIT_EXCEEDED,
                confidence=DiagnosisConfidence.HIGH,
                summary="  Codex reported a usage limit. ",
                evidence_ids=(first.evidence_id, second.evidence_id),
                diagnosed_at=102,
                valid_until=200,
            )

            self.assertEqual(diagnosis.session_id, "session-a")
            self.assertEqual(
                diagnosis.evidence_ids,
                (first.evidence_id, second.evidence_id),
            )
            self.assertEqual(diagnosis.summary, "Codex reported a usage limit.")
            self.assertEqual(store.get_diagnosis(diagnosis.diagnosis_id), diagnosis)
            self.assertEqual(store.list_diagnoses(worker_id="worker"), [diagnosis])

    def test_diagnosis_rejects_cross_worker_or_cross_session_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiagnosticStore(Path(tmp) / "presence.db")
            worker_a = store.record_evidence(
                worker_id="worker-a",
                session_id="session-a",
                source=EvidenceSource.CODEX_HOOK,
                kind=EvidenceKind.ACTIVITY,
                state="active",
            )
            worker_b = store.record_evidence(
                worker_id="worker-b",
                session_id="session-b",
                source=EvidenceSource.CODEX_HOOK,
                kind=EvidenceKind.ACTIVITY,
                state="active",
            )
            with self.assertRaisesRegex(ValueError, "same worker"):
                store.record_diagnosis(
                    worker_id="worker-a",
                    kind=DiagnosisKind.WORKING,
                    confidence=DiagnosisConfidence.HIGH,
                    summary="Worker is active.",
                    evidence_ids=(worker_a.evidence_id, worker_b.evidence_id),
                )

            other_session = store.record_evidence(
                worker_id="worker-a",
                session_id="session-b",
                source=EvidenceSource.CODEX_APP_SERVER,
                kind=EvidenceKind.THREAD_STATUS,
                state="active",
            )
            with self.assertRaisesRegex(ValueError, "multiple Codex sessions"):
                store.record_diagnosis(
                    worker_id="worker-a",
                    kind=DiagnosisKind.WORKING,
                    confidence=DiagnosisConfidence.MEDIUM,
                    summary="Conflicting session evidence.",
                    evidence_ids=(worker_a.evidence_id, other_session.evidence_id),
                )

    def test_incident_is_updated_once_then_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiagnosticStore(Path(tmp) / "presence.db")
            evidence = store.record_evidence(
                worker_id="worker",
                session_id="session-a",
                source=EvidenceSource.CODEX_APP_SERVER,
                kind=EvidenceKind.CODEX_ERROR,
                state="UsageLimitExceeded",
                observed_at=100,
            )
            first_diagnosis = store.record_diagnosis(
                worker_id="worker",
                kind=DiagnosisKind.USAGE_LIMIT_EXCEEDED,
                confidence=DiagnosisConfidence.HIGH,
                summary="Usage is blocked.",
                evidence_ids=(evidence.evidence_id,),
                diagnosed_at=101,
            )
            incident = store.open_or_update_incident(
                diagnosis_id=first_diagnosis.diagnosis_id,
                severity=IncidentSeverity.YELLOW,
                now=102,
            )
            notified = store.mark_incident_notified(incident.incident_id, now=103)
            self.assertEqual(notified.last_notified_at, 103)

            second_diagnosis = store.record_diagnosis(
                worker_id="worker",
                kind=DiagnosisKind.USAGE_LIMIT_EXCEEDED,
                confidence=DiagnosisConfidence.HIGH,
                summary="Usage remains blocked.",
                evidence_ids=(evidence.evidence_id,),
                diagnosed_at=104,
            )
            escalated = store.open_or_update_incident(
                diagnosis_id=second_diagnosis.diagnosis_id,
                severity=IncidentSeverity.ORANGE,
                now=105,
            )

            self.assertEqual(escalated.incident_id, incident.incident_id)
            self.assertEqual(escalated.severity, IncidentSeverity.ORANGE)
            self.assertEqual(
                escalated.current_diagnosis_id,
                second_diagnosis.diagnosis_id,
            )
            self.assertEqual(
                store.list_incidents(status=IncidentStatus.OPEN),
                [escalated],
            )

            resolved = store.resolve_incident(
                incident.incident_id,
                resolution="Codex activity resumed.",
                now=106,
            )
            self.assertEqual(resolved.status, IncidentStatus.RESOLVED)
            self.assertEqual(resolved.resolved_at, 106)
            self.assertEqual(resolved.resolution, "Codex activity resumed.")
            self.assertEqual(store.list_incidents(status="open"), [])


if __name__ == "__main__":
    unittest.main()
