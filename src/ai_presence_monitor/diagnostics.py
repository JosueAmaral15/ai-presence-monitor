from __future__ import annotations

import math
import sqlite3
import time
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class EvidenceSource(str, Enum):
    CODEX_APP_SERVER = "codex_app_server"
    CODEX_HOOK = "codex_hook"
    PROCESS = "process"
    NETWORK = "network"
    POWER = "power"
    INTERACTION = "interaction"
    SERVICE = "service"
    WORKSPACE = "workspace"


class EvidenceKind(str, Enum):
    ACTIVITY = "activity"
    TURN_STATUS = "turn_status"
    THREAD_STATUS = "thread_status"
    CODEX_ERROR = "codex_error"
    TOKEN_USAGE = "token_usage"
    ACCOUNT_LIMIT = "account_limit"
    CONTEXT_COMPACTION = "context_compaction"
    PROCESS_STATE = "process_state"
    NETWORK_STATE = "network_state"
    POWER_STATE = "power_state"
    INTERACTION_STATE = "interaction_state"
    SERVICE_STATE = "service_state"
    WORKSPACE_STATE = "workspace_state"


class DiagnosisKind(str, Enum):
    WORKING = "working"
    LONG_RUNNING_OPERATION = "long_running_operation"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    USAGE_LIMIT_EXCEEDED = "usage_limit_exceeded"
    CONTEXT_WINDOW_EXCEEDED = "context_window_exceeded"
    NETWORK_UNAVAILABLE = "network_unavailable"
    CODEX_CLOSED = "codex_closed"
    CODEX_CRASHED = "codex_crashed"
    SYSTEM_SUSPENDED = "system_suspended"
    OBSERVER_UNHEALTHY = "observer_unhealthy"
    UNEXPLAINED_INACTIVITY = "unexplained_inactivity"


class DiagnosisConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IncidentSeverity(str, Enum):
    INFO = "info"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class IncidentStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class NotificationDeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class DiagnosticEvidence:
    evidence_id: str
    worker_id: str
    session_id: str | None
    source: EvidenceSource
    kind: EvidenceKind
    state: str
    summary: str | None
    observed_at: float
    expires_at: float | None


@dataclass(frozen=True)
class Diagnosis:
    diagnosis_id: str
    worker_id: str
    session_id: str | None
    kind: DiagnosisKind
    confidence: DiagnosisConfidence
    summary: str
    evidence_ids: tuple[str, ...]
    diagnosed_at: float
    valid_until: float | None


@dataclass(frozen=True)
class DiagnosticIncident:
    incident_id: str
    worker_id: str
    session_id: str | None
    status: IncidentStatus
    severity: IncidentSeverity
    current_diagnosis_id: str
    opened_at: float
    updated_at: float
    resolved_at: float | None
    resolution: str | None
    last_notified_at: float | None


@dataclass(frozen=True)
class DiagnosticNotification:
    notification_id: str
    incident_id: str
    diagnosis_id: str
    event_key: str
    channel: str
    status: NotificationDeliveryStatus
    attempted_at: float
    delivered_at: float | None
    failure_code: str | None


