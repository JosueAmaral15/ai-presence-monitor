from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .diagnostics import (
    Diagnosis,
    DiagnosisConfidence,
    DiagnosisKind,
    DiagnosticEvidence,
    DiagnosticIncident,
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
    IncidentSeverity,
    IncidentStatus,
)
from .protocols import choose_threshold, get_protocol
from .store import PresenceStore, WorkerState


@dataclass(frozen=True)
class DiagnosisAssessment:
    kind: DiagnosisKind
    confidence: DiagnosisConfidence
    summary: str
    evidence: tuple[DiagnosticEvidence, ...]


@dataclass(frozen=True)
class DiagnosisResult:
    worker_id: str
    session_id: str | None
    age_seconds: float
    severity: IncidentSeverity
    assessment: DiagnosisAssessment
    transition: str
    diagnosis: Diagnosis | None
    incident: DiagnosticIncident | None


_USAGE_LIMIT_STATES = frozenset(
    {
        "account_limit_reached",
        "ordinary_usage_blocked",
        "rate_limit_reached",
        "spend_control_reached",
        "workspace_member_credits_depleted",
        "workspace_member_usage_limit_reached",
        "workspace_owner_credits_depleted",
        "workspace_owner_usage_limit_reached",
    }
)
_WAITING_FOR_APPROVAL_STATES = frozenset(
    {"approval_required", "awaiting_approval", "waiting_for_approval"}
)
_WAITING_FOR_USER_STATES = frozenset(
    {"awaiting_user", "question_pending", "waiting_for_user"}
)
_CONTEXT_LIMIT_STATES = frozenset(
    {"context_length_exceeded", "context_window_exceeded", "max_context_reached"}
)
_LONG_RUNNING_STATES = frozenset({"started", "subagent_started", "tool_started"})
_WORKING_STATES = frozenset(
    {
        "completed",
        "presence_within_threshold",
        "prompt_submitted",
        "session_started",
        "subagent_stopped",
        "tool_completed",
    }
)
_HEALTHY_DIAGNOSES = frozenset(
    {DiagnosisKind.WORKING, DiagnosisKind.LONG_RUNNING_OPERATION}
)


def select_current_evidence(
    evidence: Iterable[DiagnosticEvidence],
    *,
    session_id: str | None = None,
) -> tuple[DiagnosticEvidence, ...]:
    records = tuple(evidence)
    if session_id is None:
        sessions = {item.session_id for item in records if item.session_id is not None}
        if len(sessions) > 1:
            raise ValueError(
                "Current diagnostic evidence spans multiple Codex sessions; "
                "provide --session."
            )
        selected_session = next(iter(sessions), None)
    else:
        selected_session = session_id

    eligible = tuple(
        item
        for item in records
        if item.session_id is None or item.session_id == selected_session
    )
    newest: dict[tuple[EvidenceSource, EvidenceKind], float] = {}
    for item in eligible:
        key = (item.source, item.kind)
        newest[key] = max(newest.get(key, item.observed_at), item.observed_at)

    current = (
        item
        for item in eligible
        if item.observed_at == newest[(item.source, item.kind)]
    )
    return tuple(
        sorted(
            current,
            key=lambda item: (
                -item.observed_at,
                item.source.value,
                item.kind.value,
                item.state,
                item.evidence_id,
            ),
        )
    )


