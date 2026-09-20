from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.cli import main as cli_main
from ai_presence_monitor.diagnostic_notifications import (
    DiagnosticDiscordClient,
    DiscordDeliveryRejected,
    DiscordDeliveryUncertain,
    build_diagnostic_discord_payload,
    diagnostic_event_key,
    notify_diagnostic_incident,
)
from ai_presence_monitor.diagnostics import (
    DiagnosisConfidence,
    DiagnosisKind,
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
    IncidentSeverity,
    NotificationDeliveryStatus,
)
from ai_presence_monitor.store import PresenceStore


class FakeResponse:
    def __init__(self, status: int = 204) -> None:
        self.status = status
        self.read_size: int | None = None

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        self.read_size = size
        return b""


class RecordingSender:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dict[str, object]]] = []

    def send(self, url: str, payload: dict[str, object]) -> None:
        self.calls.append((url, payload))
        if self.error is not None:
            raise self.error


def create_worker(db_path: Path, worker_id: str = "worker") -> None:
    PresenceStore(db_path).record_event(
        worker_id=worker_id,
        computer="computer`name",
        ia_name="codex",
        protocol="protocol2",
        event_type="start",
        task="task",
    )


def create_open_incident(
    db_path: Path,
    *,
    worker_id: str = "worker",
    kind: DiagnosisKind = DiagnosisKind.USAGE_LIMIT_EXCEEDED,
    confidence: DiagnosisConfidence = DiagnosisConfidence.HIGH,
    severity: IncidentSeverity = IncidentSeverity.YELLOW,
    now: float = 100,
):
    create_worker(db_path, worker_id)
    store = DiagnosticStore(db_path)
    evidence = store.record_evidence(
        worker_id=worker_id,
        session_id="session-a",
        source=EvidenceSource.CODEX_APP_SERVER,
        kind=EvidenceKind.ACCOUNT_LIMIT,
        state="rate_limit_reached",
        summary="Bounded evidence.",
        observed_at=now - 2,
        expires_at=now + 600,
    )
    diagnosis = store.record_diagnosis(
        worker_id=worker_id,
        session_id="session-a",
        kind=kind,
        confidence=confidence,
        summary=f"Diagnosis for {kind.value}.",
        evidence_ids=(evidence.evidence_id,),
        diagnosed_at=now - 1,
        valid_until=now + 600,
    )
    incident = store.open_or_update_incident(
        diagnosis_id=diagnosis.diagnosis_id,
        severity=severity,
        now=now,
    )
    return store, diagnosis, incident


def update_incident(
    store: DiagnosticStore,
    *,
    worker_id: str = "worker",
    kind: DiagnosisKind,
    confidence: DiagnosisConfidence,
    severity: IncidentSeverity,
    now: float,
):
    evidence = store.record_evidence(
        worker_id=worker_id,
        session_id="session-a",
        source=EvidenceSource.PROCESS,
        kind=EvidenceKind.PROCESS_STATE,
        state="missing",
        observed_at=now - 2,
        expires_at=now + 600,
    )
    diagnosis = store.record_diagnosis(
        worker_id=worker_id,
        session_id="session-a",
        kind=kind,
        confidence=confidence,
        summary=f"Diagnosis for {kind.value}.",
        evidence_ids=(evidence.evidence_id,),
        diagnosed_at=now - 1,
        valid_until=now + 600,
    )
    incident = store.open_or_update_incident(
        diagnosis_id=diagnosis.diagnosis_id,
        severity=severity,
        now=now,
    )
    return diagnosis, incident


