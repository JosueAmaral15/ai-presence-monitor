from __future__ import annotations

import gzip
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_deb import (
    _control_text,
    _postrm_text,
    _safe_wheel_member,
    _validate_maintainer,
    _wrapper_text,
    _write_gzip,
)
from scripts.release_lib import ReleaseError


class DebianPackageTests(unittest.TestCase):
    def test_control_declares_portable_python_package(self) -> None:
        control = _control_text("1.2.3-1", "Maintainer <maintainer@example.test>")

        self.assertIn("Package: ai-presence-monitor", control)
        self.assertIn("Version: 1.2.3-1", control)
        self.assertIn("Architecture: all", control)
        self.assertIn("python3 (>= 3.10), python3 (<< 3.13)", control)

    def test_maintainer_rejects_control_injection(self) -> None:
        with self.assertRaisesRegex(ReleaseError, "maintainer"):
            _validate_maintainer("Maintainer <a@example.test>\nDepends: unsafe")

    def test_wrapper_uses_fixed_system_python_and_module(self) -> None:
        wrapper = _wrapper_text("ai_presence_monitor.cli")

        self.assertTrue(wrapper.startswith("#!/usr/bin/python3\n"))
        self.assertIn("from ai_presence_monitor.cli import main", wrapper)
        self.assertNotIn("eval", wrapper)

    def test_wrapper_rejects_foreign_module(self) -> None:
        with self.assertRaisesRegex(ReleaseError, "module"):
            _wrapper_text("subprocess")

    def test_postrm_only_cleans_package_bytecode_cache(self) -> None:
        postrm = _postrm_text()

        self.assertIn("/usr/lib/python3/dist-packages/ai_presence_monitor", postrm)
        self.assertIn("-name __pycache__", postrm)
        self.assertNotIn("$HOME", postrm)
        self.assertNotIn(".config", postrm)
        self.assertNotIn("presence.db", postrm)

    def test_wheel_member_rejects_path_traversal(self) -> None:
        with self.assertRaisesRegex(ReleaseError, "unsafe path"):
            _safe_wheel_member("../outside")

    def test_wheel_member_accepts_package_path(self) -> None:
        member = _safe_wheel_member("ai_presence_monitor/cli.py")

        self.assertIsNotNone(member)
        assert member is not None
        self.assertEqual(member.as_posix(), "ai_presence_monitor/cli.py")

    def test_bad_wheel_is_rejected_by_metadata_reader(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "bad.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("../outside", "unsafe")

            with self.assertRaises(ReleaseError):
                from scripts.build_deb import _extract_wheel

                _extract_wheel(wheel, Path(temporary) / "target")

    def test_gzip_header_has_no_build_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "manual.gz"

            _write_gzip(archive, "content\n", mtime=0)

            self.assertEqual(archive.read_bytes()[4:8], b"\x00\x00\x00\x00")
            with gzip.open(archive, "rt", encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "content\n")


if __name__ == "__main__":
    unittest.main()
