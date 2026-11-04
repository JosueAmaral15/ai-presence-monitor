from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_presence_monitor.codex_repository import (
    CodexRepositoryError,
    classify_codex_repository_path,
    inspect_codex_repository,
)


class CodexRepositoryInventoryTests(unittest.TestCase):
    def test_inventory_counts_without_reading_or_listing_session_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".codex"
            session = root / "sessions" / "2026" / "11"
            session.mkdir(parents=True)
            (session / "private-session-id.jsonl").write_text(
                '{"secret":"must-not-appear"}\n',
                encoding="utf-8",
            )
            (root / "auth.json").write_text("token", encoding="utf-8")
            (root / "state_5.sqlite").write_bytes(b"sqlite")
            (root / "unknown.bin").write_bytes(b"unknown")

            inventory = inspect_codex_repository(root)
            payload = inventory.as_dict()
            rendered = repr(payload)

            self.assertNotIn("private-session-id", rendered)
            self.assertNotIn("must-not-appear", rendered)
            categories = {item.name: item for item in inventory.categories}
            self.assertTrue(
                categories["conversation_candidate"].schema_review_candidate
            )
            self.assertFalse(
                categories["secret_or_configuration"].schema_review_candidate
            )
            self.assertFalse(categories["active_database"].schema_review_candidate)
            self.assertFalse(categories["unknown"].schema_review_candidate)

    def test_only_jsonl_in_known_history_roots_is_candidate(self) -> None:
        self.assertEqual(
            classify_codex_repository_path(Path("sessions/2026/session.jsonl")),
            "conversation_candidate",
        )
        self.assertEqual(
            classify_codex_repository_path(Path("sessions/session.sqlite")),
            "unknown",
        )
        self.assertEqual(
            classify_codex_repository_path(Path("auth.json")),
            "secret_or_configuration",
        )

    def test_invalid_root_fails_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"

            with self.assertRaisesRegex(CodexRepositoryError, "does not exist"):
                inspect_codex_repository(missing)

            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
