from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .store import PresenceAlert, PresenceEvent, PresenceStore, RemoteQuestion

NotificationSeverity = Literal["information", "warning", "critical"]

EVENT_CURSOR_KEY = "desktop_notifications:event_cursor:v1"
ALERT_CURSOR_KEY = "desktop_notifications:alert_cursor:v1"
QUESTION_STATE_PREFIX = "desktop_notifications:question:v1:"
QUESTION_INITIALIZED_KEY = "desktop_notifications:questions_initialized_at:v1"


@dataclass(frozen=True)
class DesktopNotification:
    key: str
    title: str
    message: str
    severity: NotificationSeverity = "information"


class DesktopNotificationObserver:
    def __init__(self, store: PresenceStore):
        self.store = store

    def acknowledge_current(self) -> int:
        self.store.set_observer_state(EVENT_CURSOR_KEY, str(self.store.latest_event_id()))
        self.store.set_observer_state(ALERT_CURSOR_KEY, str(self.store.latest_alert_id()))
        self.store.set_observer_state(QUESTION_INITIALIZED_KEY, str(time.time()))
        pending = 0
        for question in self.store.list_questions(limit=1000):
            if question.status == "pending":
                pending += 1
            self.store.set_observer_state(
                self._question_key(question.question_id),
                question.status,
            )
        return pending

    def poll(self, *, limit: int = 100) -> tuple[DesktopNotification, ...]:
        if limit <= 0:
            return ()
        notices: list[DesktopNotification] = []
        notices.extend(self._poll_events(limit=limit))
        notices.extend(self._poll_alerts(limit=limit))
        notices.extend(self._poll_questions())
        return tuple(notices)

    def _poll_events(self, *, limit: int) -> list[DesktopNotification]:
        cursor = self._cursor(EVENT_CURSOR_KEY, self.store.latest_event_id)
        if cursor is None:
            return []
        events = self.store.list_events_after(cursor, limit=limit)
        if events:
            self.store.set_observer_state(EVENT_CURSOR_KEY, str(events[-1].event_id))
        return [notice for event in events if (notice := _event_notice(event))]

    def _poll_alerts(self, *, limit: int) -> list[DesktopNotification]:
        cursor = self._cursor(ALERT_CURSOR_KEY, self.store.latest_alert_id)
        if cursor is None:
            return []
        alerts = self.store.list_alerts_after(cursor, limit=limit)
        if alerts:
            self.store.set_observer_state(ALERT_CURSOR_KEY, str(alerts[-1].alert_id))
        return [_alert_notice(alert) for alert in alerts]

    def _poll_questions(self) -> list[DesktopNotification]:
        notices: list[DesktopNotification] = []
        initialized_at = self._questions_initialized_at()
        for question in reversed(self.store.list_questions(limit=1000)):
            key = self._question_key(question.question_id)
            previous = self.store.get_observer_state(key)
            if previous == question.status:
                continue
            notice = _question_notice(
                question,
                previous=previous,
                created_after_initialization=question.created_at >= initialized_at,
            )
            self.store.set_observer_state(key, question.status)
            if notice is not None:
                notices.append(notice)
        return notices

    def _questions_initialized_at(self) -> float:
        raw = self.store.get_observer_state(QUESTION_INITIALIZED_KEY)
        if raw is not None:
            try:
                initialized_at = float(raw)
            except ValueError:
                initialized_at = -1
            if initialized_at >= 0:
                return initialized_at
        initialized_at = time.time()
        self.store.set_observer_state(QUESTION_INITIALIZED_KEY, str(initialized_at))
        return initialized_at

    def _cursor(self, key: str, latest: Callable[[], int]) -> int | None:
        raw = self.store.get_observer_state(key)
        if raw is None:
            latest_id = latest()
            self.store.set_observer_state(key, str(latest_id))
            return None
        try:
            cursor = int(raw)
        except ValueError:
            cursor = -1
        if cursor < 0:
            latest_id = latest()
            self.store.set_observer_state(key, str(latest_id))
            return None
        return cursor

    @staticmethod
    def _question_key(question_id: str) -> str:
        return QUESTION_STATE_PREFIX + question_id


def _event_notice(event: PresenceEvent) -> DesktopNotification | None:
    label = _label(event.task, event.worker_id)
    if event.event_type == "start":
        return DesktopNotification(
            key=f"event:{event.event_id}",
            title="AI task started",
            message=f"{label} is now active.",
        )
    if event.event_type == "finish":
        return DesktopNotification(
            key=f"event:{event.event_id}",
            title="AI task finished",
            message=f"{label} reported that its task ended.",
        )
    if event.event_type == "observation:codex:Stop":
        return DesktopNotification(
            key=f"event:{event.event_id}",
            title="Codex turn ended",
            message=f"Codex emitted a Stop hook for {label}.",
        )
    return None


def _alert_notice(alert: PresenceAlert) -> DesktopNotification:
    severity: NotificationSeverity = (
        "critical" if alert.level == "red" else "warning"
    )
    minutes = max(0, round(alert.signal_age_seconds / 60))
    return DesktopNotification(
        key=f"alert:{alert.alert_id}",
        title=f"{alert.level.capitalize()} inactivity alert",
        message=(
            f"{_short(alert.worker_id)} reached a {alert.level} alert "
            f"after about {minutes} minutes."
        ),
        severity=severity,
    )


def _question_notice(
    question: RemoteQuestion,
    *,
    previous: str | None,
    created_after_initialization: bool,
) -> DesktopNotification | None:
    worker = _short(question.worker_id)
    messages: dict[str, tuple[str, str, NotificationSeverity]] = {
        "pending": (
            "Discord question pending",
            f"{worker} is waiting for a direct reply to its Discord question.",
            "warning",
        ),
        "answered": (
            "Discord reply received",
            f"An authorized Discord reply was correlated for {worker}.",
            "information",
        ),
        "input_emitted": (
            "Discord answer transport completed",
            f"Input transport completed for {worker}; await later session evidence.",
            "information",
        ),
        "delivery_confirmed": (
            "Codex activity after Discord answer",
            (
                f"A later exact-session hook was observed for {worker}; "
                "this confirms activity, not interpretation."
            ),
            "information",
        ),
        "dispatch_failed": (
            "Discord answer delivery failed",
            f"The authorized reply for {worker} was not delivered automatically.",
            "critical",
        ),
        "publish_failed": (
            "Discord question was not published",
            f"The question created by {worker} could not be posted.",
            "critical",
        ),
        "expired": (
            "Discord question expired",
            f"The question created by {worker} expired without an accepted reply.",
            "warning",
        ),
    }
    values = messages.get(question.status)
    if values is None:
        return None
    if (
        previous is None
        and question.status != "pending"
        and not created_after_initialization
    ):
        return None
    title, message, severity = values
    return DesktopNotification(
        key=f"question:{question.question_id}:{question.status}",
        title=title,
        message=message,
        severity=severity,
    )


def _label(task: str | None, worker_id: str) -> str:
    return _short(task or worker_id)


def _short(value: str, maximum: int = 96) -> str:
    clean = " ".join(value.split())
    if len(clean) <= maximum:
        return clean
    return clean[: maximum - 3] + "..."
