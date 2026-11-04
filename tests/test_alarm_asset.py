from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_alarm_asset import EXPECTED_SHA256, generate_alarm_wave


class AlarmAssetTests(unittest.TestCase):
    def test_committed_alarm_is_reproducible(self) -> None:
        committed = Path(__file__).parents[1] / "assets" / "ai-presence-alarm.wav"
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary) / "alarm.wav"

            digest = generate_alarm_wave(generated)

            self.assertEqual(digest, EXPECTED_SHA256)
            self.assertEqual(generated.read_bytes(), committed.read_bytes())


if __name__ == "__main__":
    unittest.main()
