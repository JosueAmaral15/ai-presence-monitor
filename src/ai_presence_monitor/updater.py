from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import AppConfig, user_state_dir
from .store import SCHEMA_VERSION, inspect_schema

MANIFEST_VERSION = 1
MANAGED_SERVICES = (
    "ai-presence-monitor.service",
    "ai-presence-reply-observer.service",
)
PACKAGE_NAME = "ai-presence-monitor"
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[A-Za-z0-9_.+-]*)?$")


class UpgradeError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpgradeResult:
    status: str
    from_version: str
    to_version: str
    manifest_path: Path | None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
        }


Runner = Callable[..., subprocess.CompletedProcess[str]]


def upgrade_from_wheel(
    *,
    config: AppConfig,
    target_wheel: Path,
    rollback_wheel: Path,
    authorized: bool,
    dry_run: bool = False,
    backup_root: Path | None = None,
    python_executable: str | None = None,
    runner: Runner = subprocess.run,
) -> UpgradeResult:
    _require_linux()
    if not dry_run and not authorized:
        raise UpgradeError("Upgrade requires --authorize-once.")
    python = python_executable or sys.executable
    target = _validated_wheel(target_wheel)
    rollback = _validated_wheel(rollback_wheel)
    target_version = read_wheel_version(target)
    rollback_version = read_wheel_version(rollback)
    current_version = installed_version(python, runner=runner)
    if rollback_version != current_version:
        raise UpgradeError(
            "Rollback wheel does not match the installed runtime: "
            f"installed={current_version} rollback={rollback_version}."
        )
    if target_version == current_version:
        raise UpgradeError("Target wheel is already installed.")
    _validate_database_preflight(config.db_path)
    active_services = _active_services(runner)

    if dry_run:
        return UpgradeResult(
            status="would_upgrade",
            from_version=current_version,
            to_version=target_version,
            manifest_path=None,
        )

    root = (backup_root or user_state_dir() / "backups").expanduser().resolve()
    backup_dir = _create_backup_directory(root, current_version, target_version)
    target_copy = _copy_private(target, backup_dir / target.name)
    rollback_copy = _copy_private(rollback, backup_dir / rollback.name)
    database_copy = backup_dir / "presence.db.before-upgrade"
    _backup_database(config.db_path, database_copy)
    manifest_path = backup_dir / "manifest.json"
    manifest: dict[str, object] = {
        "manifest_version": MANIFEST_VERSION,
        "status": "prepared",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "from_version": current_version,
        "to_version": target_version,
        "target_wheel": _artifact_entry(target_copy),
        "rollback_wheel": _artifact_entry(rollback_copy),
        "database": {
            "path": str(config.db_path.expanduser().resolve()),
            **_artifact_entry(database_copy),
        },
        "active_services": list(active_services),
    }
    _write_manifest(manifest_path, manifest)

    stopped_services: list[str] = []
    try:
        for unit in active_services:
            _stop_service(unit, runner)
            stopped_services.append(unit)
    except Exception as exc:
        try:
            _start_services(tuple(stopped_services), runner)
            manifest["status"] = "aborted_before_install"
            manifest["failure_code"] = type(exc).__name__[:64]
            _write_manifest(manifest_path, manifest)
        except Exception as restore_exc:
            manifest["status"] = "service_restore_failed"
            manifest["failure_code"] = type(exc).__name__[:64]
            manifest["restore_failure_code"] = type(restore_exc).__name__[:64]
            _write_manifest(manifest_path, manifest)
            raise UpgradeError(
                f"Service stop failed and service restoration failed; inspect {manifest_path}."
            ) from restore_exc
        raise UpgradeError(
            f"Service stop failed before package installation; inspect {manifest_path}."
        ) from exc

    started_services: list[str] = []
    try:
        _install_wheel(python, target_copy, runner)
        _initialize_runtime(python, config.env_path, runner)
        _verify_runtime(python, target_version, config.env_path, runner)
        for unit in active_services:
            _start_service(unit, runner)
            started_services.append(unit)
        manifest["status"] = "completed"
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        _write_manifest(manifest_path, manifest)
        return UpgradeResult(
            status="completed",
            from_version=current_version,
            to_version=target_version,
            manifest_path=manifest_path,
        )
    except Exception as exc:
        failure_code = type(exc).__name__[:64]
        try:
            for unit in reversed(started_services):
                _stop_service(unit, runner)
            _install_wheel(python, rollback_copy, runner)
            _restore_database(database_copy, config.db_path)
            _verify_installed_version(python, current_version, runner)
            _start_services(active_services, runner)
            manifest["status"] = "rolled_back_after_failure"
            manifest["failure_code"] = failure_code
            manifest["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
            _write_manifest(manifest_path, manifest)
        except Exception as rollback_exc:
            manifest["status"] = "rollback_failed"
            manifest["failure_code"] = failure_code
            manifest["rollback_failure_code"] = type(rollback_exc).__name__[:64]
            _write_manifest(manifest_path, manifest)
            raise UpgradeError(
                f"Upgrade failed and automatic rollback failed; inspect {manifest_path}."
            ) from rollback_exc
        raise UpgradeError(
            f"Upgrade failed and was rolled back; inspect {manifest_path}."
        ) from exc


def rollback_upgrade(
    *,
    config: AppConfig,
    manifest_path: Path,
    authorized: bool,
    restore_database: bool,
    dry_run: bool = False,
    backup_root: Path | None = None,
    python_executable: str | None = None,
    runner: Runner = subprocess.run,
) -> UpgradeResult:
    _require_linux()
    if not dry_run and not authorized:
        raise UpgradeError("Rollback requires --authorize-once.")
    if not dry_run and not restore_database:
        raise UpgradeError("Rollback requires --restore-database acknowledgement.")
    root = (backup_root or user_state_dir() / "backups").expanduser().resolve()
    manifest_file = manifest_path.expanduser().resolve()
    if not manifest_file.is_relative_to(root) or manifest_file.name != "manifest.json":
        raise UpgradeError("Manifest must be inside the managed backup directory.")
    manifest = _load_manifest(manifest_file)
    if manifest.get("status") != "completed":
        raise UpgradeError("Only a completed upgrade can be rolled back manually.")
    from_version = _manifest_string(manifest, "from_version")
    to_version = _manifest_string(manifest, "to_version")
    rollback_wheel = _manifest_artifact(manifest_file.parent, manifest, "rollback_wheel")
    target_wheel = _manifest_artifact(manifest_file.parent, manifest, "target_wheel")
    database_backup = _manifest_artifact(manifest_file.parent, manifest, "database")
    database_entry = manifest.get("database")
    assert isinstance(database_entry, dict)
    if Path(_manifest_string(database_entry, "path")).resolve() != config.db_path.resolve():
        raise UpgradeError("Manifest database does not match the configured database.")
    active_services = _manifest_services(manifest)
    python = python_executable or sys.executable
    current_version = installed_version(python, runner=runner)
    if current_version != to_version:
        raise UpgradeError(
            "Installed runtime does not match the completed upgrade: "
            f"installed={current_version} manifest={to_version}."
        )

    if dry_run:
        return UpgradeResult(
            status="would_rollback",
            from_version=to_version,
            to_version=from_version,
            manifest_path=manifest_file,
        )

    pre_rollback = manifest_file.parent / "presence.db.before-manual-rollback"
    _backup_database(config.db_path, pre_rollback)
    manifest["pre_rollback_database"] = _artifact_entry(pre_rollback)
    _write_manifest(manifest_file, manifest)

    stopped_services: list[str] = []
    try:
        for unit in active_services:
            _stop_service(unit, runner)
            stopped_services.append(unit)
    except Exception as exc:
        try:
            _start_services(tuple(stopped_services), runner)
            manifest["rollback_attempt_failure_code"] = type(exc).__name__[:64]
            _write_manifest(manifest_file, manifest)
        except Exception as restore_exc:
            manifest["status"] = "rollback_service_restore_failed"
            manifest["rollback_failure_code"] = type(exc).__name__[:64]
            manifest["restore_failure_code"] = type(restore_exc).__name__[:64]
            _write_manifest(manifest_file, manifest)
            raise UpgradeError(
                f"Service stop failed and service restoration failed; inspect {manifest_file}."
            ) from restore_exc
        raise UpgradeError(
            f"Service stop failed before rollback installation; inspect {manifest_file}."
        ) from exc

    manifest["status"] = "rollback_prepared"
    _write_manifest(manifest_file, manifest)
    started_services: list[str] = []
    try:
        _install_wheel(python, rollback_wheel, runner)
        _restore_database(database_backup, config.db_path)
        _verify_installed_version(python, from_version, runner)
        for unit in active_services:
            _start_service(unit, runner)
            started_services.append(unit)
        manifest["status"] = "manually_rolled_back"
        manifest["manually_rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        _write_manifest(manifest_file, manifest)
        return UpgradeResult(
            status="manually_rolled_back",
            from_version=to_version,
            to_version=from_version,
            manifest_path=manifest_file,
        )
    except Exception as exc:
        failure_code = type(exc).__name__[:64]
        try:
            for unit in reversed(started_services):
                _stop_service(unit, runner)
            _install_wheel(python, target_wheel, runner)
            _restore_database(pre_rollback, config.db_path)
            _verify_installed_version(python, to_version, runner)
            _start_services(active_services, runner)
            manifest["status"] = "rollback_reverted_after_failure"
            manifest["rollback_failure_code"] = failure_code
            _write_manifest(manifest_file, manifest)
        except Exception as recovery_exc:
            manifest["status"] = "rollback_recovery_failed"
            manifest["rollback_failure_code"] = failure_code
            manifest["recovery_failure_code"] = type(recovery_exc).__name__[:64]
            _write_manifest(manifest_file, manifest)
            raise UpgradeError(
                f"Rollback and recovery failed; inspect {manifest_file}."
            ) from recovery_exc
        raise UpgradeError(
            f"Rollback failed and the upgraded state was restored; inspect {manifest_file}."
        ) from exc


def read_wheel_version(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_files = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_files) != 1:
                raise UpgradeError("Wheel must contain exactly one METADATA file.")
            content = archive.read(metadata_files[0]).decode("utf-8")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, KeyError) as exc:
        raise UpgradeError("Wheel metadata is unreadable.") from exc
    fields = {}
    for line in content.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            if key in {"Name", "Version"}:
                fields[key] = value.strip()
    if fields.get("Name", "").lower().replace("_", "-") != PACKAGE_NAME:
        raise UpgradeError("Wheel package name is not ai-presence-monitor.")
    version = fields.get("Version", "")
    if not _VERSION.fullmatch(version):
        raise UpgradeError("Wheel version is invalid.")
    return version


def installed_version(python_executable: str, *, runner: Runner = subprocess.run) -> str:
    result = _run_checked(
        [
            python_executable,
            "-c",
            "import ai_presence_monitor; print(ai_presence_monitor.__version__)",
        ],
        runner,
        failure="installed_version_unavailable",
        cwd=Path("/tmp"),
        env=_clean_environment(),
    )
    version = result.stdout.strip()
    if not _VERSION.fullmatch(version):
        raise UpgradeError("Installed runtime returned an invalid version.")
    return version


def _validated_wheel(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.suffix != ".whl":
        raise UpgradeError("Package path must be an existing local wheel.")
    read_wheel_version(resolved)
    return resolved


def _validate_database_preflight(path: Path) -> None:
    schema = inspect_schema(path)
    if not schema.database_exists:
        raise UpgradeError("Configured database is missing; run init before upgrade.")
    if schema.integrity != "ok" or schema.migration_status in {"newer", "unreadable"}:
        raise UpgradeError("Database preflight failed.")
    if schema.current_version is not None and schema.current_version > SCHEMA_VERSION:
        raise UpgradeError("Database schema is newer than this updater.")
    if schema.missing_tables:
        raise UpgradeError("Database preflight found missing required tables.")


def _require_linux() -> None:
    if not sys.platform.startswith("linux"):
        raise UpgradeError("Transactional upgrade is supported only on Linux.")


def _create_backup_directory(root: Path, old: str, new: str) -> Path:
    try:
        root.mkdir(parents=True, exist_ok=True)
        root.chmod(0o700)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = root / f"upgrade-{old}-to-{new}-{timestamp}-{uuid.uuid4().hex[:8]}"
        target.mkdir(mode=0o700)
    except OSError as exc:
        raise UpgradeError("Backup directory creation failed.") from exc
    return target


def _copy_private(source: Path, target: Path) -> Path:
    try:
        shutil.copy2(source, target)
        target.chmod(0o600)
    except OSError as exc:
        raise UpgradeError("Upgrade artifact copy failed.") from exc
    return target


def _backup_database(source: Path, target: Path) -> None:
    if not source.is_file():
        raise UpgradeError("Configured database is missing.")
    try:
        with sqlite3.connect(source) as current, sqlite3.connect(target) as backup:
            current.backup(backup)
    except (OSError, sqlite3.Error) as exc:
        raise UpgradeError("Database backup failed.") from exc
    try:
        target.chmod(0o600)
    except OSError as exc:
        raise UpgradeError("Database backup permissions could not be secured.") from exc


def _restore_database(source: Path, target: Path) -> None:
    try:
        with sqlite3.connect(source) as backup, sqlite3.connect(target) as current:
            backup.backup(current)
    except (OSError, sqlite3.Error) as exc:
        raise UpgradeError("Database restore failed.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise UpgradeError("Upgrade artifact could not be hashed.") from exc
    return digest.hexdigest()


def _artifact_entry(path: Path) -> dict[str, str]:
    return {"filename": path.name, "sha256": _sha256(path)}


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix=".manifest.", suffix=".tmp", dir=path.parent, text=True
        )
        temporary = Path(temporary_name)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)
    except OSError as exc:
        raise UpgradeError("Upgrade manifest write failed.") from exc
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpgradeError("Upgrade manifest is unreadable.") from exc
    if not isinstance(payload, dict) or payload.get("manifest_version") != MANIFEST_VERSION:
        raise UpgradeError("Upgrade manifest version is unsupported.")
    return payload


def _manifest_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise UpgradeError(f"Manifest field is invalid: {key}.")
    return value


def _manifest_artifact(
    backup_dir: Path,
    manifest: dict[str, object],
    key: str,
) -> Path:
    entry = manifest.get(key)
    if not isinstance(entry, dict):
        raise UpgradeError(f"Manifest artifact is invalid: {key}.")
    filename = _manifest_string(entry, "filename")
    if Path(filename).name != filename:
        raise UpgradeError(f"Manifest artifact path is invalid: {key}.")
    path = backup_dir / filename
    expected_hash = _manifest_string(entry, "sha256")
    if not path.is_file() or _sha256(path) != expected_hash:
        raise UpgradeError(f"Manifest artifact checksum failed: {key}.")
    return path


def _manifest_services(manifest: dict[str, object]) -> tuple[str, ...]:
    values = manifest.get("active_services")
    if not isinstance(values, list):
        raise UpgradeError("Manifest active_services is invalid.")
    services = tuple(value for value in values if isinstance(value, str))
    if len(services) != len(values) or not set(services).issubset(MANAGED_SERVICES):
        raise UpgradeError("Manifest contains unmanaged services.")
    return services


def _active_services(runner: Runner) -> tuple[str, ...]:
    active = []
    for unit in MANAGED_SERVICES:
        try:
            result = runner(
                ["systemctl", "--user", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=10.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpgradeError("Could not determine managed service state.") from exc
        if result.returncode == 0 and result.stdout.strip() == "active":
            active.append(unit)
        elif result.returncode not in {3, 4}:
            raise UpgradeError("Could not determine managed service state.")
    return tuple(active)


def _stop_service(unit: str, runner: Runner) -> None:
    _run_checked(
        ["systemctl", "--user", "stop", unit],
        runner,
        failure="service_stop_failed",
    )


def _start_service(unit: str, runner: Runner) -> None:
    _run_checked(
        ["systemctl", "--user", "start", unit],
        runner,
        failure="service_start_failed",
    )


def _start_services(services: tuple[str, ...], runner: Runner) -> None:
    for unit in services:
        _start_service(unit, runner)


def _install_wheel(python: str, wheel: Path, runner: Runner) -> None:
    _run_checked(
        [
            python,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--upgrade",
            "--force-reinstall",
            str(wheel),
        ],
        runner,
        failure="package_install_failed",
        cwd=Path("/tmp"),
        env=_clean_environment(),
    )


def _initialize_runtime(python: str, env_file: Path, runner: Runner) -> None:
    _run_checked(
        [python, "-m", "ai_presence_monitor", "--env-file", str(env_file), "init"],
        runner,
        failure="database_migration_failed",
        cwd=Path("/tmp"),
        env=_clean_environment(),
    )


def _verify_runtime(
    python: str,
    expected_version: str,
    env_file: Path,
    runner: Runner,
) -> None:
    _verify_installed_version(python, expected_version, runner)
    result = _run_checked(
        [
            python,
            "-m",
            "ai_presence_monitor",
            "--env-file",
            str(env_file),
            "doctor",
            "--json",
        ],
        runner,
        failure="postflight_doctor_failed",
        cwd=Path("/tmp"),
        env=_clean_environment(),
    )
    try:
        status = json.loads(result.stdout).get("status")
    except (AttributeError, json.JSONDecodeError) as exc:
        raise UpgradeError("Postflight doctor returned invalid JSON.") from exc
    if status == "error":
        raise UpgradeError("Postflight doctor reported an error.")


def _verify_installed_version(
    python: str,
    expected_version: str,
    runner: Runner,
) -> None:
    actual = installed_version(python, runner=runner)
    if actual != expected_version:
        raise UpgradeError(
            f"Installed version mismatch: expected={expected_version} actual={actual}."
        )


def _clean_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _run_checked(
    command: list[str],
    runner: Runner,
    *,
    failure: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            timeout=120.0,
            check=False,
            cwd=cwd,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpgradeError(failure) from exc
    if result.returncode != 0:
        raise UpgradeError(failure)
    return result
