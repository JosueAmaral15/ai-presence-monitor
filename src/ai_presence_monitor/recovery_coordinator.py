from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .codex_input import (
    CodexInputError,
    CodexInputResult,
    CodexQueueClient,
    is_current_codex_session,
)
from .control import ControlSettings
from .diagnostic_notifications import diagnostic_event_key
from .diagnostics import (
    Diagnosis,
    DiagnosisConfidence,
    DiagnosisKind,
    DiagnosticIncident,
    DiagnosticRecovery,
    DiagnosticStore,
    IncidentStatus,
    NotificationDeliveryStatus,
    RecoveryStatus,
)
from .store import PresenceStore

RECOVERY_ACTION = "native_continue"
_RECOVERABLE_CONFIDENCE = {
    DiagnosisKind.CODEX_CLOSED: frozenset(
        {DiagnosisConfidence.MEDIUM, DiagnosisConfidence.HIGH}
    ),
    DiagnosisKind.CODEX_CRASHED: frozenset({DiagnosisConfidence.HIGH}),
}


class NativeRecoveryClient(Protocol):
    def is_available(self) -> bool: ...

    def send(
        self,
        *,
        thread_id: str,
        text: str,
        remote: str | None = None,
        remote_auth_token_env: str | None = None,
        detached: bool = False,
    ) -> CodexInputResult: ...


@dataclass(frozen=True)
class RecoveryResult:
    worker_id: str
    status: str
    incident_id: str | None
    diagnosis_id: str | None
    recovery_id: str | None
    diagnosis_kind: str | None
    confidence: str | None
    severity: str | None
    session_id: str | None
    stored_status: str | None


def recover_diagnostic_incident(
    *,
    db_path: Path,
    worker_id: str,
    controls: ControlSettings,
    message: str,
    authorized: bool = False,
    dry_run: bool = False,
    client: NativeRecoveryClient | None = None,
    now: float | None = None,
) -> RecoveryResult:
    timestamp = time.time() if now is None else now
    if not math.isfinite(timestamp):
        raise ValueError("now must be a finite timestamp.")
    text = _message(message)
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

    _validate_eligibility(
        incident=incident,
        diagnosis=diagnosis,
        now=timestamp,
    )
    notification = store.find_notification(
        incident_id=incident.incident_id,
        event_key=diagnostic_event_key(incident, diagnosis),
    )
    if (
        notification is None
        or notification.status is not NotificationDeliveryStatus.DELIVERED
    ):
        raise ValueError(
            "Recovery requires confirmed Discord delivery for the current "
            "diagnostic event."
        )

    existing = store.find_recovery(
        incident_id=incident.incident_id,
        action=RECOVERY_ACTION,
    )
    if existing is not None:
        return _result(
            worker_id=worker_id,
            status="deduplicated",
            incident=incident,
            diagnosis=diagnosis,
            recovery=existing,
        )

    if not controls.native_input_enabled:
        raise ValueError("Native input is disabled.")
    if dry_run:
        return _result(
            worker_id=worker_id,
            status="would_dispatch",
            incident=incident,
            diagnosis=diagnosis,
        )
    if not authorized:
        raise ValueError("Recovery requires --authorize-once for this invocation.")

    native_client = client or CodexQueueClient()
    if not native_client.is_available():
        raise ValueError("The Codex executable is not available in PATH.")

    recovery, created = store.reserve_recovery(
        incident_id=incident.incident_id,
        diagnosis_id=diagnosis.diagnosis_id,
        action=RECOVERY_ACTION,
        now=timestamp,
    )
    if not created:
        return _result(
            worker_id=worker_id,
            status="deduplicated",
            incident=incident,
            diagnosis=diagnosis,
            recovery=recovery,
        )

    assert incident.session_id is not None
    try:
        dispatch = native_client.send(
            thread_id=incident.session_id,
            text=text,
            detached=is_current_codex_session(incident.session_id),
        )
    except CodexInputError:
        recovery = store.complete_recovery(
            recovery.recovery_id,
            status=RecoveryStatus.UNCERTAIN,
            failure_code="codex_input_uncertain",
            now=timestamp,
        )
        return _result(
            worker_id=worker_id,
            status=RecoveryStatus.UNCERTAIN.value,
            incident=incident,
            diagnosis=diagnosis,
            recovery=recovery,
        )

    recovery = store.complete_recovery(
        recovery.recovery_id,
        status=RecoveryStatus(dispatch.state),
        now=timestamp,
    )
    return _result(
        worker_id=worker_id,
        status=dispatch.state,
        incident=incident,
        diagnosis=diagnosis,
        recovery=recovery,
    )


def _validate_eligibility(
    *,
    incident: DiagnosticIncident,
    diagnosis: Diagnosis,
    now: float,
) -> None:
    allowed_confidence = _RECOVERABLE_CONFIDENCE.get(diagnosis.kind)
    if allowed_confidence is None or diagnosis.confidence not in allowed_confidence:
        raise ValueError(
            "Diagnosis is not eligible for native recovery: "
            f"{diagnosis.kind.value}/{diagnosis.confidence.value}."
        )
    if diagnosis.valid_until is not None and diagnosis.valid_until < now:
        raise ValueError("The current diagnosis expired before recovery.")
    if incident.session_id is None or diagnosis.session_id is None:
        raise ValueError("Recovery requires an exact persisted Codex session.")
    if incident.session_id != diagnosis.session_id:
        raise ValueError("Incident and diagnosis sessions do not match.")


def _message(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError("Recovery message cannot be empty.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise ValueError("Recovery message must be a single line.")
    if len(clean) > 2000:
        raise ValueError("Recovery message cannot exceed 2000 characters.")
    return clean


def _result(
    *,
    worker_id: str,
    status: str,
    incident: DiagnosticIncident | None = None,
    diagnosis: Diagnosis | None = None,
    recovery: DiagnosticRecovery | None = None,
) -> RecoveryResult:
    return RecoveryResult(
        worker_id=worker_id,
        status=status,
        incident_id=incident.incident_id if incident else None,
        diagnosis_id=diagnosis.diagnosis_id if diagnosis else None,
        recovery_id=recovery.recovery_id if recovery else None,
        diagnosis_kind=diagnosis.kind.value if diagnosis else None,
        confidence=diagnosis.confidence.value if diagnosis else None,
        severity=incident.severity.value if incident else None,
        session_id=incident.session_id if incident else None,
        stored_status=recovery.status.value if recovery else None,
    )
