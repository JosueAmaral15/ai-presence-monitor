from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from . import __version__
from .codex_hook_installer import (
    HOOK_EVENTS,
    count_presence_hooks,
    default_user_hooks_path,
    load_hooks_file,
)
from .config import AppConfig
from .control import ControlError, ControlStore
from .linux_evidence import observe_user_service
from .store import SchemaStatus, inspect_schema

DOCTOR_SERVICES = (
    "ai-presence-monitor.service",
    "ai-presence-reply-observer.service",
)


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: str
    summary: str


@dataclass(frozen=True)
class DoctorReport:
    version: str
    status: str
    checks: tuple[HealthCheck, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "status": self.status,
            "checks": [asdict(check) for check in self.checks],
        }

    def render_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)

    def exit_code(self, *, strict: bool = False) -> int:
        if self.status == "error":
            return 2
        if strict and self.status == "warning":
            return 1
        return 0


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
ExecutableFinder = Callable[[str], str | None]


def collect_doctor_report(
    config: AppConfig,
    *,
    platform_name: str | None = None,
    hooks_path: Path | None = None,
    tray_autostart_path: Path | None = None,
    executable_finder: ExecutableFinder = shutil.which,
    runner: CommandRunner = subprocess.run,
) -> DoctorReport:
    selected_platform = (platform_name or sys.platform).lower()
    checks = [HealthCheck("runtime", "ok", f"ai-presence {__version__}")]
    checks.append(_platform_check(selected_platform, config))
    checks.append(_environment_check(config.env_path))

    schema = inspect_schema(config.db_path)
    checks.append(_schema_check(schema))
    checks.append(_control_check(config))
    checks.append(_hooks_check(hooks_path or default_user_hooks_path()))
    checks.append(_codex_check(executable_finder, runner))

    if selected_platform.startswith("linux"):
        checks.extend(_service_checks(config, runner))
        checks.append(
            _tray_check(
                tray_autostart_path
                or Path.home() / ".config" / "autostart" / "ai-presence-tray.desktop"
            )
        )

    return DoctorReport(
        version=__version__,
        status=_overall_status(checks),
        checks=tuple(checks),
    )


def _overall_status(checks: list[HealthCheck]) -> str:
    statuses = {check.status for check in checks}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _platform_check(platform_name: str, config: AppConfig) -> HealthCheck:
    if platform_name.startswith("linux"):
        return HealthCheck("platform", "ok", "supported Linux runtime")
    if platform_name in {"win32", "windows", "cygwin"}:
        status = "warning" if config.experimental_windows_enabled else "error"
        summary = (
            "experimental Windows runtime enabled"
            if config.experimental_windows_enabled
            else "experimental Windows runtime disabled"
        )
        return HealthCheck("platform", status, summary)
    return HealthCheck("platform", "error", "unsupported runtime platform")


def _environment_check(env_path: Path) -> HealthCheck:
    if not env_path.is_file():
        return HealthCheck("environment", "warning", "environment file is missing")
    try:
        mode = env_path.stat().st_mode & 0o777
    except OSError:
        return HealthCheck("environment", "error", "environment file is unreadable")
    if os.name == "posix" and mode & 0o077:
        return HealthCheck(
            "environment",
            "warning",
            "environment file permissions are broader than 600",
        )
    return HealthCheck("environment", "ok", "environment file is present and private")


def _schema_check(schema: SchemaStatus) -> HealthCheck:
    if not schema.database_exists:
        return HealthCheck("database", "warning", "database is missing; run init")
    if schema.migration_status == "newer":
        return HealthCheck(
            "database",
            "error",
            f"schema {schema.current_version} is newer than runtime {schema.expected_version}",
        )
    if schema.migration_status in {"unreadable"} or schema.integrity != "ok":
        return HealthCheck("database", "error", "database integrity check failed")
    if schema.migration_status == "outdated":
        return HealthCheck(
            "database",
            "warning",
            f"schema {schema.current_version} requires migration to {schema.expected_version}",
        )
    if schema.missing_tables:
        return HealthCheck(
            "database",
            "error",
            f"schema is missing {len(schema.missing_tables)} required tables",
        )
    return HealthCheck(
        "database",
        "ok",
        f"schema {schema.current_version} current; integrity ok",
    )


def _control_check(config: AppConfig) -> HealthCheck:
    try:
        controls = ControlStore.from_config(config).load()
    except ControlError:
        return HealthCheck("controls", "error", "control file is invalid or unreadable")
    summary = (
        f"task_automation={str(controls.task_automation_enabled).lower()} "
        f"native_input={str(controls.native_input_enabled).lower()} "
        f"gui_fallback={str(controls.gui_fallback_enabled).lower()} "
        f"remote_input={str(controls.remote_input_enabled).lower()} "
        f"activity_sync={str(controls.sync_activity_enabled).lower()}"
    )
    return HealthCheck("controls", "ok", summary)


def _hooks_check(path: Path) -> HealthCheck:
    if not path.is_file():
        return HealthCheck("codex_hooks", "warning", "Codex hook file is missing")
    try:
        count = count_presence_hooks(load_hooks_file(path))
    except (OSError, ValueError, json.JSONDecodeError):
        return HealthCheck("codex_hooks", "error", "Codex hook file is invalid")
    expected = len(HOOK_EVENTS)
    if count == expected:
        return HealthCheck("codex_hooks", "ok", f"{count} presence hooks installed")
    return HealthCheck(
        "codex_hooks",
        "warning",
        f"expected {expected} presence hooks; found {count}",
    )


def _codex_check(
    executable_finder: ExecutableFinder,
    runner: CommandRunner,
) -> HealthCheck:
    executable = executable_finder("codex")
    if executable is None:
        return HealthCheck("codex_queue", "warning", "Codex CLI is not in PATH")
    try:
        result = runner(
            [executable, "queue", "--help"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return HealthCheck("codex_queue", "warning", "Codex queue probe failed")
    if result.returncode != 0:
        return HealthCheck("codex_queue", "warning", "Codex queue is unavailable")
    return HealthCheck("codex_queue", "ok", "Codex queue is available")


def _service_checks(config: AppConfig, runner: CommandRunner) -> list[HealthCheck]:
    checks = []
    for unit in DOCTOR_SERVICES:
        observation = observe_user_service(
            unit,
            timeout_seconds=config.linux_service_timeout_seconds,
            runner=runner,
        )
        if observation.state == "active":
            status = "ok"
        elif observation.state == "failed":
            status = "error"
        else:
            status = "warning"
        checks.append(HealthCheck(f"service:{unit}", status, observation.summary))
    return checks


def _tray_check(path: Path) -> HealthCheck:
    if not path.is_file():
        return HealthCheck("tray_autostart", "warning", "tray autostart is not configured")
    try:
        content = path.read_text(encoding="utf-8")
        mode = path.stat().st_mode & 0o777
    except OSError:
        return HealthCheck("tray_autostart", "error", "tray autostart is unreadable")
    if "ai-presence" not in content or " tray" not in content:
        return HealthCheck("tray_autostart", "error", "tray autostart command is invalid")
    if os.name == "posix" and mode & 0o077:
        return HealthCheck("tray_autostart", "warning", "tray autostart permissions exceed 600")
    return HealthCheck("tray_autostart", "ok", "tray autostart is configured")