def assess_diagnosis(
    evidence: Iterable[DiagnosticEvidence],
    *,
    overdue: bool,
) -> DiagnosisAssessment:
    records = tuple(evidence)
    if not records:
        raise ValueError("A diagnosis assessment requires current evidence.")

    if not overdue:
        supporting = _matching(records, states={"presence_within_threshold"})
        return _assessment(
            DiagnosisKind.WORKING,
            DiagnosisConfidence.HIGH,
            "The worker presence clock remains within its protocol threshold.",
            supporting or records[:1],
        )

    checks = (
        (
            DiagnosisKind.USAGE_LIMIT_EXCEEDED,
            DiagnosisConfidence.HIGH,
            "Codex reported an account or usage limit while the worker was overdue.",
            _matching(records, kinds={EvidenceKind.ACCOUNT_LIMIT}, states=_USAGE_LIMIT_STATES),
        ),
        (
            DiagnosisKind.WAITING_FOR_APPROVAL,
            DiagnosisConfidence.HIGH,
            "Codex reported that the worker is waiting for approval.",
            _matching(records, states=_WAITING_FOR_APPROVAL_STATES),
        ),
        (
            DiagnosisKind.WAITING_FOR_USER,
            DiagnosisConfidence.HIGH,
            "Codex reported that the worker is waiting for user input.",
            _matching(records, states=_WAITING_FOR_USER_STATES),
        ),
        (
            DiagnosisKind.CONTEXT_WINDOW_EXCEEDED,
            DiagnosisConfidence.HIGH,
            "Codex reported that the context window was exceeded.",
            _matching(records, states=_CONTEXT_LIMIT_STATES),
        ),
        (
            DiagnosisKind.CODEX_CRASHED,
            DiagnosisConfidence.HIGH,
            "The selected Codex process is a zombie.",
            _matching(
                records,
                kinds={EvidenceKind.PROCESS_STATE},
                states={"zombie"},
            ),
        ),
        (
            DiagnosisKind.CODEX_CLOSED,
            DiagnosisConfidence.MEDIUM,
            "The selected Codex process or session is no longer present.",
            (
                *_matching(
                    records,
                    kinds={EvidenceKind.PROCESS_STATE},
                    states={"dead", "missing"},
                ),
                *_matching(
                    records,
                    kinds={EvidenceKind.THREAD_STATUS},
                    states={"session_ended"},
                ),
            ),
        ),
        (
            DiagnosisKind.SYSTEM_SUSPENDED,
            DiagnosisConfidence.MEDIUM,
            "Linux reported a resume gap that can explain the inactivity interval.",
            _matching(
                records,
                kinds={EvidenceKind.POWER_STATE},
                states={"resume_detected"},
            ),
        ),
        (
            DiagnosisKind.OBSERVER_UNHEALTHY,
            DiagnosisConfidence.HIGH,
            "A required diagnostic service failed or is not installed.",
            _matching(
                records,
                kinds={EvidenceKind.SERVICE_STATE},
                states={"failed", "not_found"},
            ),
        ),
        (
            DiagnosisKind.OBSERVER_UNHEALTHY,
            DiagnosisConfidence.MEDIUM,
            "A selected observer target is unavailable or cannot be identified.",
            (
                *_matching(
                    records,
                    kinds={EvidenceKind.PROCESS_STATE},
                    states={"identity_mismatch", "replaced", "unreadable"},
                ),
                *_matching(
                    records,
                    kinds={EvidenceKind.SERVICE_STATE},
                    states={"deactivating", "inactive"},
                ),
            ),
        ),
        (
            DiagnosisKind.OBSERVER_UNHEALTHY,
            DiagnosisConfidence.LOW,
            "A required diagnostic service could not report a known state.",
            _matching(
                records,
                kinds={EvidenceKind.SERVICE_STATE},
                states={"unknown"},
            ),
        ),
        (
            DiagnosisKind.NETWORK_UNAVAILABLE,
            DiagnosisConfidence.MEDIUM,
            "Linux reports no usable local network path; upstream access is unverified.",
            _matching(
                records,
                kinds={EvidenceKind.NETWORK_STATE},
                states={"default_route_link_down", "no_usable_link"},
            ),
        ),
        (
            DiagnosisKind.NETWORK_UNAVAILABLE,
            DiagnosisConfidence.LOW,
            "Linux reports no local default route; upstream access is unverified.",
            _matching(
                records,
                kinds={EvidenceKind.NETWORK_STATE},
                states={"link_up_no_default_route"},
            ),
        ),
        (
            DiagnosisKind.LONG_RUNNING_OPERATION,
            DiagnosisConfidence.MEDIUM,
            "Recent Codex evidence indicates a recognized long-running operation.",
            _matching(records, states=_LONG_RUNNING_STATES),
        ),
        (
            DiagnosisKind.WORKING,
            DiagnosisConfidence.HIGH,
            "Recent Codex hook evidence indicates worker activity.",
            _matching(records, states=_WORKING_STATES - {"presence_within_threshold"}),
        ),
    )
    for kind, confidence, summary, supporting in checks:
        if supporting:
            return _assessment(
                kind,
                confidence,
                summary,
                _with_overdue_context(records, supporting),
            )

    threshold = _matching(records, states={"presence_threshold_exceeded"})
    return _assessment(
        DiagnosisKind.UNEXPLAINED_INACTIVITY,
        DiagnosisConfidence.LOW,
        "The worker is overdue, but current evidence does not establish a specific cause.",
        threshold or records,
    )


