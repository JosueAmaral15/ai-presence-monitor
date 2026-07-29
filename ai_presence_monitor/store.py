from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkerState:
    worker_id: str
    computer: str
    ia_name: str
    protocol: str
    status: str
    current_task: str | None
    last_signal_at: float | None
    last_activity_at: float | None
    last_message: str | None
    last_alert_level: str | None
    last_alert_at: float | None
    updated_at: float


@dataclass(frozen=True)
class RemoteQuestion:
    question_id: str
    worker_id: str
    prompt: str
    status: str
    channel_id: str | None
    external_message_id: str | None
    answer: str | None
    answered_by: str | None
    reply_message_id: str | None
    target_window_id: str | None
    target_window_title: str | None
    target_window_pattern: str | None
    created_at: float
    expires_at: float
    answered_at: float | None
    input_emitted_at: float | None
    delivery_confirmed_at: float | None
    last_error: str | None
    updated_at: float


class PresenceStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    computer TEXT NOT NULL,
                    ia_name TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_task TEXT,
                    last_signal_at REAL,
                    last_activity_at REAL,
                    last_message TEXT,
                    last_alert_level TEXT,
                    last_alert_at REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(workers)").fetchall()
            }
            if "last_alert_at" not in columns:
                conn.execute("ALTER TABLE workers ADD COLUMN last_alert_at REAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    occurred_at REAL NOT NULL,
                    message TEXT,
                    task TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    level TEXT NOT NULL,
                    triggered_at REAL NOT NULL,
                    signal_age_seconds REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                UPDATE workers
                SET last_alert_at = (
                    SELECT MAX(alerts.triggered_at)
                    FROM alerts
                    WHERE alerts.worker_id = workers.worker_id
                )
                WHERE last_alert_at IS NULL
                  AND last_alert_level IS NOT NULL
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS remote_questions (
                    question_id TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    channel_id TEXT,
                    external_message_id TEXT UNIQUE,
                    answer TEXT,
                    answered_by TEXT,
                    reply_message_id TEXT UNIQUE,
                    target_window_id TEXT,
                    target_window_title TEXT,
                    target_window_pattern TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    answered_at REAL,
                    input_emitted_at REAL,
                    delivery_confirmed_at REAL,
                    last_error TEXT,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_remote_questions_status
                ON remote_questions(status, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS observer_state (
                    state_key TEXT PRIMARY KEY,
                    state_value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def get_worker(self, worker_id: str) -> WorkerState | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM workers WHERE worker_id = ?",
                (worker_id,),
            ).fetchone()
        return self._row_to_worker(row) if row else None

    def list_workers(self, only_active: bool = False) -> list[WorkerState]:
        query = "SELECT * FROM workers"
        params: tuple[str, ...] = ()
        if only_active:
            query += " WHERE status = ?"
            params = ("active",)
        query += " ORDER BY computer, ia_name, worker_id"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_worker(row) for row in rows]

    def record_event(
        self,
        *,
        worker_id: str,
        computer: str,
        ia_name: str,
        protocol: str,
        event_type: str,
        message: str | None = None,
        task: str | None = None,
    ) -> WorkerState:
        now = time.time()
        previous = self.get_worker(worker_id)

        status = "idle" if event_type == "finish" else "active"
        current_task = task
        if current_task is None and previous is not None:
            current_task = previous.current_task
        if event_type == "finish":
            current_task = None

        if event_type == "touch" and previous is not None:
            last_signal_at = previous.last_signal_at
        else:
            last_signal_at = now

        worker = WorkerState(
            worker_id=worker_id,
            computer=computer,
            ia_name=ia_name,
            protocol=protocol,
            status=status,
            current_task=current_task,
            last_signal_at=last_signal_at,
            last_activity_at=now,
            last_message=message,
            last_alert_level=None,
            last_alert_at=None,
            updated_at=now,
        )

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO workers (
                    worker_id, computer, ia_name, protocol, status, current_task,
                    last_signal_at, last_activity_at, last_message,
                    last_alert_level, last_alert_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    computer = excluded.computer,
                    ia_name = excluded.ia_name,
                    protocol = excluded.protocol,
                    status = excluded.status,
                    current_task = excluded.current_task,
                    last_signal_at = excluded.last_signal_at,
                    last_activity_at = excluded.last_activity_at,
                    last_message = excluded.last_message,
                    last_alert_level = excluded.last_alert_level,
                    last_alert_at = excluded.last_alert_at,
                    updated_at = excluded.updated_at
                """,
                (
                    worker.worker_id,
                    worker.computer,
                    worker.ia_name,
                    worker.protocol,
                    worker.status,
                    worker.current_task,
                    worker.last_signal_at,
                    worker.last_activity_at,
                    worker.last_message,
                    worker.last_alert_level,
                    worker.last_alert_at,
                    worker.updated_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO events (
                    worker_id, event_type, protocol, occurred_at, message, task
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (worker_id, event_type, protocol, now, message, current_task),
            )
        return worker

    def record_observation(
        self,
        *,
        worker_id: str,
        computer: str,
        ia_name: str,
        protocol: str,
        source: str,
        message: str | None = None,
        task: str | None = None,
        auto_start: bool = True,
    ) -> WorkerState | None:
        now = time.time()
        previous = self.get_worker(worker_id)
        if previous is None and not auto_start:
            return None
        if previous is not None and previous.status != "active" and not auto_start:
            return None

        current_task = task
        if current_task is None and previous is not None:
            current_task = previous.current_task

        worker = WorkerState(
            worker_id=worker_id,
            computer=computer,
            ia_name=ia_name,
            protocol=protocol,
            status="active",
            current_task=current_task,
            last_signal_at=previous.last_signal_at if previous is not None else None,
            last_activity_at=now,
            last_message=message,
            last_alert_level=None,
            last_alert_at=None,
            updated_at=now,
        )

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO workers (
                    worker_id, computer, ia_name, protocol, status, current_task,
                    last_signal_at, last_activity_at, last_message,
                    last_alert_level, last_alert_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    computer = excluded.computer,
                    ia_name = excluded.ia_name,
                    protocol = excluded.protocol,
                    status = excluded.status,
                    current_task = excluded.current_task,
                    last_activity_at = excluded.last_activity_at,
                    last_message = excluded.last_message,
                    last_alert_level = excluded.last_alert_level,
                    last_alert_at = excluded.last_alert_at,
                    updated_at = excluded.updated_at
                """,
                (
                    worker.worker_id,
                    worker.computer,
                    worker.ia_name,
                    worker.protocol,
                    worker.status,
                    worker.current_task,
                    worker.last_signal_at,
                    worker.last_activity_at,
                    worker.last_message,
                    worker.last_alert_level,
                    worker.last_alert_at,
                    worker.updated_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO events (
                    worker_id, event_type, protocol, occurred_at, message, task
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (worker_id, f"observation:{source}", protocol, now, message, current_task),
            )
        return worker

    def record_alert(
        self,
        *,
        worker_id: str,
        protocol: str,
        level: str,
        signal_age_seconds: float,
        triggered_at: float | None = None,
    ) -> None:
        now = time.time() if triggered_at is None else triggered_at
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO alerts (
                    worker_id, protocol, level, triggered_at, signal_age_seconds
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (worker_id, protocol, level, now, signal_age_seconds),
            )
            conn.execute(
                """
                UPDATE workers
                SET last_alert_level = ?, last_alert_at = ?, updated_at = ?
                WHERE worker_id = ?
                """,
                (level, now, now, worker_id),
            )

    def create_question(
        self,
        *,
        worker_id: str,
        prompt: str,
        timeout_seconds: int,
        target_window_id: str | None = None,
        target_window_title: str | None = None,
        target_window_pattern: str | None = None,
        now: float | None = None,
    ) -> RemoteQuestion:
        created_at = time.time() if now is None else now
        question = RemoteQuestion(
            question_id=str(uuid.uuid4()),
            worker_id=worker_id,
            prompt=prompt,
            status="pending",
            channel_id=None,
            external_message_id=None,
            answer=None,
            answered_by=None,
            reply_message_id=None,
            target_window_id=target_window_id,
            target_window_title=target_window_title,
            target_window_pattern=target_window_pattern,
            created_at=created_at,
            expires_at=created_at + timeout_seconds,
            answered_at=None,
            input_emitted_at=None,
            delivery_confirmed_at=None,
            last_error=None,
            updated_at=created_at,
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO remote_questions (
                    question_id, worker_id, prompt, status, channel_id,
                    external_message_id, answer, answered_by, reply_message_id,
                    target_window_id, target_window_title, target_window_pattern,
                    created_at, expires_at, answered_at, input_emitted_at,
                    delivery_confirmed_at, last_error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.question_id,
                    question.worker_id,
                    question.prompt,
                    question.status,
                    question.channel_id,
                    question.external_message_id,
                    question.answer,
                    question.answered_by,
                    question.reply_message_id,
                    question.target_window_id,
                    question.target_window_title,
                    question.target_window_pattern,
                    question.created_at,
                    question.expires_at,
                    question.answered_at,
                    question.input_emitted_at,
                    question.delivery_confirmed_at,
                    question.last_error,
                    question.updated_at,
                ),
            )
        return question

    def mark_question_published(
        self,
        question_id: str,
        *,
        channel_id: str,
        external_message_id: str,
        now: float | None = None,
    ) -> RemoteQuestion:
        updated_at = time.time() if now is None else now
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE remote_questions
                SET channel_id = ?, external_message_id = ?, updated_at = ?
                WHERE question_id = ? AND status = 'pending'
                """,
                (channel_id, external_message_id, updated_at, question_id),
            )
        if cursor.rowcount != 1:
            raise ValueError(f"Pergunta nao esta pendente: {question_id}")
        return self.require_question(question_id)

    def mark_question_error(
        self,
        question_id: str,
        *,
        status: str,
        error: str,
        allowed_statuses: tuple[str, ...],
        now: float | None = None,
    ) -> RemoteQuestion:
        updated_at = time.time() if now is None else now
        placeholders = ", ".join("?" for _ in allowed_statuses)
        params = (status, error, updated_at, question_id, *allowed_statuses)
        with self.connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE remote_questions
                SET status = ?, last_error = ?, updated_at = ?
                WHERE question_id = ? AND status IN ({placeholders})
                """,
                params,
            )
        if cursor.rowcount != 1:
            raise ValueError(f"Estado da pergunta nao permite a operacao: {question_id}")
        return self.require_question(question_id)

    def record_question_answer(
        self,
        *,
        external_message_id: str,
        channel_id: str,
        reply_message_id: str,
        answered_by: str,
        answer: str,
        now: float | None = None,
    ) -> RemoteQuestion | None:
        answered_at = time.time() if now is None else now
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM remote_questions
                WHERE external_message_id = ? AND channel_id = ?
                """,
                (external_message_id, channel_id),
            ).fetchone()
            if row is None:
                return None
            question = self._row_to_question(row)
            if question.status != "pending":
                return None
            if question.expires_at <= answered_at:
                conn.execute(
                    """
                    UPDATE remote_questions
                    SET status = 'expired', updated_at = ?
                    WHERE question_id = ? AND status = 'pending'
                    """,
                    (answered_at, question.question_id),
                )
                return None
            try:
                cursor = conn.execute(
                    """
                    UPDATE remote_questions
                    SET status = 'answered', answer = ?, answered_by = ?,
                        reply_message_id = ?, answered_at = ?, last_error = NULL,
                        updated_at = ?
                    WHERE question_id = ? AND status = 'pending'
                    """,
                    (
                        answer,
                        answered_by,
                        reply_message_id,
                        answered_at,
                        answered_at,
                        question.question_id,
                    ),
                )
            except sqlite3.IntegrityError:
                return None
        if cursor.rowcount != 1:
            return None
        return self.require_question(question.question_id)

    def mark_input_emitted(
        self,
        question_id: str,
        *,
        now: float | None = None,
        allow_retry: bool = False,
    ) -> RemoteQuestion:
        emitted_at = time.time() if now is None else now
        allowed = ("answered", "dispatch_failed") if allow_retry else ("answered",)
        placeholders = ", ".join("?" for _ in allowed)
        with self.connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE remote_questions
                SET status = 'input_emitted', input_emitted_at = ?,
                    last_error = NULL, updated_at = ?
                WHERE question_id = ? AND status IN ({placeholders})
                """,
                (emitted_at, emitted_at, question_id, *allowed),
            )
        if cursor.rowcount != 1:
            raise ValueError(f"Resposta nao esta pronta para entrega: {question_id}")
        return self.require_question(question_id)

    def confirm_deliveries(
        self,
        *,
        worker_id: str,
        observed_at: float,
        timeout_seconds: int,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE remote_questions
                SET status = 'delivery_confirmed',
                    delivery_confirmed_at = ?,
                    updated_at = ?
                WHERE worker_id = ?
                  AND status = 'input_emitted'
                  AND input_emitted_at <= ?
                  AND input_emitted_at >= ?
                """,
                (
                    observed_at,
                    observed_at,
                    worker_id,
                    observed_at,
                    observed_at - timeout_seconds,
                ),
            )
        return cursor.rowcount

    def expire_questions(self, now: float | None = None) -> int:
        checked_at = time.time() if now is None else now
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE remote_questions
                SET status = 'expired', updated_at = ?
                WHERE status = 'pending' AND expires_at <= ?
                """,
                (checked_at, checked_at),
            )
        return cursor.rowcount

    def get_question(self, question_id: str) -> RemoteQuestion | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM remote_questions WHERE question_id = ?",
                (question_id,),
            ).fetchone()
        return self._row_to_question(row) if row else None

    def require_question(self, question_id: str) -> RemoteQuestion:
        question = self.get_question(question_id)
        if question is None:
            raise ValueError(f"Pergunta nao encontrada: {question_id}")
        return question

    def list_questions(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[RemoteQuestion]:
        query = "SELECT * FROM remote_questions"
        params: tuple[object, ...]
        if status:
            query += " WHERE status = ?"
            params = (status, limit)
        else:
            params = (limit,)
        query += " ORDER BY created_at DESC LIMIT ?"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_question(row) for row in rows]

    def get_observer_state(self, key: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT state_value FROM observer_state WHERE state_key = ?",
                (key,),
            ).fetchone()
        return row["state_value"] if row else None

    def set_observer_state(
        self,
        key: str,
        value: str,
        *,
        now: float | None = None,
    ) -> None:
        updated_at = time.time() if now is None else now
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO observer_state (state_key, state_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    state_value = excluded.state_value,
                    updated_at = excluded.updated_at
                """,
                (key, value, updated_at),
            )

    @staticmethod
    def _row_to_worker(row: sqlite3.Row) -> WorkerState:
        return WorkerState(
            worker_id=row["worker_id"],
            computer=row["computer"],
            ia_name=row["ia_name"],
            protocol=row["protocol"],
            status=row["status"],
            current_task=row["current_task"],
            last_signal_at=row["last_signal_at"],
            last_activity_at=row["last_activity_at"],
            last_message=row["last_message"],
            last_alert_level=row["last_alert_level"],
            last_alert_at=row["last_alert_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_question(row: sqlite3.Row) -> RemoteQuestion:
        return RemoteQuestion(
            question_id=row["question_id"],
            worker_id=row["worker_id"],
            prompt=row["prompt"],
            status=row["status"],
            channel_id=row["channel_id"],
            external_message_id=row["external_message_id"],
            answer=row["answer"],
            answered_by=row["answered_by"],
            reply_message_id=row["reply_message_id"],
            target_window_id=row["target_window_id"],
            target_window_title=row["target_window_title"],
            target_window_pattern=row["target_window_pattern"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            answered_at=row["answered_at"],
            input_emitted_at=row["input_emitted_at"],
            delivery_confirmed_at=row["delivery_confirmed_at"],
            last_error=row["last_error"],
            updated_at=row["updated_at"],
        )
