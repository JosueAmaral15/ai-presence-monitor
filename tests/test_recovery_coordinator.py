from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.cli import main as cli_main
from ai_presence_monitor.codex_input import CodexInputError, CodexInputResult
from ai_presence_monitor.control import ControlSettings
from ai_presence_monitor.diagnostic_notifications import diagnostic_event_key
from ai_presence_monitor.diagnostics import (
    DiagnosisConfidence,
    DiagnosisKind,
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
    IncidentSeverity,
    NotificationDeliveryStatus,
    RecoveryStatus,
)
from ai_presence_monitor.recovery_coordinator import (
    RECOVERY_ACTION,
    recover_diagnostic_incident,
)
from ai_presence_monitor.store import PresenceStore


class FakeRecoveryClient:
    def __init__(
        self,
        *,
        state: str = "input_emitted",
        error: Exception | None = None,
        available: bool = True,
    ) -> None:
        self.state = state
        self.error = error
        self.available = available
        self.availability_checks = 0
        self.sent: list[dict[str, object]] = []

    def is_available(self) -> bool:
        self.availability_checks += 1
        return self.available

    def send(
        self,
        *,
        thread_id: str,
        text: str,
        remote: str | None = None,
        remote_auth_token_env: str | None = None,
        detached: bool = False,
    ) -> CodexInputResult:
        self.sent.append(
            {
                "thread_id": thread_id,
                "text": text,
                "remote": remote,
                "remote_auth_token_env": remote_auth_token_env,
                "detached": detached,
            }
        )
        if self.error is not None:
            raise self.error
        return CodexInputResult(
            thread_id=thread_id,
            remote=remote,
            state=self.state,  # type: ignore[arg-type]
        )


def create_recovery_incident(
    db_path: Path,
    *,
    worker_id: str = "worker",
    session_id: str | None = "session-a",
    kind: DiagnosisKind = DiagnosisKind.CODEX_CRASHED,
    confidence: DiagnosisConfidence = DiagnosisConfidence.HIGH,
    severity: IncidentSeverity = IncidentSeverity.RED,
    valid_until: float | None = 500,
    delivered_notification: bool = True,
):
    presence = PresenceStore(db_path)
    worker = presence.record_event(
        worker_id=worker_id,
        computer="computer",
        ia_name="codex",
        protocol="protocol2",
        event_type="start",
        task="task",
    )
    store = DiagnosticStore(db_path)
    evidence = store.record_evidence(
        worker_id=worker_id,
        session_id=session_id,
        source=EvidenceSource.PROCESS,
        kind=EvidenceKind.PROCESS_STATE,
        state="zombie" if kind is DiagnosisKind.CODEX_CRASHED else "missing",
        observed_at=110,
        expires_at=valid_until,
    )
    diagnosis = store.record_diagnosis(
        worker_id=worker_id,
        session_id=session_id,
        kind=kind,
        confidence=confidence,
        summary=f"Recovery diagnosis for {kind.value}.",
        evidence_ids=(evidence.evidence_id,),
        diagnosed_at=120,
        valid_until=valid_until,
    )
    incident = store.open_or_update_incident(
        diagnosis_id=diagnosis.diagnosis_id,
        severity=severity,
        now=130,
    )
    if delivered_notification:
        notification, created = store.reserve_notification(
            incident_id=incident.incident_id,
            diagnosis_id=diagnosis.diagnosis_id,
            event_key=diagnostic_event_key(incident, diagnosis),
            now=140,
        )
        assert created
        store.complete_notification(
            notification.notification_id,
            status=NotificationDeliveryStatus.DELIVERED,
            now=150,
        )
    return presence, store, worker, diagnosis, incident