class DiagnosticDiscordClientTests(unittest.TestCase):
    def test_client_posts_bounded_json_once(self) -> None:
        response = FakeResponse()
        client = DiagnosticDiscordClient(timeout_seconds=7)
        with patch(
            "ai_presence_monitor.diagnostic_notifications.urllib.request.urlopen",
            return_value=response,
        ) as urlopen:
            client.send("https://example.invalid/webhook", {"message": "test"})

        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {"message": "test"})
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(request.headers["User-agent"], "ai-presence-monitor/0.8.0")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 7)
        self.assertEqual(response.read_size, 1024)

    def test_client_distinguishes_rejection_from_uncertainty(self) -> None:
        client = DiagnosticDiscordClient()
        http_error = urllib.error.HTTPError(
            "https://example.invalid",
            403,
            "forbidden",
            {},
            io.BytesIO(),
        )
        with patch(
            "ai_presence_monitor.diagnostic_notifications.urllib.request.urlopen",
            side_effect=http_error,
        ):
            with self.assertRaises(DiscordDeliveryRejected):
                client.send("https://example.invalid", {})

        with patch(
            "ai_presence_monitor.diagnostic_notifications.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaises(DiscordDeliveryUncertain):
                client.send("https://example.invalid", {})

        with patch(
            "ai_presence_monitor.diagnostic_notifications.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            with self.assertRaises(DiscordDeliveryUncertain):
                client.send("https://example.invalid", {})

        with patch(
            "ai_presence_monitor.diagnostic_notifications.urllib.request.urlopen",
            return_value=FakeResponse(status=500),
        ):
            with self.assertRaises(DiscordDeliveryRejected):
                client.send("https://example.invalid", {})

    def test_client_rejects_nonpositive_timeout(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            DiagnosticDiscordClient(timeout_seconds=0)


class DiagnosticNotificationWorkflowTests(unittest.TestCase):
    def test_payload_disables_mentions_and_sanitizes_display_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            _, diagnosis, incident = create_open_incident(db_path)
            worker = PresenceStore(db_path).get_worker("worker")
            assert worker is not None

            payload = build_diagnostic_discord_payload(
                worker=worker,
                incident=incident,
                diagnosis=diagnosis,
            )

            self.assertEqual(payload["allowed_mentions"], {"parse": []})
            embed = payload["embeds"][0]  # type: ignore[index]
            fields = embed["fields"]  # type: ignore[index]
            self.assertEqual(fields[1]["value"], "computer'name")
            self.assertEqual(embed["description"], diagnosis.summary)  # type: ignore[index]

    def test_success_marks_delivery_and_incident_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store, diagnosis, incident = create_open_incident(db_path)
            sender = RecordingSender()

            result = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=sender,
                now=200,
            )

            self.assertEqual(result.status, "delivered")
            self.assertEqual(len(sender.calls), 1)
            notification = store.require_notification(result.notification_id or "")
            self.assertEqual(notification.status, NotificationDeliveryStatus.DELIVERED)
            self.assertEqual(notification.delivered_at, 200)
            self.assertEqual(store.require_incident(incident.incident_id).last_notified_at, 200)
            self.assertEqual(result.event_key, diagnostic_event_key(incident, diagnosis))

    def test_same_semantics_are_deduplicated_across_diagnosis_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store, _, _ = create_open_incident(db_path)
            first_sender = RecordingSender()
            first = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=first_sender,
                now=200,
            )
            update_incident(
                store,
                kind=DiagnosisKind.USAGE_LIMIT_EXCEEDED,
                confidence=DiagnosisConfidence.HIGH,
                severity=IncidentSeverity.YELLOW,
                now=210,
            )
            second_sender = RecordingSender()

            second = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=second_sender,
                now=220,
            )

            self.assertEqual(first.status, "delivered")
            self.assertEqual(second.status, "deduplicated")
            self.assertEqual(len(first_sender.calls), 1)
            self.assertEqual(second_sender.calls, [])
            self.assertEqual(len(store.list_notifications()), 1)

    def test_cause_or_severity_change_creates_one_new_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store, _, _ = create_open_incident(db_path)
            sender = RecordingSender()
            notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=sender,
                now=200,
            )
            update_incident(
                store,
                kind=DiagnosisKind.CODEX_CLOSED,
                confidence=DiagnosisConfidence.MEDIUM,
                severity=IncidentSeverity.ORANGE,
                now=210,
            )

            changed = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=sender,
                now=220,
            )
            repeated = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=sender,
                now=230,
            )

            self.assertEqual(changed.status, "delivered")
            self.assertEqual(repeated.status, "deduplicated")
            self.assertEqual(len(sender.calls), 2)
            self.assertEqual(len(store.list_notifications()), 2)

    def test_red_uses_dedicated_webhook_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            create_open_incident(db_path, severity=IncidentSeverity.RED)
            sender = RecordingSender()

            result = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                discord_red_webhook_url="https://example.invalid/red",
                sender=sender,
                now=200,
            )

            self.assertEqual(result.status, "delivered")
            self.assertEqual(sender.calls[0][0], "https://example.invalid/red")

    def test_red_falls_back_to_alert_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            create_open_incident(db_path, severity=IncidentSeverity.RED)
            sender = RecordingSender()

            notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=sender,
                now=200,
            )

            self.assertEqual(sender.calls[0][0], "https://example.invalid/alert")

    def test_rejected_and_uncertain_attempts_are_not_automatically_retried(self) -> None:
        cases = (
            (
                DiscordDeliveryRejected("rejected"),
                "rejected",
                NotificationDeliveryStatus.REJECTED,
                "discord_webhook_rejected",
            ),
            (
                DiscordDeliveryUncertain("uncertain"),
                "uncertain",
                NotificationDeliveryStatus.UNCERTAIN,
                "discord_delivery_uncertain",
            ),
        )
        for error, result_status, stored_status, failure_code in cases:
            with self.subTest(status=result_status), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "presence.db"
                store, _, incident = create_open_incident(db_path)
                sender = RecordingSender(error)
                first = notify_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    discord_alert_webhook_url="https://example.invalid/alert",
                    sender=sender,
                    now=200,
                )
                retry_sender = RecordingSender()
                second = notify_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    discord_alert_webhook_url="https://example.invalid/alert",
                    sender=retry_sender,
                    now=210,
                )

                notification = store.require_notification(first.notification_id or "")
                self.assertEqual(first.status, result_status)
                self.assertEqual(second.status, "deduplicated")
                self.assertEqual(notification.status, stored_status)
                self.assertEqual(notification.failure_code, failure_code)
                self.assertIsNone(store.require_incident(incident.incident_id).last_notified_at)
                self.assertEqual(len(sender.calls), 1)
                self.assertEqual(retry_sender.calls, [])

    def test_unexpected_interruption_leaves_pending_and_suppresses_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store, _, _ = create_open_incident(db_path)
            with self.assertRaisesRegex(RuntimeError, "process stopped"):
                notify_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    discord_alert_webhook_url="https://example.invalid/alert",
                    sender=RecordingSender(RuntimeError("process stopped")),
                    now=200,
                )

            notifications = store.list_notifications()
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0].status, NotificationDeliveryStatus.PENDING)
            retry_sender = RecordingSender()
            result = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                sender=retry_sender,
                now=210,
            )
            self.assertEqual(result.status, "deduplicated")
            self.assertEqual(retry_sender.calls, [])

    def test_dry_run_and_missing_webhook_write_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store, _, _ = create_open_incident(db_path)
            sender = RecordingSender()
            result = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url="https://example.invalid/alert",
                dry_run=True,
                sender=sender,
                now=200,
            )
            self.assertEqual(result.status, "would_send")
            self.assertEqual(store.list_notifications(), [])
            self.assertEqual(sender.calls, [])

            with self.assertRaisesRegex(ValueError, "not configured"):
                notify_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    discord_alert_webhook_url=None,
                    now=210,
                )
            self.assertEqual(store.list_notifications(), [])

    def test_no_incident_and_inactive_worker_fail_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            create_worker(db_path)
            result = notify_diagnostic_incident(
                db_path=db_path,
                worker_id="worker",
                discord_alert_webhook_url=None,
                dry_run=True,
            )
            self.assertEqual(result.status, "no_open_incident")

            PresenceStore(db_path).record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="finish",
            )
            with self.assertRaisesRegex(ValueError, "not active"):
                notify_diagnostic_incident(
                    db_path=db_path,
                    worker_id="worker",
                    discord_alert_webhook_url=None,
                    dry_run=True,
                )

    def test_missing_worker_and_invalid_timeout_fail_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            sender = RecordingSender()
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                notify_diagnostic_incident(
                    db_path=db_path,
                    worker_id="missing",
                    discord_alert_webhook_url="https://example.invalid/alert",
                    timeout_seconds=0,
                    sender=sender,
                )
            with self.assertRaisesRegex(ValueError, "Worker not found"):
                notify_diagnostic_incident(
                    db_path=db_path,
                    worker_id="missing",
                    discord_alert_webhook_url="https://example.invalid/alert",
                    sender=sender,
                )
            self.assertEqual(sender.calls, [])

    def test_cli_dry_run_emits_json_without_network_or_ledger_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "presence.db"
            env_path = root / ".env"
            env_path.write_text(
                "DISCORD_ALERT_WEBHOOK_URL=https://example.invalid/alert\n",
                encoding="utf-8",
            )
            store, _, _ = create_open_incident(db_path)
            output = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "ai_presence_monitor.diagnostic_notifications.urllib.request.urlopen"
                ) as urlopen,
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
                        "notify-diagnostic-incident",
                        "--worker",
                        "worker",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(raised.exception.code, 0)
            self.assertEqual(payload["status"], "would_send")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(store.list_notifications(), [])
            urlopen.assert_not_called()


