from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from test_cli import make_config

from ai_presence_monitor import __version__
from ai_presence_monitor.codex_hook_installer import (
    build_presence_hooks,
    render_hooks,
)
from ai_presence_monitor.product_health import collect_doctor_report
from ai_presence_monitor.store import SCHEMA_VERSION, PresenceStore, inspect_schema


class SchemaVersionTests(unittest.TestCase):
    def test_missing_schema_inspection_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "missing.db"

            status = inspect_schema(db_path)

            self.assertFalse(status.database_exists)
            self.assertEqual(status.migration_status, "missing")
            self.assertFalse(status.healthy)
            self.assertFalse(db_path.exists())

    def test_presence_store_migrates_legacy_database_to_current_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE legacy_marker (value TEXT NOT NULL)")

            PresenceStore(db_path)
            status = inspect_schema(db_path)

            self.assertTrue(status.healthy)
            self.assertEqual(status.current_version, SCHEMA_VERSION)
            self.assertEqual(status.integrity, "ok")

    def test_presence_store_rejects_newer_schema_without_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "future.db"
            future_version = SCHEMA_VERSION + 1
            with sqlite3.connect(db_path) as conn:
                conn.execute(f"PRAGMA user_version = {future_version}")

            with self.assertRaisesRegex(ValueError, "newer than this runtime"):
                PresenceStore(db_path)

            with sqlite3.connect(db_path) as conn:
                current = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(current, future_version)


class ProductHealthTests(unittest.TestCase):
    def test_doctor_reports_healthy_sanitized_linux_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                make_config(root),
                discord_bot_token="discord-secret",
                telegram_bot_token="telegram-secret",
            )
            config.env_path.write_text("PRESENCE_DB_PATH=./presence.db\n", encoding="utf-8")
            config.env_path.chmod(0o600)
            PresenceStore(config.db_path)

            hooks_path = root / "hooks.json"
            hooks_path.write_text(
                render_hooks(build_presence_hooks("python -m ai_presence_monitor.codex_hook")),
                encoding="utf-8",
            )
            tray_path = root / "ai-presence-tray.desktop"
            tray_path.write_text(
                "[Desktop Entry]\nExec=/usr/bin/ai-presence tray\n",
                encoding="utf-8",
            )
            tray_path.chmod(0o600)

            def runner(
                command: list[str],
                **_: object,
            ) -> subprocess.CompletedProcess[str]:
                if command[0] == "/usr/bin/codex":
                    return subprocess.CompletedProcess(command, 0, "queue help", "")
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "LoadState=loaded\nActiveState=active\nResult=success\n",
                    "",
                )

            report = collect_doctor_report(
                config,
                platform_name="linux",
                hooks_path=hooks_path,
                tray_autostart_path=tray_path,
                executable_finder=lambda _: "/usr/bin/codex",
                runner=runner,
            )

            self.assertEqual(report.status, "ok")
            self.assertEqual(report.exit_code(), 0)
            payload = report.render_json()
            self.assertNotIn("discord-secret", payload)
            self.assertNotIn("telegram-secret", payload)
            self.assertEqual(json.loads(payload)["version"], __version__)

    def test_doctor_strict_mode_fails_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)

            def runner(
                command: list[str],
                **_: object,
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "LoadState=not-found\nActiveState=inactive\nResult=success\n",
                    "",
                )

            report = collect_doctor_report(
                config,
                platform_name="linux",
                hooks_path=root / "missing-hooks.json",
                tray_autostart_path=root / "missing.desktop",
                executable_finder=lambda _: None,
                runner=runner,
            )

            self.assertEqual(report.status, "warning")
            self.assertEqual(report.exit_code(), 0)
            self.assertEqual(report.exit_code(strict=True), 1)
            self.assertFalse(config.db_path.exists())


if __name__ == "__main__":
    unittest.main()
