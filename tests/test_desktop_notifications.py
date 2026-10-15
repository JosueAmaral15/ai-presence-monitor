from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from ai_presence_monitor.desktop_notifications import (
    ALERT_CURSOR_KEY,
    EVENT_CURSOR_KEY,
    DesktopNotificationObserver,
)
from ai_presence_monitor.store import PresenceStore


class DesktopNotificationObserverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = PresenceStore(Path(self.temporary.name) / "presence.db")
        self.observer = DesktopNotificationObserver(self.store)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def record(self, event_type: str, *, task: str = "project") -> None:
        self.store.record_event(
            worker_id="computer:codex:project=test",
            computer="computer",
            ia_name="codex",
            protocol="protocol2",
            event_type=event_type,
            message="test event",
            task=task,
        )

    def test_first_poll_skips_old_events_then_reports_supported_new_events(self) -> None:
        self.record("start", task="historical")

        self.assertEqual(self.observer.poll(), ())

        self.record("start", task="current")
        self.store.record_observation(
            worker_id="computer:codex:project=test",
            computer="computer",
            ia_name="codex",
            protocol="protocol2",
            source="codex:Stop",
            message="codex hook Stop",
            task="current",
        )
        self.record("finish", task="current")
        notices = self.observer.poll()

        self.assertEqual(
            [notice.title for notice in notices],
            ["AI task started", "Codex turn ended", "AI task finished"],
        )
        self.assertIn("emitted a Stop hook", notices[1].message)
        self.assertEqual(self.observer.poll(), ())

    def test_alerts_are_severity_mapped_and_not_repeated(self) -> None:
        self.assertEqual(self.observer.poll(), ())
        self.store.record_alert(
            worker_id="worker",
            protocol="protocol2",
            level="yellow",
            signal_age_seconds=301,
            triggered_at=1000,
        )
        self.store.record_alert(
            worker_id="worker",
            protocol="protocol2",
            level="red",
            signal_age_seconds=901,
            triggered_at=1100,
        )

        notices = self.observer.poll()

        self.assertEqual([notice.severity for notice in notices], ["warning", "critical"])
        self.assertIn("about 15 minutes", notices[1].message)
        self.assertEqual(self.observer.poll(), ())

    def test_question_lifecycle_uses_precise_delivery_language(self) -> None:
        self.assertEqual(self.observer.poll(), ())
        question = self.store.create_question(
            worker_id="worker",
            prompt="Choose one option",
            timeout_seconds=600,
            answer_transport="native",
            target_session_id="session-1",
            target_destination="local",
            now=1000,
        )
        self.store.mark_question_published(
            question.question_id,
            channel_id="channel",
            external_message_id="100",
            now=1001,
        )

        pending = self.observer.poll()
        self.assertEqual([notice.title for notice in pending], ["Discord question pending"])
        self.assertEqual(self.observer.poll(), ())

        answered = self.store.record_question_answer(
            external_message_id="100",
            channel_id="channel",
            reply_message_id="101",
            answered_by="allowed-user",
            answer="Proceed",
            now=1002,
        )
        assert answered is not None
        self.assertEqual(
            [notice.title for notice in self.observer.poll()],
            ["Discord reply received"],
        )

        self.store.mark_input_emitted(question.question_id, now=1003)
        emitted = self.observer.poll()
        self.assertEqual(emitted[0].title, "Discord answer transport completed")
        self.assertIn("await later session evidence", emitted[0].message)

        self.store.confirm_deliveries(
            worker_id="worker",
            observed_at=1004,
            timeout_seconds=60,
            session_id="session-1",
        )
        confirmed = self.observer.poll()
        self.assertEqual(confirmed[0].title, "Codex activity after Discord answer")
        self.assertIn("not interpretation", confirmed[0].message)

    def test_existing_pending_question_is_reported_once_after_first_start(self) -> None:
        self.store.create_question(
            worker_id="worker",
            prompt="Historical but pending",
            timeout_seconds=600,
            now=1000,
        )

        notices = self.observer.poll()

        self.assertEqual([notice.title for notice in notices], ["Discord question pending"])
        restarted = DesktopNotificationObserver(self.store)
        self.assertEqual(restarted.poll(), ())

    def test_new_publish_failure_is_reported_but_historical_failure_is_not(self) -> None:
        historical = self.store.create_question(
            worker_id="worker",
            prompt="Historical failure",
            timeout_seconds=600,
            now=1000,
        )
        self.store.mark_question_error(
            historical.question_id,
            status="publish_failed",
            error="offline",
            allowed_statuses=("pending",),
            now=1001,
        )
        self.assertEqual(self.observer.poll(), ())

        current = self.store.create_question(
            worker_id="worker",
            prompt="Current failure",
            timeout_seconds=600,
            now=time.time() + 1,
        )
        self.store.mark_question_error(
            current.question_id,
            status="publish_failed",
            error="offline",
            allowed_statuses=("pending",),
            now=time.time() + 2,
        )

        notices = self.observer.poll()
        self.assertEqual(
            [notice.title for notice in notices],
            ["Discord question was not published"],
        )

    def test_acknowledge_current_suppresses_disabled_period_backlog(self) -> None:
        self.record("start")
        self.store.record_alert(
            worker_id="worker",
            protocol="protocol2",
            level="orange",
            signal_age_seconds=600,
        )
        self.store.create_question(
            worker_id="worker",
            prompt="Pending",
            timeout_seconds=600,
        )

        pending = self.observer.acknowledge_current()

        self.assertEqual(pending, 1)
        self.assertEqual(self.observer.poll(), ())

    def test_invalid_cursors_are_rebased_without_replaying_history(self) -> None:
        self.record("finish")
        self.store.record_alert(
            worker_id="worker",
            protocol="protocol2",
            level="red",
            signal_age_seconds=900,
        )
        self.store.set_observer_state(EVENT_CURSOR_KEY, "invalid")
        self.store.set_observer_state(ALERT_CURSOR_KEY, "-1")

        self.assertEqual(self.observer.poll(), ())


if __name__ == "__main__":
    unittest.main()
