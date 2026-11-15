from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ai_presence_monitor.store import (
    SCHEMA_VERSION,
    PresenceStore,
    automation_session_fingerprint,
    inspect_schema,
)


class DispatchAuditTests(unittest.TestCase):
    def test_schema_three_migrates_additively_to_dispatch_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.db"
            PresenceStore(path)
            with sqlite3.connect(path) as conn:
                conn.execute("DROP TABLE automation_dispatch_audit")
                conn.execute("PRAGMA user_version = 3")
                conn.execute("CREATE TABLE preserved (value TEXT NOT NULL)")
                conn.execute("INSERT INTO preserved VALUES ('yes')")

            PresenceStore(path)

            self.assertEqual(SCHEMA_VERSION, 4)
            self.assertTrue(inspect_schema(path).healthy)
            with sqlite3.connect(path) as conn:
                value = conn.execute("SELECT value FROM preserved").fetchone()[0]
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertEqual(value, "yes")
            self.assertIn("automation_dispatch_audit", tables)

    def test_claim_and_completion_never_persist_raw_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.db"
            store = PresenceStore(path)
            session_id = "11111111-2222-3333-4444-555555555555"

            claimed = store.claim_automation_dispatch(
                worker_id="worker-a",
                rule_id="rule-a",
                source="prompt_rule",
                trigger="red_inactivity",
                provider="codex",
                session_id=session_id,
                attempted_at=100.0,
            )
            completed = store.complete_automation_dispatch(
                claimed.audit_id,
                transport_state="dispatch_started",
                updated_at=101.0,
            )

            self.assertEqual(completed.confirmation_state, "pending")
            self.assertEqual(completed.occurrence_number, 1)
            self.assertEqual(
                completed.target_session_fingerprint,
                automation_session_fingerprint("worker-a", session_id),
            )
            with sqlite3.connect(path) as conn:
                persisted = " ".join(
                    str(value)
                    for value in conn.execute(
                        "SELECT * FROM automation_dispatch_audit"
                    ).fetchone()
                )
            self.assertNotIn(session_id, persisted)

    def test_later_exact_session_observation_confirms_pending_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presence.db"
            store = PresenceStore(path)
            session_id = "11111111-2222-3333-4444-555555555555"
            other_session = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            claimed = store.claim_automation_dispatch(
                worker_id="worker-a",
                rule_id="codex:availability",
                source="availability_recovery",
                trigger="unavailable_to_available",
                provider="codex",
                session_id=session_id,
                attempted_at=100.0,
            )
            store.complete_automation_dispatch(
                claimed.audit_id,
                transport_state="dispatch_started",
                updated_at=100.0,
            )
            with store.session() as conn:
                conn.execute(
                    """
                    INSERT INTO events (
                        worker_id, event_type, protocol, occurred_at, message, task
                    ) VALUES (?, 'observation:codex:UserPromptSubmit',
                              'protocol2', ?, ?, 'task')
                    """,
                    ("worker-a", 101.0, f"session={other_session}"),
                )

            self.assertEqual(store.confirm_pending_automation_dispatches(), 0)
            with store.session() as conn:
                conn.execute(
                    """
                    INSERT INTO events (
                        worker_id, event_type, protocol, occurred_at, message, task
                    ) VALUES (?, 'observation:codex:PostToolUse',
                              'protocol2', ?, ?, 'task')
                    """,
                    ("worker-a", 102.0, f"session={session_id}"),
                )

            self.assertEqual(store.confirm_pending_automation_dispatches(), 1)
            confirmed = store.get_automation_dispatch_audit(claimed.audit_id)
            assert confirmed is not None
            self.assertEqual(confirmed.confirmation_state, "confirmed")
            self.assertEqual(confirmed.confirmed_at, 102.0)
            self.assertEqual(store.confirm_pending_automation_dispatches(), 0)

    def test_uncertain_transport_is_terminal_and_sources_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            session_id = "11111111-2222-3333-4444-555555555555"
            first = store.claim_automation_dispatch(
                worker_id="worker-a",
                rule_id="shared-rule",
                source="prompt_rule",
                trigger="after_delay",
                provider="codex",
                session_id=session_id,
                attempted_at=100.0,
            )
            second = store.claim_automation_dispatch(
                worker_id="worker-a",
                rule_id="shared-rule",
                source="availability_recovery",
                trigger="unavailable_to_available",
                provider="codex",
                session_id=session_id,
                attempted_at=101.0,
            )

            failed = store.complete_automation_dispatch(
                first.audit_id,
                transport_state="failed_or_uncertain",
                updated_at=102.0,
            )

            self.assertEqual(failed.confirmation_state, "not_applicable")
            self.assertEqual(first.occurrence_number, 1)
            self.assertEqual(second.occurrence_number, 1)
            with self.assertRaisesRegex(ValueError, "not dispatching"):
                store.complete_automation_dispatch(
                    first.audit_id,
                    transport_state="dispatch_started",
                )


if __name__ == "__main__":
    unittest.main()