def diagnose_worker(
    *,
    db_path: Path,
    worker_id: str,
    session_id: str | None = None,
    now: float | None = None,
    dry_run: bool = False,
    presence_ttl_seconds: int = 60,
) -> DiagnosisResult:
    if presence_ttl_seconds <= 0:
        raise ValueError("Presence diagnosis TTL must be greater than zero.")
    timestamp = time.time() if now is None else now
    worker = PresenceStore(db_path).get_worker(worker_id)
    if worker is None:
        raise ValueError(f"Worker not found: {worker_id}. Run start before diagnosis.")
    if worker.status != "active":
        raise ValueError(f"Worker is not active: {worker_id}.")

    age_seconds, severity = _worker_age_and_severity(worker, timestamp)
    overdue = severity is not IncidentSeverity.INFO
    store = DiagnosticStore(db_path)
    existing = store.list_evidence(worker_id=worker_id, valid_at=timestamp, limit=100)
    selected = select_current_evidence(existing, session_id=session_id)
    selected_session = _selected_session(selected, session_id)
    presence = DiagnosticEvidence(
        evidence_id="dry-run-presence" if dry_run else "pending-presence",
        worker_id=worker_id,
        session_id=selected_session,
        source=EvidenceSource.WORKSPACE,
        kind=EvidenceKind.WORKSPACE_STATE,
        state="presence_threshold_exceeded" if overdue else "presence_within_threshold",
        summary=(
            "The worker presence clock exceeded its protocol threshold."
            if overdue
            else "The worker presence clock remains within its protocol threshold."
        ),
        observed_at=timestamp,
        expires_at=timestamp + presence_ttl_seconds,
    )
    current = select_current_evidence((*selected, presence), session_id=selected_session)
    assessment = assess_diagnosis(current, overdue=overdue)
    open_incident = _open_incident(store, worker_id)

    if dry_run:
        transition = _planned_transition(assessment.kind, open_incident)
        return DiagnosisResult(
            worker_id=worker_id,
            session_id=selected_session,
            age_seconds=age_seconds,
            severity=severity,
            assessment=assessment,
            transition=transition,
            diagnosis=None,
            incident=open_incident,
        )

    persisted_presence = store.record_evidence(
        worker_id=presence.worker_id,
        session_id=presence.session_id,
        source=presence.source,
        kind=presence.kind,
        state=presence.state,
        summary=presence.summary,
        observed_at=presence.observed_at,
        expires_at=presence.expires_at,
    )
    persisted_current = tuple(
        persisted_presence if item.evidence_id == presence.evidence_id else item
        for item in current
    )
    assessment = assess_diagnosis(persisted_current, overdue=overdue)
    valid_until = _valid_until(assessment.evidence)
    diagnosis = store.record_diagnosis(
        worker_id=worker_id,
        session_id=selected_session,
        kind=assessment.kind,
        confidence=assessment.confidence,
        summary=assessment.summary,
        evidence_ids=tuple(item.evidence_id for item in assessment.evidence),
        diagnosed_at=timestamp,
        valid_until=valid_until,
    )

    if assessment.kind in _HEALTHY_DIAGNOSES:
        if open_incident is None:
            transition = "none"
            incident = None
        else:
            transition = "resolved"
            incident = store.resolve_incident(
                open_incident.incident_id,
                resolution="Current diagnostic evidence indicates worker activity.",
                now=timestamp,
            )
    else:
        transition = "opened" if open_incident is None else "updated"
        incident = store.open_or_update_incident(
            diagnosis_id=diagnosis.diagnosis_id,
            severity=severity,
            now=timestamp,
        )

    return DiagnosisResult(
        worker_id=worker_id,
        session_id=selected_session,
        age_seconds=age_seconds,
        severity=severity,
        assessment=assessment,
        transition=transition,
        diagnosis=diagnosis,
        incident=incident,
    )


def _matching(
    evidence: tuple[DiagnosticEvidence, ...],
    *,
    kinds: set[EvidenceKind] | None = None,
    states: set[str] | frozenset[str],
) -> tuple[DiagnosticEvidence, ...]:
    return tuple(
        item
        for item in evidence
        if (kinds is None or item.kind in kinds) and item.state in states
    )


def _assessment(
    kind: DiagnosisKind,
    confidence: DiagnosisConfidence,
    summary: str,
    evidence: tuple[DiagnosticEvidence, ...],
) -> DiagnosisAssessment:
    return DiagnosisAssessment(kind, confidence, summary, evidence)


def _with_overdue_context(
    records: tuple[DiagnosticEvidence, ...],
    supporting: tuple[DiagnosticEvidence, ...],
) -> tuple[DiagnosticEvidence, ...]:
    threshold = _matching(records, states={"presence_threshold_exceeded"})
    return tuple(dict.fromkeys((*supporting, *threshold)))


def _selected_session(
    evidence: tuple[DiagnosticEvidence, ...],
    requested: str | None,
) -> str | None:
    if requested is not None:
        return requested
    return next((item.session_id for item in evidence if item.session_id is not None), None)


def _worker_age_and_severity(
    worker: WorkerState,
    now: float,
) -> tuple[float, IncidentSeverity]:
    protocol = get_protocol(worker.protocol)
    if protocol.monitored_clock == "last_signal_at":
        clock = worker.last_signal_at
    else:
        clock = worker.last_activity_at or worker.last_signal_at
    age_seconds = float("inf") if clock is None else max(0.0, now - clock)
    threshold = choose_threshold(protocol, age_seconds)
    severity = IncidentSeverity.INFO if threshold is None else IncidentSeverity(threshold.level)
    return age_seconds, severity


def _open_incident(store: DiagnosticStore, worker_id: str) -> DiagnosticIncident | None:
    incidents = store.list_incidents(
        worker_id=worker_id,
        status=IncidentStatus.OPEN,
        limit=1,
    )
    return incidents[0] if incidents else None


def _planned_transition(
    kind: DiagnosisKind,
    incident: DiagnosticIncident | None,
) -> str:
    if kind in _HEALTHY_DIAGNOSES:
        return "resolved" if incident is not None else "none"
    return "opened" if incident is None else "updated"


def _valid_until(evidence: tuple[DiagnosticEvidence, ...]) -> float | None:
    expiries = [item.expires_at for item in evidence if item.expires_at is not None]
    return min(expiries) if expiries else None
