from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.codex_hook_installer import (
    count_presence_hooks,
    default_hook_script_path,
    install_codex_hook,
    uninstall_codex_hook,
)
from ai_presence_monitor.codex_hook_installer import (
    main as installer_main,
)


class CodexHookInstallerTests(unittest.TestCase):
    def test_compatibility_hook_path_uses_project_root_with_src_layout(self) -> None:
        path = default_hook_script_path()

        self.assertEqual(path.name, "codex_presence_hook.py")
        self.assertTrue(path.is_file())
        self.assertEqual(path.parent.name, "hooks")

    def test_install_creates_presence_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hooks.json"
            env_file = Path(tmp) / ".env"

            result = install_codex_hook(target_path=target, env_file=env_file)

            self.assertTrue(result.changed)
            self.assertTrue(target.exists())
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(count_presence_hooks(data), 5)

    def test_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hooks.json"
            env_file = Path(tmp) / ".env"

            first = install_codex_hook(target_path=target, env_file=env_file)
            second = install_codex_hook(target_path=target, env_file=env_file)

            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertTrue(first.changed)
            self.assertFalse(second.changed)
            self.assertEqual(count_presence_hooks(data), 5)

    def test_install_preserves_external_hook_and_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hooks.json"
            env_file = Path(tmp) / ".env"
            target.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 /tmp/external.py",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = install_codex_hook(target_path=target, env_file=env_file)

            self.assertIsNotNone(result.backup_path)
            assert result.backup_path is not None
            self.assertTrue(result.backup_path.exists())
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("external.py", json.dumps(data))
            self.assertEqual(count_presence_hooks(data), 5)

    def test_uninstall_removes_only_presence_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hooks.json"
            env_file = Path(tmp) / ".env"
            install_codex_hook(target_path=target, env_file=env_file)
            data = json.loads(target.read_text(encoding="utf-8"))
            data["hooks"].setdefault("Stop", []).append(
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 /tmp/external.py",
                        }
                    ]
                }
            )
            target.write_text(json.dumps(data), encoding="utf-8")

            result = uninstall_codex_hook(target_path=target)

            self.assertTrue(result.changed)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(count_presence_hooks(data), 0)
            self.assertIn("external.py", json.dumps(data))

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hooks.json"
            env_file = Path(tmp) / ".env"

            result = install_codex_hook(target_path=target, env_file=env_file, dry_run=True)

            self.assertTrue(result.changed)
            self.assertFalse(target.exists())
            self.assertIn("ai_presence_monitor.codex_hook", result.rendered_json)

    def test_install_replaces_legacy_script_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hooks.json"
            env_file = Path(tmp) / ".env"
            target.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 /tmp/codex_presence_hook.py",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            install_codex_hook(target_path=target, env_file=env_file)

            rendered = target.read_text(encoding="utf-8")
            self.assertNotIn("/tmp/codex_presence_hook.py", rendered)
            self.assertIn("ai_presence_monitor.codex_hook", rendered)

    def test_direct_installer_blocks_windows_without_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "hooks.json"
            env_path = root / ".env"
            env_path.write_text(
                "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=false\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True), patch(
                "ai_presence_monitor.platform_integration.sys.platform",
                "win32",
            ), redirect_stderr(StringIO()) as error, self.assertRaises(
                SystemExit
            ) as exit_context:
                installer_main(
                    [
                        "install",
                        "--target",
                        str(target),
                        "--env-file",
                        str(env_path),
                    ]
                )

            self.assertEqual(exit_context.exception.code, 2)
            self.assertIn("Windows e experimental", error.getvalue())
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