def initialize_diagnostic_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_evidence (
            evidence_id TEXT PRIMARY KEY,
            worker_id TEXT NOT NULL,
            session_id TEXT,
            source TEXT NOT NULL,
            kind TEXT NOT NULL,
            state TEXT NOT NULL,
            summary TEXT,
            observed_at REAL NOT NULL,
            expires_at REAL,
            CHECK (expires_at IS NULL OR expires_at >= observed_at)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_diagnostic_evidence_worker_time
        ON diagnostic_evidence(worker_id, observed_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_diagnostic_evidence_session_time
        ON diagnostic_evidence(session_id, observed_at DESC)
        WHERE session_id IS NOT NULL
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_diagnoses (
            diagnosis_id TEXT PRIMARY KEY,
            worker_id TEXT NOT NULL,
            session_id TEXT,
            kind TEXT NOT NULL,
            confidence TEXT NOT NULL,
            summary TEXT NOT NULL,
            diagnosed_at REAL NOT NULL,
            valid_until REAL,
            CHECK (valid_until IS NULL OR valid_until >= diagnosed_at)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_diagnostic_diagnoses_worker_time
        ON diagnostic_diagnoses(worker_id, diagnosed_at DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_diagnosis_evidence (
            diagnosis_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (diagnosis_id, evidence_id),
            UNIQUE (diagnosis_id, position),
            FOREIGN KEY (diagnosis_id)
                REFERENCES diagnostic_diagnoses(diagnosis_id) ON DELETE CASCADE,
            FOREIGN KEY (evidence_id)
                REFERENCES diagnostic_evidence(evidence_id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_incidents (
            incident_id TEXT PRIMARY KEY,
            worker_id TEXT NOT NULL,
            session_id TEXT,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            current_diagnosis_id TEXT NOT NULL,
            opened_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            resolved_at REAL,
            resolution TEXT,
            last_notified_at REAL,
            FOREIGN KEY (current_diagnosis_id)
                REFERENCES diagnostic_diagnoses(diagnosis_id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_diagnostic_incidents_open_worker
        ON diagnostic_incidents(worker_id)
        WHERE status = 'open'
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_diagnostic_incidents_status_time
        ON diagnostic_incidents(status, updated_at DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_notifications (
            notification_id TEXT PRIMARY KEY,
            incident_id TEXT NOT NULL,
            diagnosis_id TEXT NOT NULL,
            event_key TEXT NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL,
            attempted_at REAL NOT NULL,
            delivered_at REAL,
            failure_code TEXT,
            UNIQUE (incident_id, event_key, channel),
            FOREIGN KEY (incident_id)
                REFERENCES diagnostic_incidents(incident_id) ON DELETE RESTRICT,
            FOREIGN KEY (diagnosis_id)
                REFERENCES diagnostic_diagnoses(diagnosis_id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_diagnostic_notifications_status_time
        ON diagnostic_notifications(status, attempted_at DESC)
        """
    )


class DiagnosticStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.session() as conn:
            initialize_diagnostic_schema(conn)

    def record_evidence(
        self,
        *,
        worker_id: str,
        source: EvidenceSource | str,
        kind: EvidenceKind | str,
        state: str,
        session_id: str | None = None,
        summary: str | None = None,
        observed_at: float | None = None,
        expires_at: float | None = None,
    ) -> DiagnosticEvidence:
        timestamp = time.time() if observed_at is None else _timestamp(
            observed_at,
            "observed_at",
        )
        expiry = None if expires_at is None else _timestamp(expires_at, "expires_at")
        if expiry is not None and expiry < timestamp:
            raise ValueError("expires_at cannot be earlier than observed_at.")

        evidence = DiagnosticEvidence(
            evidence_id=str(uuid.uuid4()),
            worker_id=_identifier(worker_id, "worker_id"),
            session_id=_optional_identifier(session_id, "session_id"),
            source=_enum_value(EvidenceSource, source, "evidence source"),
            kind=_enum_value(EvidenceKind, kind, "evidence kind"),
            state=_identifier(state, "evidence state", max_length=120),
            summary=_optional_summary(summary),
            observed_at=timestamp,
            expires_at=expiry,
        )
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO diagnostic_evidence (
                    evidence_id, worker_id, session_id, source, kind, state,
                    summary, observed_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.evidence_id,
                    evidence.worker_id,
                    evidence.session_id,
                    evidence.source.value,
                    evidence.kind.value,
                    evidence.state,
                    evidence.summary,
                    evidence.observed_at,
                    evidence.expires_at,
                ),
            )
        return evidence

    def get_evidence(self, evidence_id: str) -> DiagnosticEvidence | None:
        clean_id = _identifier(evidence_id, "evidence_id")
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM diagnostic_evidence WHERE evidence_id = ?",
                (clean_id,),
            ).fetchone()
        return self._row_to_evidence(row) if row else None

    def list_evidence(
        self,
        *,
        worker_id: str,
        session_id: str | None = None,
        valid_at: float | None = None,
        limit: int = 100,
    ) -> list[DiagnosticEvidence]:
        clean_worker = _identifier(worker_id, "worker_id")
        clean_session = _optional_identifier(session_id, "session_id")
        checked_at = None if valid_at is None else _timestamp(valid_at, "valid_at")
        safe_limit = _limit(limit)
        clauses = ["worker_id = ?"]
        params: list[object] = [clean_worker]
        if clean_session is not None:
            clauses.append("session_id = ?")
            params.append(clean_session)
        if checked_at is not None:
            clauses.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(checked_at)
        params.append(safe_limit)
        with self.session() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM diagnostic_evidence
                WHERE {' AND '.join(clauses)}
                ORDER BY observed_at DESC, evidence_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    def record_diagnosis(
        self,
        *,
        worker_id: str,
        kind: DiagnosisKind | str,
        confidence: DiagnosisConfidence | str,
        summary: str,
        evidence_ids: Sequence[str],
        session_id: str | None = None,
        diagnosed_at: float | None = None,
        valid_until: float | None = None,
    ) -> Diagnosis:
        clean_worker = _identifier(worker_id, "worker_id")
        clean_session = _optional_identifier(session_id, "session_id")
        linked_ids = tuple(
            dict.fromkeys(_identifier(item, "evidence_id") for item in evidence_ids)
        )
        if not linked_ids:
            raise ValueError("A diagnosis requires at least one evidence record.")
        timestamp = time.time() if diagnosed_at is None else _timestamp(
            diagnosed_at,
            "diagnosed_at",
        )
        validity = (
            None if valid_until is None else _timestamp(valid_until, "valid_until")
        )
        if validity is not None and validity < timestamp:
            raise ValueError("valid_until cannot be earlier than diagnosed_at.")

        placeholders = ", ".join("?" for _ in linked_ids)
        with self.session() as conn:
            rows = conn.execute(
                f"""
                SELECT evidence_id, worker_id, session_id
                FROM diagnostic_evidence
                WHERE evidence_id IN ({placeholders})
                """,
                linked_ids,
            ).fetchall()
            found = {row["evidence_id"] for row in rows}
            missing = [item for item in linked_ids if item not in found]
            if missing:
                raise ValueError(f"Diagnostic evidence not found: {missing[0]}")
            if any(row["worker_id"] != clean_worker for row in rows):
                raise ValueError("Diagnosis evidence must belong to the same worker.")

            evidence_sessions = {
                row["session_id"] for row in rows if row["session_id"] is not None
            }
            if clean_session is None:
                if len(evidence_sessions) > 1:
                    raise ValueError("Diagnosis evidence spans multiple Codex sessions.")
                clean_session = next(iter(evidence_sessions), None)
            elif any(value != clean_session for value in evidence_sessions):
                raise ValueError("Diagnosis evidence belongs to another Codex session.")

            diagnosis = Diagnosis(
                diagnosis_id=str(uuid.uuid4()),
                worker_id=clean_worker,
                session_id=clean_session,
                kind=_enum_value(DiagnosisKind, kind, "diagnosis kind"),
                confidence=_enum_value(
                    DiagnosisConfidence,
                    confidence,
                    "diagnosis confidence",
                ),
                summary=_summary(summary),
                evidence_ids=linked_ids,
                diagnosed_at=timestamp,
                valid_until=validity,
            )
            conn.execute(
                """
                INSERT INTO diagnostic_diagnoses (
                    diagnosis_id, worker_id, session_id, kind, confidence,
                    summary, diagnosed_at, valid_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diagnosis.diagnosis_id,
                    diagnosis.worker_id,
                    diagnosis.session_id,
                    diagnosis.kind.value,
                    diagnosis.confidence.value,
                    diagnosis.summary,
                    diagnosis.diagnosed_at,
                    diagnosis.valid_until,
                ),
            )
            conn.executemany(
                """
                INSERT INTO diagnostic_diagnosis_evidence (
                    diagnosis_id, evidence_id, position
                ) VALUES (?, ?, ?)
                """,
                (
                    (diagnosis.diagnosis_id, evidence_id, position)
                    for position, evidence_id in enumerate(linked_ids)
                ),
            )
        return diagnosis

    def get_diagnosis(self, diagnosis_id: str) -> Diagnosis | None:
        clean_id = _identifier(diagnosis_id, "diagnosis_id")
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM diagnostic_diagnoses WHERE diagnosis_id = ?",
                (clean_id,),
            ).fetchone()
            if row is None:
                return None
            evidence_rows = conn.execute(
                """
                SELECT evidence_id
                FROM diagnostic_diagnosis_evidence
                WHERE diagnosis_id = ?
                ORDER BY position
                """,
                (clean_id,),
            ).fetchall()
        return self._row_to_diagnosis(
            row,
            tuple(item["evidence_id"] for item in evidence_rows),
        )

    def list_diagnoses(
        self,
        *,
        worker_id: str,
        limit: int = 100,
    ) -> list[Diagnosis]:
        clean_worker = _identifier(worker_id, "worker_id")
        safe_limit = _limit(limit)
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM diagnostic_diagnoses
                WHERE worker_id = ?
                ORDER BY diagnosed_at DESC, diagnosis_id DESC
                LIMIT ?
                """,
                (clean_worker, safe_limit),
            ).fetchall()
            result = []
            for row in rows:
                evidence_rows = conn.execute(
                    """
                    SELECT evidence_id
                    FROM diagnostic_diagnosis_evidence
                    WHERE diagnosis_id = ?
                    ORDER BY position
                    """,
                    (row["diagnosis_id"],),
                ).fetchall()
                result.append(
                    self._row_to_diagnosis(
                        row,
                        tuple(item["evidence_id"] for item in evidence_rows),
                    )
                )
        return result

    def open_or_update_incident(
        self,
        *,
        diagnosis_id: str,
        severity: IncidentSeverity | str,
        now: float | None = None,
    ) -> DiagnosticIncident:
        diagnosis = self.get_diagnosis(diagnosis_id)
        if diagnosis is None:
            raise ValueError(f"Diagnosis not found: {diagnosis_id}")
        timestamp = time.time() if now is None else _timestamp(now, "now")
        normalized_severity = _enum_value(
            IncidentSeverity,
            severity,
            "incident severity",
        )
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT * FROM diagnostic_incidents
                WHERE worker_id = ? AND status = 'open'
                """,
                (diagnosis.worker_id,),
            ).fetchone()
            if row is None:
                incident_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO diagnostic_incidents (
                        incident_id, worker_id, session_id, status, severity,
                        current_diagnosis_id, opened_at, updated_at, resolved_at,
                        resolution, last_notified_at
                    ) VALUES (?, ?, ?, 'open', ?, ?, ?, ?, NULL, NULL, NULL)
                    """,
                    (
                        incident_id,
                        diagnosis.worker_id,
                        diagnosis.session_id,
                        normalized_severity.value,
                        diagnosis.diagnosis_id,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                incident_id = row["incident_id"]
                conn.execute(
                    """
                    UPDATE diagnostic_incidents
                    SET session_id = ?, severity = ?, current_diagnosis_id = ?,
                        updated_at = ?
                    WHERE incident_id = ? AND status = 'open'
                    """,
                    (
                        diagnosis.session_id,
                        normalized_severity.value,
                        diagnosis.diagnosis_id,
                        timestamp,
                        incident_id,
                    ),
                )
        return self.require_incident(incident_id)

    def get_incident(self, incident_id: str) -> DiagnosticIncident | None:
        clean_id = _identifier(incident_id, "incident_id")
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM diagnostic_incidents WHERE incident_id = ?",
                (clean_id,),
            ).fetchone()
        return self._row_to_incident(row) if row else None

    def require_incident(self, incident_id: str) -> DiagnosticIncident:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise ValueError(f"Incident not found: {incident_id}")
        return incident

    def list_incidents(
        self,
        *,
        worker_id: str | None = None,
        status: IncidentStatus | str | None = None,
        limit: int = 100,
    ) -> list[DiagnosticIncident]:
        clauses: list[str] = []
        params: list[object] = []
        if worker_id is not None:
            clauses.append("worker_id = ?")
            params.append(_identifier(worker_id, "worker_id"))
        if status is not None:
            clauses.append("status = ?")
            params.append(_enum_value(IncidentStatus, status, "incident status").value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(_limit(limit))
        with self.session() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM diagnostic_incidents
                {where}
                ORDER BY updated_at DESC, incident_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_incident(row) for row in rows]

    def mark_incident_notified(
        self,
        incident_id: str,
        *,
        now: float | None = None,
    ) -> DiagnosticIncident:
        clean_id = _identifier(incident_id, "incident_id")
        timestamp = time.time() if now is None else _timestamp(now, "now")
        with self.session() as conn:
            cursor = conn.execute(
                """
                UPDATE diagnostic_incidents
                SET last_notified_at = ?, updated_at = ?
                WHERE incident_id = ? AND status = 'open'
                """,
                (timestamp, timestamp, clean_id),
            )
        if cursor.rowcount != 1:
            raise ValueError(f"Open incident not found: {clean_id}")
        return self.require_incident(clean_id)

    def resolve_incident(
        self,
        incident_id: str,
        *,
        resolution: str,
        now: float | None = None,
    ) -> DiagnosticIncident:
        clean_id = _identifier(incident_id, "incident_id")
        timestamp = time.time() if now is None else _timestamp(now, "now")
        clean_resolution = _summary(resolution)
        with self.session() as conn:
            cursor = conn.execute(
                """
                UPDATE diagnostic_incidents
                SET status = 'resolved', resolved_at = ?, resolution = ?,
                    updated_at = ?
                WHERE incident_id = ? AND status = 'open'
                """,
                (timestamp, clean_resolution, timestamp, clean_id),
            )
        if cursor.rowcount != 1:
            raise ValueError(f"Open incident not found: {clean_id}")
        return self.require_incident(clean_id)

    def find_notification(
        self,
        *,
        incident_id: str,
        event_key: str,
        channel: str = "discord",
    ) -> DiagnosticNotification | None:
        clean_incident = _identifier(incident_id, "incident_id")
        clean_event = _identifier(event_key, "notification event key")
        clean_channel = _identifier(channel, "notification channel", max_length=40)
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT * FROM diagnostic_notifications
                WHERE incident_id = ? AND event_key = ? AND channel = ?
                """,
                (clean_incident, clean_event, clean_channel),
            ).fetchone()
        return self._row_to_notification(row) if row else None

    def reserve_notification(
        self,
        *,
        incident_id: str,
        diagnosis_id: str,
        event_key: str,
        channel: str = "discord",
        now: float | None = None,
    ) -> tuple[DiagnosticNotification, bool]:
        clean_incident = _identifier(incident_id, "incident_id")
        clean_diagnosis = _identifier(diagnosis_id, "diagnosis_id")
        clean_event = _identifier(event_key, "notification event key")
        clean_channel = _identifier(channel, "notification channel", max_length=40)
        timestamp = time.time() if now is None else _timestamp(now, "now")
        notification_id = str(uuid.uuid4())
        with self.session() as conn:
            incident = conn.execute(
                """
                SELECT status, current_diagnosis_id
                FROM diagnostic_incidents
                WHERE incident_id = ?
                """,
                (clean_incident,),
            ).fetchone()
            if incident is None or incident["status"] != IncidentStatus.OPEN.value:
                raise ValueError(f"Open incident not found: {clean_incident}")
            if incident["current_diagnosis_id"] != clean_diagnosis:
                raise ValueError("Notification diagnosis is not current for the incident.")
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO diagnostic_notifications (
                    notification_id, incident_id, diagnosis_id, event_key,
                    channel, status, attempted_at, delivered_at, failure_code
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, NULL)
                """,
                (
                    notification_id,
                    clean_incident,
                    clean_diagnosis,
                    clean_event,
                    clean_channel,
                    timestamp,
                ),
            )
            created = cursor.rowcount == 1
            row = conn.execute(
                """
                SELECT * FROM diagnostic_notifications
                WHERE incident_id = ? AND event_key = ? AND channel = ?
                """,
                (clean_incident, clean_event, clean_channel),
            ).fetchone()
        assert row is not None
        return self._row_to_notification(row), created

    def complete_notification(
        self,
        notification_id: str,
        *,
        status: NotificationDeliveryStatus | str,
        failure_code: str | None = None,
        now: float | None = None,
    ) -> DiagnosticNotification:
        clean_id = _identifier(notification_id, "notification_id")
        normalized_status = _enum_value(
            NotificationDeliveryStatus,
            status,
            "notification status",
        )
        if normalized_status is NotificationDeliveryStatus.PENDING:
            raise ValueError("A completed notification cannot remain pending.")
        clean_failure = _optional_identifier(
            failure_code,
            "notification failure code",
        )
        if normalized_status is NotificationDeliveryStatus.DELIVERED:
            clean_failure = None
        elif clean_failure is None:
            raise ValueError("A failed notification requires a failure code.")
        timestamp = time.time() if now is None else _timestamp(now, "now")
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT incident_id FROM diagnostic_notifications
                WHERE notification_id = ? AND status = 'pending'
                """,
                (clean_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Pending notification not found: {clean_id}")
            conn.execute(
                """
                UPDATE diagnostic_notifications
                SET status = ?, delivered_at = ?, failure_code = ?
                WHERE notification_id = ? AND status = 'pending'
                """,
                (
                    normalized_status.value,
                    timestamp
                    if normalized_status is NotificationDeliveryStatus.DELIVERED
                    else None,
                    clean_failure,
                    clean_id,
                ),
            )
            if normalized_status is NotificationDeliveryStatus.DELIVERED:
                conn.execute(
                    """
                    UPDATE diagnostic_incidents
                    SET last_notified_at = ?
                    WHERE incident_id = ?
                    """,
                    (timestamp, row["incident_id"]),
                )
        return self.require_notification(clean_id)

    def get_notification(self, notification_id: str) -> DiagnosticNotification | None:
        clean_id = _identifier(notification_id, "notification_id")
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM diagnostic_notifications WHERE notification_id = ?",
                (clean_id,),
            ).fetchone()
        return self._row_to_notification(row) if row else None

    def require_notification(self, notification_id: str) -> DiagnosticNotification:
        notification = self.get_notification(notification_id)
        if notification is None:
            raise ValueError(f"Notification not found: {notification_id}")
        return notification

    def list_notifications(
        self,
        *,
        incident_id: str | None = None,
        status: NotificationDeliveryStatus | str | None = None,
        limit: int = 100,
    ) -> list[DiagnosticNotification]:
        clauses: list[str] = []
        params: list[object] = []
        if incident_id is not None:
            clauses.append("incident_id = ?")
            params.append(_identifier(incident_id, "incident_id"))
        if status is not None:
            clauses.append("status = ?")
            params.append(
                _enum_value(
                    NotificationDeliveryStatus,
                    status,
                    "notification status",
                ).value
            )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(_limit(limit))
        with self.session() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM diagnostic_notifications
                {where}
                ORDER BY attempted_at DESC, notification_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_notification(row) for row in rows]

    @staticmethod
    def _row_to_evidence(row: sqlite3.Row) -> DiagnosticEvidence:
        return DiagnosticEvidence(
            evidence_id=row["evidence_id"],
            worker_id=row["worker_id"],
            session_id=row["session_id"],
            source=EvidenceSource(row["source"]),
            kind=EvidenceKind(row["kind"]),
            state=row["state"],
            summary=row["summary"],
            observed_at=row["observed_at"],
            expires_at=row["expires_at"],
        )

    @staticmethod
    def _row_to_diagnosis(
        row: sqlite3.Row,
        evidence_ids: tuple[str, ...],
    ) -> Diagnosis:
        return Diagnosis(
            diagnosis_id=row["diagnosis_id"],
            worker_id=row["worker_id"],
            session_id=row["session_id"],
            kind=DiagnosisKind(row["kind"]),
            confidence=DiagnosisConfidence(row["confidence"]),
            summary=row["summary"],
            evidence_ids=evidence_ids,
            diagnosed_at=row["diagnosed_at"],
            valid_until=row["valid_until"],
        )

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> DiagnosticIncident:
        return DiagnosticIncident(
            incident_id=row["incident_id"],
            worker_id=row["worker_id"],
            session_id=row["session_id"],
            status=IncidentStatus(row["status"]),
            severity=IncidentSeverity(row["severity"]),
            current_diagnosis_id=row["current_diagnosis_id"],
            opened_at=row["opened_at"],
            updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
            resolution=row["resolution"],
            last_notified_at=row["last_notified_at"],
        )

    @staticmethod
    def _row_to_notification(row: sqlite3.Row) -> DiagnosticNotification:
        return DiagnosticNotification(
            notification_id=row["notification_id"],
            incident_id=row["incident_id"],
            diagnosis_id=row["diagnosis_id"],
            event_key=row["event_key"],
            channel=row["channel"],
            status=NotificationDeliveryStatus(row["status"]),
            attempted_at=row["attempted_at"],
            delivered_at=row["delivered_at"],
            failure_code=row["failure_code"],
        )


def _enum_value(enum_type: type[Enum], value: Enum | str, label: str):
    try:
        return enum_type(value)
    except ValueError as exc:
        choices = ", ".join(item.value for item in enum_type)
        raise ValueError(f"Unknown {label}: {value!r}. Use: {choices}.") from exc


def _identifier(value: str, label: str, *, max_length: int = 255) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError(f"{label} cannot be empty.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise ValueError(f"{label} must be a single line.")
    if len(clean) > max_length:
        raise ValueError(f"{label} cannot exceed {max_length} characters.")
    return clean


def _optional_identifier(value: str | None, label: str) -> str | None:
    if value is None or not value.strip():
        return None
    return _identifier(value, label)


def _summary(value: str) -> str:
    clean = " ".join(value.split())
    if not clean:
        raise ValueError("Diagnostic summary cannot be empty.")
    if "\x00" in clean:
        raise ValueError("Diagnostic summary cannot contain NUL.")
    if len(clean) > 500:
        raise ValueError("Diagnostic summary cannot exceed 500 characters.")
    return clean


def _optional_summary(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return _summary(value)


def _timestamp(value: float, label: str) -> float:
    timestamp = float(value)
    if not math.isfinite(timestamp):
        raise ValueError(f"{label} must be a finite timestamp.")
    return timestamp


def _limit(value: int) -> int:
    if value <= 0 or value > 1000:
        raise ValueError("limit must be between 1 and 1000.")
    return value
