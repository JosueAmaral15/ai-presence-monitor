from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from ai_presence_monitor.cli import _check_once
from ai_presence_monitor.config import AppConfig
from ai_presence_monitor.store import PresenceStore
from ai_presence_monitor.work_window import is_time_in_window, parse_clock


def make_config(
    db_path: Path,
    *,
    work_window_enabled: bool = False,
    alert_repeat_enabled: bool = False,
    protocol: str = "protocol2",
    red_notification_mode: str = "none",
    red_alert_command: str | None = None,
) -> AppConfig:
    return AppConfig(
        env_path=db_path.parent / ".env",
        db_path=db_path,
        default_protocol=protocol,
        computer_name="test-computer",
        monitor_interval_seconds=30,
        work_window_enabled=work_window_enabled,
        work_window_start="13:00",
        work_window_end="18:00",
        work_window_timezone="UTC",
        outside_work_window_behavior="suppress_alerts",
        alert_repeat_enabled=alert_repeat_enabled,
        alert_repeat_seconds=300,
        alert_repeat_levels=("yellow", "orange", "red"),
        discord_point_webhook_url=None,
        discord_alert_webhook_url=None,
        discord_red_webhook_url=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        red_notification_mode=red_notification_mode,
        red_alert_command=red_alert_command,
        phone_webhook_url=None,
        codex_worker_id=None,
        codex_ai_name="codex",
        codex_protocol=protocol,
        codex_task=None,
        codex_worker_scope="global",
        codex_auto_start=False,
        codex_hook_fail_closed=False,
    )


def make_stale_worker(store: PresenceStore, *, protocol: str, now: float, age_seconds: int) -> None:
    worker = store.record_event(
        worker_id="test-computer:codex",
        computer="test-computer",
        ia_name="codex",
        protocol=protocol,
        event_type="start",
        message="inicio",
        task="teste",
    )
    stale_clock = now - age_seconds
    with store.session() as conn:
        conn.execute(
            """
            UPDATE workers
            SET last_signal_at = ?,
                last_activity_at = ?,
                updated_at = ?
            WHERE worker_id = ?
            """,
            (stale_clock, stale_clock, stale_clock, worker.worker_id),
        )


class MonitorPolicyTests(unittest.TestCase):
    def test_time_window_supports_regular_and_overnight_ranges(self) -> None:
        self.assertTrue(is_time_in_window(parse_clock("14:00"), parse_clock("13:00"), parse_clock("18:00")))
        self.assertFalse(is_time_in_window(parse_clock("19:00"), parse_clock("13:00"), parse_clock("18:00")))
        self.assertTrue(is_time_in_window(parse_clock("23:00"), parse_clock("22:00"), parse_clock("06:00")))
        self.assertTrue(is_time_in_window(parse_clock("05:00"), parse_clock("22:00"), parse_clock("06:00")))
        self.assertFalse(is_time_in_window(parse_clock("12:00"), parse_clock("22:00"), parse_clock("06:00")))

    def test_monitor_suppresses_alerts_outside_work_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            config = make_config(db_path, work_window_enabled=True)
            store = PresenceStore(db_path)
            now = datetime(2026, 4, 1, 19, 0, tzinfo=timezone.utc).timestamp()
            make_stale_worker(store, protocol="protocol2", now=now, age_seconds=16 * 60)

            alerts = _check_once(config, dry_run=True, now=now)

            self.assertEqual(alerts, 0)
            worker = store.get_worker("test-computer:codex")
            self.assertIsNotNone(worker)
            assert worker is not None
            self.assertIsNone(worker.last_alert_level)

    def test_monitor_allows_alerts_inside_work_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            config = make_config(db_path, work_window_enabled=True)
            store = PresenceStore(db_path)
            now = datetime(2026, 4, 1, 14, 0, tzinfo=timezone.utc).timestamp()
            make_stale_worker(store, protocol="protocol2", now=now, age_seconds=6 * 60)

            alerts = _check_once(config, dry_run=True, now=now)

            self.assertEqual(alerts, 1)
            worker = store.get_worker("test-computer:codex")
            self.assertIsNotNone(worker)
            assert worker is not None
            self.assertEqual(worker.last_alert_level, "yellow")
            self.assertEqual(worker.last_alert_at, now)

    def test_monitor_repeats_same_level_after_repeat_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            config = make_config(
                db_path,
                work_window_enabled=True,
                alert_repeat_enabled=True,
                protocol="protocol1",
            )
            store = PresenceStore(db_path)
            now = datetime(2026, 4, 1, 14, 0, tzinfo=timezone.utc).timestamp()
            make_stale_worker(store, protocol="protocol1", now=now, age_seconds=8 * 60)

            self.assertEqual(_check_once(config, dry_run=True, now=now), 1)
            self.assertEqual(_check_once(config, dry_run=True, now=now + 100), 0)
            self.assertEqual(_check_once(config, dry_run=True, now=now + 301), 1)

            worker = store.get_worker("test-computer:codex")
            self.assertIsNotNone(worker)
            assert worker is not None
            self.assertEqual(worker.last_alert_level, "yellow")
            self.assertEqual(worker.last_alert_at, now + 301)

    def test_red_alert_is_one_shot_until_activity_rearms_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            config = make_config(
                db_path,
                work_window_enabled=True,
                alert_repeat_enabled=True,
                red_notification_mode="alarm",
                red_alert_command="echo red-alert",
            )
            store = PresenceStore(db_path)
            now = datetime(2026, 4, 1, 14, 0, tzinfo=timezone.utc).timestamp()
            make_stale_worker(store, protocol="protocol2", now=now, age_seconds=16 * 60)

            first_output = StringIO()
            with redirect_stdout(first_output):
                self.assertEqual(_check_once(config, dry_run=True, now=now), 1)
            self.assertIn("[dry-run:comando] echo red-alert", first_output.getvalue())

            repeat_output = StringIO()
            with redirect_stdout(repeat_output):
                self.assertEqual(_check_once(config, dry_run=True, now=now + 301), 0)
            self.assertNotIn("[dry-run:discord:alerta:red]", repeat_output.getvalue())
            self.assertNotIn("[dry-run:telegram:alerta:red]", repeat_output.getvalue())
            self.assertNotIn("[dry-run:comando] echo red-alert", repeat_output.getvalue())

            activity_at = now + 302
            worker = store.record_observation(
                worker_id="test-computer:codex",
                computer="test-computer",
                ia_name="codex",
                protocol="protocol2",
                source="test",
                message="atividade retomada",
                auto_start=False,
                now=activity_at,
            )
            self.assertIsNotNone(worker)
            assert worker is not None
            self.assertIsNone(worker.last_alert_level)

            rearmed_output = StringIO()
            with redirect_stdout(rearmed_output):
                self.assertEqual(
                    _check_once(config, dry_run=True, now=activity_at + 16 * 60),
                    1,
                )
            self.assertIn("[dry-run:discord:alerta:red]", rearmed_output.getvalue())
            self.assertIn("[dry-run:telegram:alerta:red]", rearmed_output.getvalue())
            self.assertIn("[dry-run:comando] echo red-alert", rearmed_output.getvalue())


if __name__ == "__main__":
    unittest.main()
