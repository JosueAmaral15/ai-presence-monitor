from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from . import __version__
from .diagnostics import (
    Diagnosis,
    DiagnosticIncident,
    DiagnosticNotification,
    DiagnosticStore,
    IncidentSeverity,
    IncidentStatus,
    NotificationDeliveryStatus,
)
from .store import PresenceStore, WorkerState


class DiscordDeliveryRejected(RuntimeError):
    pass


class DiscordDeliveryUncertain(RuntimeError):
    pass


class DiscordSender(Protocol):
    def send(self, url: str, payload: dict[str, object]) -> None: ...


@dataclass(frozen=True)
class DiagnosticNotificationResult:
    worker_id: str
    status: str
    event_key: str | None
    incident_id: str | None
    diagnosis_id: str | None
    notification_id: str | None
    diagnosis_kind: str | None
    confidence: str | None
    severity: str | None


class DiagnosticDiscordClient:
    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Diagnostic notification timeout must be greater than zero.")
        self.timeout_seconds = timeout_seconds

    def send(self, url: str, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"ai-presence-monitor/{__version__}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                status = getattr(response, "status", 200)
                response.read(1024)
        except urllib.error.HTTPError as exc:
            exc.close()
            raise DiscordDeliveryRejected("discord_webhook_rejected") from exc
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            raise DiscordDeliveryUncertain("discord_delivery_uncertain") from exc
        if not 200 <= status < 300:
            raise DiscordDeliveryRejected("discord_webhook_rejected")


def diagnostic_event_key(
    incident: DiagnosticIncident,
    diagnosis: Diagnosis,
) -> str:
    return "|".join(
        (
            "v1",
            diagnosis.kind.value,
            diagnosis.confidence.value,
            incident.severity.value,
        )
    )


def build_diagnostic_discord_payload(
    *,
    worker: WorkerState,
    incident: DiagnosticIncident,
    diagnosis: Diagnosis,
) -> dict[str, object]:
    severity = incident.severity.value
    title = f"Diagnostic incident: {severity.upper()}"
    fields = [
        {"name": "Worker", "value": _discord_text(worker.worker_id), "inline": False},
        {"name": "Computer", "value": _discord_text(worker.computer), "inline": True},
        {"name": "AI", "value": _discord_text(worker.ia_name), "inline": True},
        {"name": "Protocol", "value": _discord_text(worker.protocol), "inline": True},
        {"name": "Cause", "value": diagnosis.kind.value, "inline": True},
        {"name": "Confidence", "value": diagnosis.confidence.value, "inline": True},
    ]
    return {
        "content": title,
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": title,
                "description": diagnosis.summary,
                "color": _severity_color(incident.severity),
                "fields": fields,
                "timestamp": datetime.fromtimestamp(
                    diagnosis.diagnosed_at,
                    timezone.utc,
                )
                .isoformat()
                .replace("+00:00", "Z"),
            }
        ],
    }


def notify_diagnostic_incident(
    *,
    db_path: Path,
    worker_id: str,
    discord_alert_webhook_url: str | None,
    discord_red_webhook_url: str | None = None,
    dry_run: bool = False,
    timeout_seconds: float = 15.0,
    sender: DiscordSender | None = None,
    now: float | None = None,
) -> DiagnosticNotificationResult:
    if timeout_seconds <= 0:
        raise ValueError("Diagnostic notification timeout must be greater than zero.")
    timestamp = time.time() if now is None else now
    worker = PresenceStore(db_path).get_worker(worker_id)
    if worker is None:
        raise ValueError(f"Worker not found: {worker_id}.")
    if worker.status != "active":
        raise ValueError(f"Worker is not active: {worker_id}.")

    store = DiagnosticStore(db_path)
    incidents = store.list_incidents(
        worker_id=worker_id,
        status=IncidentStatus.OPEN,
        limit=1,
    )
    if not incidents:
        return _result(worker_id=worker_id, status="no_open_incident")
    incident = incidents[0]
    diagnosis = store.get_diagnosis(incident.current_diagnosis_id)
    if diagnosis is None:
        raise ValueError(f"Diagnosis not found: {incident.current_diagnosis_id}")

    event_key = diagnostic_event_key(incident, diagnosis)
    existing = store.find_notification(
        incident_id=incident.incident_id,
        event_key=event_key,
    )
    if existing is not None:
        return _result(
            worker_id=worker_id,
            status="deduplicated",
            incident=incident,
            diagnosis=diagnosis,
            notification=existing,
            event_key=event_key,
        )

    webhook_url = (
        discord_red_webhook_url
        if incident.severity is IncidentSeverity.RED and discord_red_webhook_url
        else discord_alert_webhook_url
    )
    if not webhook_url:
        raise ValueError("Discord diagnostic webhook is not configured.")
    payload = build_diagnostic_discord_payload(
        worker=worker,
        incident=incident,
        diagnosis=diagnosis,
    )
    if dry_run:
        return _result(
            worker_id=worker_id,
            status="would_send",
            incident=incident,
            diagnosis=diagnosis,
            event_key=event_key,
        )

    notification, created = store.reserve_notification(
        incident_id=incident.incident_id,
        diagnosis_id=diagnosis.diagnosis_id,
        event_key=event_key,
        now=timestamp,
    )
    if not created:
        return _result(
            worker_id=worker_id,
            status="deduplicated",
            incident=incident,
            diagnosis=diagnosis,
            notification=notification,
            event_key=event_key,
        )

    client = sender or DiagnosticDiscordClient(timeout_seconds=timeout_seconds)
    try:
        client.send(webhook_url, payload)
    except DiscordDeliveryRejected:
        notification = store.complete_notification(
            notification.notification_id,
            status=NotificationDeliveryStatus.REJECTED,
            failure_code="discord_webhook_rejected",
            now=timestamp,
        )
        delivery_status = "rejected"
    except DiscordDeliveryUncertain:
        notification = store.complete_notification(
            notification.notification_id,
            status=NotificationDeliveryStatus.UNCERTAIN,
            failure_code="discord_delivery_uncertain",
            now=timestamp,
        )
        delivery_status = "uncertain"
    else:
        notification = store.complete_notification(
            notification.notification_id,
            status=NotificationDeliveryStatus.DELIVERED,
            now=timestamp,
        )
        delivery_status = "delivered"

    return _result(
        worker_id=worker_id,
        status=delivery_status,
        incident=incident,
        diagnosis=diagnosis,
        notification=notification,
        event_key=event_key,
    )


def _result(
    *,
    worker_id: str,
    status: str,
    incident: DiagnosticIncident | None = None,
    diagnosis: Diagnosis | None = None,
    notification: DiagnosticNotification | None = None,
    event_key: str | None = None,
) -> DiagnosticNotificationResult:
    return DiagnosticNotificationResult(
        worker_id=worker_id,
        status=status,
        event_key=event_key,
        incident_id=incident.incident_id if incident else None,
        diagnosis_id=diagnosis.diagnosis_id if diagnosis else None,
        notification_id=notification.notification_id if notification else None,
        diagnosis_kind=diagnosis.kind.value if diagnosis else None,
        confidence=diagnosis.confidence.value if diagnosis else None,
        severity=incident.severity.value if incident else None,
    )


def _discord_text(value: str) -> str:
    return value.replace("`", "'")[:1024]


def _severity_color(severity: IncidentSeverity) -> int:
    return {
        IncidentSeverity.INFO: 0x95A5A6,
        IncidentSeverity.YELLOW: 0xF1C40F,
        IncidentSeverity.ORANGE: 0xE67E22,
        IncidentSeverity.RED: 0xE74C3C,
    }[severity]