class RecoveryCoordinatorTests(unittest.TestCase):
    def test_codex_closed_medium_confidence_is_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            _, store, _, diagnosis, incident = create_recovery_incident(
                db_path,
                kind=DiagnosisKind.CODEX_CLOSED,
                confidence=DiagnosisConfidence.MEDIUM,
            )

            result = recover_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                controls=ControlSettings(),
                message="continue",
                dry_run=True,
                now=200,
            )

            self.assertEqual(result.status, "would_dispatch")
            self.assertEqual(result.incident_id, incident.incident_id)
            self.assertEqual(result.diagnosis_id, diagnosis.diagnosis_id)
            self.assertEqual(store.list_recoveries(), [])

    def test_dry_run_has_no_transport_or_recovery_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            _, store, _, diagnosis, incident = create_recovery_incident(db_path)
            client = FakeRecoveryClient(available=False)

            result = recover_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                controls=ControlSettings(),
                message="continue",
                dry_run=True,
                client=client,
                now=200,
            )

            self.assertEqual(result.status, "would_dispatch")
            self.assertEqual(result.incident_id, incident.incident_id)
            self.assertEqual(result.diagnosis_id, diagnosis.diagnosis_id)
            self.assertEqual(client.availability_checks, 0)
            self.assertEqual(client.sent, [])
            self.assertEqual(store.list_recoveries(), [])

    def test_authorized_input_is_recorded_once_without_activity_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            presence, store, worker, _, incident = create_recovery_incident(db_path)
            client = FakeRecoveryClient()

            first = recover_diagnostic_incident(
                db_path=db_path,
                worker_id=worker.worker_id,
                controls=ControlSettings(),
                message="continue",
                authorized=True,
                client=client,
                now=200,
            )
            duplicate_client = FakeRecoveryClient()
            second = recover_diagnostic_incident(
                db_path=db_path,
                worker_id=worker.worker_id,
                controls=ControlSettings(),
                message="continue",
                authorized=True,
                client=duplicate_client,
                now=210,
            )

            self.assertEqual(first.status, "input_emitted")
            self.assertEqual(second.status, "deduplicated")
            self.assertEqual(len(client.sent), 1)
            self.assertIsNone(client.sent[0]["remote"])
            self.assertIsNone(client.sent[0]["remote_auth_token_env"])
            self.assertEqual(duplicate_client.sent, [])
            recoveries = store.list_recoveries(incident_id=incident.incident_id)
            self.assertEqual(len(recoveries), 1)
            self.assertEqual(recoveries[0].status, RecoveryStatus.INPUT_EMITTED)
            unchanged = presence.get_worker(worker.worker_id)
            assert unchanged is not None
            self.assertEqual(unchanged.last_activity_at, worker.last_activity_at)

    def test_current_session_records_dispatch_started_without_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            presence, store, worker, _, _ = create_recovery_incident(db_path)
            client = FakeRecoveryClient(state="dispatch_started")
            with patch.dict(os.environ, {"CODEX_SESSION_ID": "session-a"}):
                result = recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id=worker.worker_id,
                    controls=ControlSettings(),
                    message="continue",
                    authorized=True,
                    client=client,
                    now=200,
                )

            self.assertEqual(result.status, "dispatch_started")
            self.assertTrue(client.sent[0]["detached"])
            self.assertEqual(
                store.require_recovery(result.recovery_id or "").status,
                RecoveryStatus.DISPATCH_STARTED,
            )
            unchanged = presence.get_worker(worker.worker_id)
            assert unchanged is not None
            self.assertEqual(unchanged.last_activity_at, worker.last_activity_at)

    def test_uncertain_and_interrupted_attempts_are_not_retried(self) -> None:
        cases = (
            (
                CodexInputError("uncertain"),
                RecoveryStatus.UNCERTAIN,
                "uncertain",
            ),
            (RuntimeError("interrupted"), RecoveryStatus.PENDING, None),
        )
        for error, stored_status, result_status in cases:
            with self.subTest(status=stored_status.value), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "presence.db"
                _, store, _, _, _ = create_recovery_incident(db_path)
                client = FakeRecoveryClient(error=error)
                if result_status is None:
                    with self.assertRaisesRegex(RuntimeError, "interrupted"):
                        recover_diagnostic_incident(
                            db_path=db_path,
                            worker_id="worker",
                            controls=ControlSettings(),
                            message="continue",
                            authorized=True,
                            client=client,
                            now=200,
                        )
                else:
                    result = recover_diagnostic_incident(
                        db_path=db_path,
                        worker_id="worker",
                        controls=ControlSettings(),
                        message="continue",
                        authorized=True,
                        client=client,
                        now=200,
                    )
                    self.assertEqual(result.status, result_status)

                retry_client = FakeRecoveryClient()
                repeated = recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    controls=ControlSettings(),
                    message="continue",
                    authorized=True,
                    client=retry_client,
                    now=210,
                )
                self.assertEqual(repeated.status, "deduplicated")
                self.assertEqual(retry_client.sent, [])
                self.assertEqual(store.list_recoveries()[0].status, stored_status)

    def test_real_recovery_requires_authorization_and_available_native_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            _, store, _, _, _ = create_recovery_incident(db_path)
            client = FakeRecoveryClient(available=False)
            with self.assertRaisesRegex(ValueError, "authorize-once"):
                recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    controls=ControlSettings(task_automation_enabled=True),
                    message="continue",
                    client=client,
                    now=200,
                )
            with self.assertRaisesRegex(ValueError, "not available"):
                recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    controls=ControlSettings(),
                    message="continue",
                    authorized=True,
                    client=client,
                    now=200,
                )
            with self.assertRaisesRegex(ValueError, "disabled"):
                recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    controls=ControlSettings(native_input_enabled=False),
                    message="continue",
                    authorized=True,
                    client=FakeRecoveryClient(),
                    now=200,
                )
            self.assertEqual(store.list_recoveries(), [])
            self.assertEqual(client.sent, [])

    def test_recovery_requires_eligible_current_diagnosis_and_notification(self) -> None:
        cases = (
            (
                {"kind": DiagnosisKind.USAGE_LIMIT_EXCEEDED},
                "not eligible",
            ),
            (
                {
                    "kind": DiagnosisKind.CODEX_CLOSED,
                    "confidence": DiagnosisConfidence.LOW,
                },
                "not eligible",
            ),
            ({"valid_until": 190}, "expired"),
            ({"session_id": None}, "exact persisted"),
            ({"delivered_notification": False}, "confirmed Discord"),
        )
        for options, error in cases:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "presence.db"
                _, store, _, _, _ = create_recovery_incident(db_path, **options)
                with self.assertRaisesRegex(ValueError, error):
                    recover_diagnostic_incident(
                        db_path=db_path,
                        worker_id="worker",
                        controls=ControlSettings(),
                        message="continue",
                        dry_run=True,
                        now=200,
                    )
                self.assertEqual(store.list_recoveries(), [])

    def test_worker_and_message_validation_fail_before_recovery_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            presence, store, worker, _, _ = create_recovery_incident(db_path)
            with self.assertRaisesRegex(ValueError, "single line"):
                recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id=worker.worker_id,
                    controls=ControlSettings(),
                    message="continue\nnow",
                    dry_run=True,
                )
            presence.record_event(
                worker_id=worker.worker_id,
                computer=worker.computer,
                ia_name=worker.ia_name,
                protocol=worker.protocol,
                event_type="finish",
            )
            with self.assertRaisesRegex(ValueError, "not active"):
                recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id=worker.worker_id,
                    controls=ControlSettings(),
                    message="continue",
                    dry_run=True,
                    now=200,
                )
            with self.assertRaisesRegex(ValueError, "Worker not found"):
                recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id="missing",
                    controls=ControlSettings(),
                    message="continue",
                    dry_run=True,
                    now=200,
                )
            self.assertEqual(store.list_recoveries(), [])

    def test_non_finite_time_is_rejected_before_recovery_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            _, store, _, _, _ = create_recovery_incident(db_path)

            with self.assertRaisesRegex(ValueError, "finite timestamp"):
                recover_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    controls=ControlSettings(),
                    message="continue",
                    dry_run=True,
                    now=float("nan"),
                )

            self.assertEqual(store.list_recoveries(), [])

    def test_cli_dry_run_and_real_authorization_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "presence.db"
            env_path = root / ".env"
            env_path.write_text("PRESENCE_CONTINUE_MESSAGE=continue\n", encoding="utf-8")
            _, store, _, _, _ = create_recovery_incident(
                db_path,
                valid_until=None,
            )

            output = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                redirect_stdout(output),
                self.assertRaises(SystemExit) as dry_exit,
            ):
                cli_main(
                    [
                        "--env-file",
                        str(env_path),
                        "--db",
                        str(db_path),
                        "--dry-run",
                        "recover-diagnostic-incident",
                        "--worker",
                        "worker",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(dry_exit.exception.code, 0)
            self.assertEqual(payload["status"], "would_dispatch")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(store.list_recoveries(), [])

            error = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                redirect_stderr(error),
                self.assertRaises(SystemExit) as real_exit,
            ):
                cli_main(
                    [
                        "--env-file",
                        str(env_path),
                        "--db",
                        str(db_path),
                        "recover-diagnostic-incident",
                        "--worker",
                        "worker",
                    ]
                )
            self.assertEqual(real_exit.exception.code, 1)
            self.assertIn("authorize-once", error.getvalue())
            self.assertEqual(store.list_recoveries(), [])


class RecoveryStoreTests(unittest.TestCase):
    def test_reservation_completion_and_stale_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            _, store, _, diagnosis, incident = create_recovery_incident(db_path)
            recovery, created = store.reserve_recovery(
                incident_id=incident.incident_id,
                diagnosis_id=diagnosis.diagnosis_id,
                action=RECOVERY_ACTION,
                now=200,
            )
            duplicate, duplicate_created = store.reserve_recovery(
                incident_id=incident.incident_id,
                diagnosis_id=diagnosis.diagnosis_id,
                action=RECOVERY_ACTION,
                now=201,
            )
            self.assertTrue(created)
            self.assertFalse(duplicate_created)
            self.assertEqual(duplicate, recovery)
            with self.assertRaisesRegex(ValueError, "cannot remain pending"):
                store.complete_recovery(
                    recovery.recovery_id,
                    status=RecoveryStatus.PENDING,
                )
            with self.assertRaisesRegex(ValueError, "requires a failure code"):
                store.complete_recovery(
                    recovery.recovery_id,
                    status=RecoveryStatus.UNCERTAIN,
                )
            completed = store.complete_recovery(
                recovery.recovery_id,
                status=RecoveryStatus.INPUT_EMITTED,
                failure_code="ignored",
                now=202,
            )
            self.assertEqual(completed.status, RecoveryStatus.INPUT_EMITTED)
            self.assertIsNone(completed.failure_code)
            self.assertEqual(store.list_recoveries(status="input_emitted"), [completed])
            with self.assertRaisesRegex(ValueError, "Pending recovery not found"):
                store.complete_recovery(
                    recovery.recovery_id,
                    status=RecoveryStatus.INPUT_EMITTED,
                )

    def test_reservation_rejects_stale_diagnosis_and_resolved_incident(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            _, store, _, old_diagnosis, incident = create_recovery_incident(db_path)
            evidence = store.record_evidence(
                worker_id="worker",
                session_id="session-a",
                source=EvidenceSource.PROCESS,
                kind=EvidenceKind.PROCESS_STATE,
                state="missing",
                observed_at=200,
                expires_at=500,
            )
            current_diagnosis = store.record_diagnosis(
                worker_id="worker",
                session_id="session-a",
                kind=DiagnosisKind.CODEX_CLOSED,
                confidence=DiagnosisConfidence.MEDIUM,
                summary="Current diagnosis.",
                evidence_ids=(evidence.evidence_id,),
                diagnosed_at=201,
                valid_until=500,
            )
            current_incident = store.open_or_update_incident(
                diagnosis_id=current_diagnosis.diagnosis_id,
                severity=IncidentSeverity.ORANGE,
                now=202,
            )
            self.assertEqual(current_incident.incident_id, incident.incident_id)

            with self.assertRaisesRegex(ValueError, "not current"):
                store.reserve_recovery(
                    incident_id=incident.incident_id,
                    diagnosis_id=old_diagnosis.diagnosis_id,
                    action=RECOVERY_ACTION,
                    now=203,
                )

            store.resolve_incident(
                incident.incident_id,
                resolution="healthy",
                now=204,
            )
            with self.assertRaisesRegex(ValueError, "Open incident not found"):
                store.reserve_recovery(
                    incident_id=incident.incident_id,
                    diagnosis_id=current_diagnosis.diagnosis_id,
                    action=RECOVERY_ACTION,
                    now=205,
                )

            self.assertEqual(store.list_recoveries(), [])


if __name__ == "__main__":
    unittest.main()
