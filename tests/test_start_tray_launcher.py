from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = PROJECT_ROOT / "start-tray.sh"


class StartTrayLauncherTests(unittest.TestCase):
    def test_starts_once_and_reports_existing_unit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            environment = self._fake_environment(root)

            first = self._run(environment)
            second = self._run(environment)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("tray started", first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("already running", second.stdout)
            calls = (root / "systemd-run.calls").read_text(encoding="utf-8")
            self.assertEqual(calls.count("ai-presence-tray-session"), 1)
            self.assertIn(str(root / "ai-presence"), calls)
            self.assertIn(str(root / ".env"), calls)

    def test_failed_prerequisite_does_not_start_unit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            environment = self._fake_environment(root)
            environment["FAKE_CHECK_EXIT"] = "1"

            result = self._run(environment)

            self.assertEqual(result.returncode, 1)
            self.assertIn("Tray prerequisites are unavailable", result.stderr)
            self.assertFalse((root / "systemd-run.calls").exists())

    def test_launcher_is_executable(self) -> None:
        self.assertTrue(os.access(LAUNCHER, os.X_OK))

    def _run(self, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(LAUNCHER)],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    def _fake_environment(self, root: Path) -> dict[str, str]:
        fake_bin = root / "bin"
        fake_bin.mkdir()
        state = root / "active"
        calls = root / "systemd-run.calls"
        env_file = root / ".env"
        env_file.write_text("# test\n", encoding="utf-8")

        self._write_executable(
            root / "ai-presence",
            """#!/usr/bin/env bash
if [[ "$*" == *"tray --check"* ]]; then
    exit "${FAKE_CHECK_EXIT:-0}"
fi
exit 0
""",
        )
        self._write_executable(
            fake_bin / "systemctl",
            """#!/usr/bin/env bash
[[ "${1:-}" == "--user" ]] && shift
case "${1:-}" in
    is-active) [[ -f "$FAKE_STATE" ]] ;;
    reset-failed) exit 0 ;;
    *) exit 0 ;;
esac
""",
        )
        self._write_executable(
            fake_bin / "systemd-run",
            """#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_CALLS"
touch "$FAKE_STATE"
""",
        )
        self._write_executable(fake_bin / "pgrep", "#!/usr/bin/env bash\nexit 1\n")
        self._write_executable(fake_bin / "notify-send", "#!/usr/bin/env bash\nexit 0\n")

        environment = os.environ.copy()
        environment.update(
            {
                "AI_PRESENCE_BIN": str(root / "ai-presence"),
                "AI_PRESENCE_ENV_FILE": str(env_file),
                "DISPLAY": ":99",
                "FAKE_CALLS": str(calls),
                "FAKE_STATE": str(state),
                "PATH": f"{fake_bin}:/usr/bin:/bin",
            }
        )
        environment.pop("WAYLAND_DISPLAY", None)
        return environment

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
