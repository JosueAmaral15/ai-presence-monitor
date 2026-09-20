from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from test_cli import make_config

from ai_presence_monitor.store import PresenceStore
from ai_presence_monitor.updater import (
    MANAGED_SERVICES,
    UpgradeError,
    read_wheel_version,
    rollback_upgrade,
    upgrade_from_wheel,
)


def make_wheel(root: Path, version: str) -> Path:
    path = root / f"ai_presence_monitor-{version}-py3-none-any.whl"
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: ai-presence-monitor\n"
        f"Version: {version}\n"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"ai_presence_monitor-{version}.dist-info/METADATA",
            metadata,
        )
    return path


class FakeRuntime:
    def __init__(
        self,
        *,
        version: str = "0.8.0",
        active_services: tuple[str, ...] = MANAGED_SERVICES,
        fail_doctor_version: str | None = None,
        fail_stop_unit: str | None = None,
        fail_start_unit_once: str | None = None,
    ) -> None:
        self.version = version
        self.active_services = set(active_services)
        self.fail_doctor_version = fail_doctor_version
        self.fail_stop_unit = fail_stop_unit
        self.fail_start_unit_once = fail_start_unit_once
        self.commands: list[tuple[str, ...]] = []

    def __call__(
        self,
        command: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(tuple(command))
        if command[:3] == ["systemctl", "--user", "is-active"]:
            unit = command[3]
            active = unit in self.active_services
            return self._completed(command, 0 if active else 3, "active\n" if active else "inactive\n")
        if command[:3] == ["systemctl", "--user", "stop"]:
            unit = command[3]
            if unit == self.fail_stop_unit:
                return self._completed(command, 1)
            self.active_services.discard(unit)
            return self._completed(command)
        if command[:3] == ["systemctl", "--user", "start"]:
            if command[3] == self.fail_start_unit_once:
                self.fail_start_unit_once = None
                return self._completed(command, 1)
            self.active_services.add(command[3])
            return self._completed(command)
        if len(command) > 2 and command[1] == "-c":
            return self._completed(command, stdout=f"{self.version}\n")
        if command[1:4] == ["-m", "pip", "install"]:
            self.version = read_wheel_version(Path(command[-1]))
            return self._completed(command)
        if command[1:3] == ["-m", "ai_presence_monitor"] and command[-1] == "init":
            return self._completed(command)
        if command[1:3] == ["-m", "ai_presence_monitor"] and "doctor" in command:
            if self.version == self.fail_doctor_version:
                return self._completed(command, 1, '{"status":"error"}\n')
            return self._completed(command, stdout='{"status":"ok"}\n')
        raise AssertionError(f"Unexpected command: {command}")

    @staticmethod
    def _completed(
        command: list[str],
        returncode: int = 0,
        stdout: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, returncode, stdout, "")


class TransactionalUpgradeTests(unittest.TestCase):
    def test_dry_run_validates_inputs_without_creating_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            PresenceStore(config.db_path)
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            backup_root = root / "backups"
            runtime = FakeRuntime()

            result = upgrade_from_wheel(
                config=config,
                target_wheel=target,
                rollback_wheel=rollback,
                authorized=False,
                dry_run=True,
                backup_root=backup_root,
                python_executable="/test/python",
                runner=runtime,
            )

            self.assertEqual(result.status, "would_upgrade")
            self.assertEqual(result.from_version, "0.8.0")
            self.assertEqual(result.to_version, "0.9.0")
            self.assertFalse(backup_root.exists())
            self.assertFalse(any("install" in command for command in runtime.commands))

    def test_success_creates_private_manifest_and_restarts_active_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            PresenceStore(config.db_path).set_observer_state("upgrade", "before")
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            backup_root = root / "backups"
            runtime = FakeRuntime()

            result = upgrade_from_wheel(
                config=config,
                target_wheel=target,
                rollback_wheel=rollback,
                authorized=True,
                backup_root=backup_root,
                python_executable="/test/python",
                runner=runtime,
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(runtime.version, "0.9.0")
            self.assertEqual(runtime.active_services, set(MANAGED_SERVICES))
            self.assertIsNotNone(result.manifest_path)
            assert result.manifest_path is not None
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["from_version"], "0.8.0")
            self.assertEqual(manifest["to_version"], "0.9.0")
            self.assertEqual(result.manifest_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(result.manifest_path.parent.stat().st_mode & 0o777, 0o700)

    def test_backup_filesystem_failure_is_reported_without_package_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            PresenceStore(config.db_path)
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            blocked_root = root / "not-a-directory"
            blocked_root.write_text("blocked", encoding="utf-8")
            runtime = FakeRuntime()

            with self.assertRaisesRegex(UpgradeError, "Backup directory creation failed"):
                upgrade_from_wheel(
                    config=config,
                    target_wheel=target,
                    rollback_wheel=rollback,
                    authorized=True,
                    backup_root=blocked_root,
                    python_executable="/test/python",
                    runner=runtime,
                )

            self.assertEqual(runtime.version, "0.8.0")
            self.assertFalse(any(command[1:4] == ("-m", "pip", "install") for command in runtime.commands))

    def test_failed_postflight_rolls_back_package_database_and_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            store = PresenceStore(config.db_path)
            store.set_observer_state("upgrade", "before")
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            backup_root = root / "backups"
            runtime = FakeRuntime(fail_doctor_version="0.9.0")

            with self.assertRaisesRegex(UpgradeError, "was rolled back"):
                upgrade_from_wheel(
                    config=config,
                    target_wheel=target,
                    rollback_wheel=rollback,
                    authorized=True,
                    backup_root=backup_root,
                    python_executable="/test/python",
                    runner=runtime,
                )

            manifest_path = next(backup_root.glob("*/manifest.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "rolled_back_after_failure")
            self.assertEqual(runtime.version, "0.8.0")
            self.assertEqual(runtime.active_services, set(MANAGED_SERVICES))
            self.assertEqual(PresenceStore(config.db_path).get_observer_state("upgrade"), "before")

    def test_partial_service_stop_is_reversed_before_any_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            PresenceStore(config.db_path)
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            backup_root = root / "backups"
            runtime = FakeRuntime(fail_stop_unit=MANAGED_SERVICES[1])

            with self.assertRaisesRegex(UpgradeError, "before package installation"):
                upgrade_from_wheel(
                    config=config,
                    target_wheel=target,
                    rollback_wheel=rollback,
                    authorized=True,
                    backup_root=backup_root,
                    python_executable="/test/python",
                    runner=runtime,
                )

            manifest_path = next(backup_root.glob("*/manifest.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "aborted_before_install")
            self.assertEqual(runtime.active_services, set(MANAGED_SERVICES))
            self.assertEqual(runtime.version, "0.8.0")
            self.assertFalse(any(command[1:4] == ("-m", "pip", "install") for command in runtime.commands))

    def test_partial_service_start_is_stopped_before_automatic_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            PresenceStore(config.db_path)
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            backup_root = root / "backups"
            runtime = FakeRuntime(fail_start_unit_once=MANAGED_SERVICES[1])

            with self.assertRaisesRegex(UpgradeError, "was rolled back"):
                upgrade_from_wheel(
                    config=config,
                    target_wheel=target,
                    rollback_wheel=rollback,
                    authorized=True,
                    backup_root=backup_root,
                    python_executable="/test/python",
                    runner=runtime,
                )

            first_service = MANAGED_SERVICES[0]
            first_start = runtime.commands.index(("systemctl", "--user", "start", first_service))
            later_stop = runtime.commands.index(
                ("systemctl", "--user", "stop", first_service),
                first_start,
            )
            rollback_install = max(
                index
                for index, command in enumerate(runtime.commands)
                if command[1:4] == ("-m", "pip", "install")
            )
            self.assertLess(later_stop, rollback_install)
            self.assertEqual(runtime.version, "0.8.0")
            self.assertEqual(runtime.active_services, set(MANAGED_SERVICES))

    def test_manual_rollback_restores_original_database_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            store = PresenceStore(config.db_path)
            store.set_observer_state("upgrade", "before")
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            backup_root = root / "backups"
            runtime = FakeRuntime()
            upgraded = upgrade_from_wheel(
                config=config,
                target_wheel=target,
                rollback_wheel=rollback,
                authorized=True,
                backup_root=backup_root,
                python_executable="/test/python",
                runner=runtime,
            )
            assert upgraded.manifest_path is not None
            PresenceStore(config.db_path).set_observer_state("upgrade", "after")

            result = rollback_upgrade(
                config=config,
                manifest_path=upgraded.manifest_path,
                authorized=True,
                restore_database=True,
                backup_root=backup_root,
                python_executable="/test/python",
                runner=runtime,
            )

            self.assertEqual(result.status, "manually_rolled_back")
            self.assertEqual(runtime.version, "0.8.0")
            self.assertEqual(runtime.active_services, set(MANAGED_SERVICES))
            self.assertEqual(PresenceStore(config.db_path).get_observer_state("upgrade"), "before")

    def test_authorization_and_manifest_checksum_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            PresenceStore(config.db_path)
            target = make_wheel(root, "0.9.0")
            rollback = make_wheel(root, "0.8.0")
            backup_root = root / "backups"
            runtime = FakeRuntime()

            with self.assertRaisesRegex(UpgradeError, "requires --authorize-once"):
                upgrade_from_wheel(
                    config=config,
                    target_wheel=target,
                    rollback_wheel=rollback,
                    authorized=False,
                    backup_root=backup_root,
                    python_executable="/test/python",
                    runner=runtime,
                )

            upgraded = upgrade_from_wheel(
                config=config,
                target_wheel=target,
                rollback_wheel=rollback,
                authorized=True,
                backup_root=backup_root,
                python_executable="/test/python",
                runner=runtime,
            )
            assert upgraded.manifest_path is not None
            manifest = json.loads(upgraded.manifest_path.read_text(encoding="utf-8"))
            rollback_copy = upgraded.manifest_path.parent / manifest["rollback_wheel"]["filename"]
            rollback_copy.write_bytes(rollback_copy.read_bytes() + b"tampered")

            with self.assertRaisesRegex(UpgradeError, "checksum failed"):
                rollback_upgrade(
                    config=config,
                    manifest_path=upgraded.manifest_path,
                    authorized=True,
                    restore_database=True,
                    backup_root=backup_root,
                    python_executable="/test/python",
                    runner=runtime,
                )


if __name__ == "__main__":
    unittest.main()