class DiagnosticNotificationStoreTests(unittest.TestCase):
    def test_store_validates_reservation_and_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store, diagnosis, incident = create_open_incident(db_path)
            notification, created = store.reserve_notification(
                incident_id=incident.incident_id,
                diagnosis_id=diagnosis.diagnosis_id,
                event_key="v1|usage_limit_exceeded|high|yellow",
                now=200,
            )
            duplicate, duplicate_created = store.reserve_notification(
                incident_id=incident.incident_id,
                diagnosis_id=diagnosis.diagnosis_id,
                event_key=notification.event_key,
                now=201,
            )

            self.assertTrue(created)
            self.assertFalse(duplicate_created)
            self.assertEqual(duplicate, notification)
            with self.assertRaisesRegex(ValueError, "cannot remain pending"):
                store.complete_notification(
                    notification.notification_id,
                    status=NotificationDeliveryStatus.PENDING,
                )
            with self.assertRaisesRegex(ValueError, "requires a failure code"):
                store.complete_notification(
                    notification.notification_id,
                    status=NotificationDeliveryStatus.REJECTED,
                )
            completed = store.complete_notification(
                notification.notification_id,
                status=NotificationDeliveryStatus.REJECTED,
                failure_code="discord_webhook_rejected",
                now=202,
            )
            self.assertEqual(completed.status, NotificationDeliveryStatus.REJECTED)
            self.assertEqual(
                store.list_notifications(status="rejected"),
                [completed],
            )
            with self.assertRaisesRegex(ValueError, "Pending notification not found"):
                store.complete_notification(
                    notification.notification_id,
                    status=NotificationDeliveryStatus.DELIVERED,
                    now=203,
                )

    def test_reservation_rejects_stale_diagnosis_or_resolved_incident(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store, diagnosis, incident = create_open_incident(db_path)
            replacement, updated = update_incident(
                store,
                kind=DiagnosisKind.CODEX_CLOSED,
                confidence=DiagnosisConfidence.MEDIUM,
                severity=IncidentSeverity.ORANGE,
                now=200,
            )
            self.assertEqual(updated.incident_id, incident.incident_id)
            with self.assertRaisesRegex(ValueError, "not current"):
                store.reserve_notification(
                    incident_id=incident.incident_id,
                    diagnosis_id=diagnosis.diagnosis_id,
                    event_key="stale",
                )
            store.resolve_incident(
                incident.incident_id,
                resolution="resolved",
                now=210,
            )
            with self.assertRaisesRegex(ValueError, "Open incident not found"):
                store.reserve_notification(
                    incident_id=incident.incident_id,
                    diagnosis_id=replacement.diagnosis_id,
                    event_key="resolved",
                )


if __name__ == "__main__":
    unittest.main()
