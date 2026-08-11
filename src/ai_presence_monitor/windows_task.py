from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from .background_service import (
    BackgroundServiceError,
    BackgroundServiceResult,
    validate_component,
)
from .config import APP_DIR_NAME

TASK_NAMES = {
    "monitor": "AI Presence Monitor",
    "reply-observer": "AI Presence Reply Observer",
}
TASK_COMMANDS = {
    "monitor": "monitor",
    "reply-observer": "observe-replies",
}


def _windows_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME


def default_task_definition_path(component: str) -> Path:
    validate_component(component)
    filename = "monitor-task.xml" if component == "monitor" else "reply-observer-task.xml"
    return _windows_data_dir() / "tasks" / filename


def _current_windows_user() -> str:
    username = os.environ.get("USERNAME") or getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    return f"{domain}\\{username}" if domain else username


def render_task_definition(
    *,
    component: str,
    env_file: Path,
    python_executable: str | None = None,
    user_id: str | None = None,
) -> str:
    validate_component(component)
    python = Path(python_executable or sys.executable).expanduser().resolve()
    resolved_env = env_file.expanduser().resolve()
    arguments = subprocess.list2cmdline(
        [
            "-m",
            "ai_presence_monitor",
            "--env-file",
            str(resolved_env),
            TASK_COMMANDS[component],
        ]
    )
    description = (
        "AI Presence continuous monitor"
        if component == "monitor"
        else "AI Presence Discord reply observer"
    )
    account = user_id or _current_windows_user()
    return "\n".join(
        (
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">',
            "  <RegistrationInfo>",
            f"    <Description>{escape(description)}</Description>",
            "  </RegistrationInfo>",
            "  <Triggers>",
            "    <LogonTrigger>",
            "      <Enabled>true</Enabled>",
            f"      <UserId>{escape(account)}</UserId>",
            "    </LogonTrigger>",
            "  </Triggers>",
            "  <Principals>",
            '    <Principal id="Author">',
            f"      <UserId>{escape(account)}</UserId>",
            "      <LogonType>InteractiveToken</LogonType>",
            "      <RunLevel>LeastPrivilege</RunLevel>",
            "    </Principal>",
            "  </Principals>",
            "  <Settings>",
            "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>",
            "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>",
            "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>",
            "    <StartWhenAvailable>true</StartWhenAvailable>",
            "    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>",
            "    <RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>",
            "    <Enabled>true</Enabled>",
            "  </Settings>",
            '  <Actions Context="Author">',
            "    <Exec>",
            f"      <Command>{escape(str(python))}</Command>",
            f"      <Arguments>{escape(arguments)}</Arguments>",
            f"      <WorkingDirectory>{escape(str(resolved_env.parent))}</WorkingDirectory>",
            "    </Exec>",
            "  </Actions>",
            "</Task>",
            "",
        )
    )


class WindowsTaskSchedulerService:
    def install(
        self,
        *,
        component: str,
        env_file: Path,
        target_path: Path | None = None,
        python_executable: str | None = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> BackgroundServiceResult:
        validate_component(component)
        target = (target_path or default_task_definition_path(component)).expanduser()
        rendered = render_task_definition(
            component=component,
            env_file=env_file,
            python_executable=python_executable,
        )
        current = target.read_text(encoding="utf-8") if target.exists() else None
        task_exists = self._task_exists(TASK_NAMES[component]) if not dry_run else False
        changed = current != rendered or not task_exists
        backup_path = None
        if not dry_run:
            self._require_schtasks()
            target.parent.mkdir(parents=True, exist_ok=True)
            if current != rendered:
                if backup and target.exists():
                    backup_path = self._backup(target)
                temporary = target.with_suffix(".tmp")
                temporary.write_text(rendered, encoding="utf-8")
                temporary.replace(target)
            self._run(
                [
                    "schtasks.exe",
                    "/Create",
                    "/TN",
                    TASK_NAMES[component],
                    "/XML",
                    str(target.resolve()),
                    "/F",
                ]
            )
        return BackgroundServiceResult(
            action="install",
            component=component,
            target_path=target,
            changed=changed,
            backup_path=backup_path,
            rendered_definition=rendered,
            follow_up_commands=(
                f'schtasks.exe /Run /TN "{TASK_NAMES[component]}"',
            ),
        )

    def uninstall(
        self,
        *,
        component: str,
        target_path: Path | None = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> BackgroundServiceResult:
        validate_component(component)
        target = (target_path or default_task_definition_path(component)).expanduser()
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        task_exists = self._task_exists(TASK_NAMES[component]) if not dry_run else target.exists()
        changed = task_exists or target.exists()
        backup_path = None
        if not dry_run:
            self._require_schtasks()
            if task_exists:
                self._run(
                    [
                        "schtasks.exe",
                        "/Delete",
                        "/TN",
                        TASK_NAMES[component],
                        "/F",
                    ]
                )
            if target.exists():
                if backup:
                    backup_path = self._backup(target)
                target.unlink()
        return BackgroundServiceResult(
            action="uninstall",
            component=component,
            target_path=target,
            changed=changed,
            backup_path=backup_path,
            rendered_definition=current,
            follow_up_commands=(),
        )

    @staticmethod
    def _require_schtasks() -> None:
        if shutil.which("schtasks.exe") is None:
            raise BackgroundServiceError(
                "schtasks.exe nao foi encontrado; o Task Scheduler nao esta disponivel."
            )

    @staticmethod
    def _task_exists(task_name: str) -> bool:
        if shutil.which("schtasks.exe") is None:
            return False
        result = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", task_name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    @staticmethod
    def _run(command: list[str]) -> None:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise BackgroundServiceError(
                f"Falha ao executar {command[0]}: {exc}"
            ) from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            suffix = f": {detail}" if detail else ""
            raise BackgroundServiceError(
                f"{command[0]} retornou codigo {result.returncode}{suffix}."
            )

    @staticmethod
    def _backup(path: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = path.with_name(f"{path.name}.backup-{timestamp}")
        shutil.copy2(path, backup)
        return backup
