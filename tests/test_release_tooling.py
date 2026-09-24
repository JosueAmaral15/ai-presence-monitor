from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_release import build_release
from scripts.release_lib import (
    ReleaseError,
    parse_checksums,
    project_version,
    sha256,
    wheel_metadata,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ReleaseToolingTests(unittest.TestCase):
    def test_package_and_runtime_versions_are_synchronized(self) -> None:
        self.assertEqual(project_version(PROJECT_ROOT), "0.9.0")

    def test_wheel_metadata_reads_expected_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "ai_presence_monitor-0.9.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "ai_presence_monitor-0.9.0.dist-info/METADATA",
                    "Metadata-Version: 2.1\n"
                    "Name: ai-presence-monitor\n"
                    "Version: 0.9.0\n",
                )

            self.assertEqual(wheel_metadata(wheel), ("ai-presence-monitor", "0.9.0"))

    def test_checksum_parser_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "SHA256SUMS"
            checksums.write_text(f"{'0' * 64}  ../artifact.whl\n", encoding="utf-8")

            with self.assertRaisesRegex(ReleaseError, "artifact name"):
                parse_checksums(checksums)

    def test_checksum_parser_and_hash_agree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.whl"
            artifact.write_bytes(b"release artifact")
            checksums = root / "SHA256SUMS"
            checksums.write_text(
                f"{sha256(artifact)}  {artifact.name}\n",
                encoding="utf-8",
            )

            self.assertEqual(parse_checksums(checksums), {artifact.name: sha256(artifact)})

    def test_release_builder_refuses_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing"
            output.mkdir()

            with self.assertRaisesRegex(ReleaseError, "already exists"):
                build_release(output, allow_dirty=True)

    def test_linux_installer_rejects_root_install_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheel = root / "candidate.whl"
            wheel.touch()
            environment = dict(os.environ)
            environment["HOME"] = str(root / "home")
            result = subprocess.run(
                [
                    "bash",
                    str(PROJECT_ROOT / "scripts" / "install-linux.sh"),
                    "--wheel",
                    str(wheel),
                    "--install-root",
                    "/",
                    "--python",
                    sys.executable,
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("absolute, dedicated non-root directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
