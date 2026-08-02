from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class SystemdServiceResult:
    action: str
    target_path: Path
    changed: bool
    backup_path: Path | None
    rendered_service: str


def default_user_service_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / "ai-presence-monitor.service"


def default_reply_observer_service_path() -> Path:
    return (
        Path.home()
        / ".config"
        / "systemd"
        / "user"
        / "ai-presence-reply-observer.service"
    )


def _systemd_quote(value: str | Path) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_user_service(
    *,
    env_file: Path,
    python_executable: str | None = None,
    service_command: str = "monitor",
    description: str = "AI Presence Monitor",
) -> str:
    python = python_executable or sys.executable
    exec_start = " ".join(
        (
            _systemd_quote(python),
            "-m",
            "ai_presence_monitor",
            "--env-file",
            _systemd_quote(env_file.expanduser().resolve()),
            service_command,
        )
    )
    return "\n".join(
        (
            "[Unit]",
            f"Description={description}",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"ExecStart={exec_start}",
            "Restart=always",
            "RestartSec=5",
            "Environment=PYTHONUNBUFFERED=1",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        )
    )


def _backup(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(f"{path.name}.backup-{timestamp}")
    shutil.copy2(path, backup)
    return backup


def install_user_service(
    *,
    env_file: Path,
    target_path: Path | None = None,
    python_executable: str | None = None,
    dry_run: bool = False,
    backup: bool = True,
    service_command: str = "monitor",
    description: str = "AI Presence Monitor",
) -> SystemdServiceResult:
    target = (target_path or default_user_service_path()).expanduser()
    rendered = render_user_service(
        env_file=env_file,
        python_executable=python_executable,
        service_command=service_command,
        description=description,
    )
    current = target.read_text(encoding="utf-8") if target.exists() else None
    changed = current != rendered
    backup_path = None

    if changed and not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        if backup and target.exists():
            backup_path = _backup(target)
        temporary = target.with_name(f"{target.name}.tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.chmod(0o644)
        temporary.replace(target)

    return SystemdServiceResult(
        action="install",
        target_path=target,
        changed=changed,
        backup_path=backup_path,
        rendered_service=rendered,
    )


def install_reply_observer_service(
    *,
    env_file: Path,
    target_path: Path | None = None,
    python_executable: str | None = None,
    dry_run: bool = False,
    backup: bool = True,
) -> SystemdServiceResult:
    return install_user_service(
        env_file=env_file,
        target_path=target_path or default_reply_observer_service_path(),
        python_executable=python_executable,
        dry_run=dry_run,
        backup=backup,
        service_command="observe-replies",
        description="AI Presence Discord Reply Observer",
    )


def uninstall_reply_observer_service(
    *,
    target_path: Path | None = None,
    dry_run: bool = False,
    backup: bool = True,
) -> SystemdServiceResult:
    return uninstall_user_service(
        target_path=target_path or default_reply_observer_service_path(),
        dry_run=dry_run,
        backup=backup,
    )


def uninstall_user_service(
    *,
    target_path: Path | None = None,
    dry_run: bool = False,
    backup: bool = True,
) -> SystemdServiceResult:
    target = (target_path or default_user_service_path()).expanduser()
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    changed = target.exists()
    backup_path = None

    if changed and not dry_run:
        if backup:
            backup_path = _backup(target)
        target.unlink()

    return SystemdServiceResult(
        action="uninstall",
        target_path=target,
        changed=changed,
        backup_path=backup_path,
        rendered_service=current,
    )


def print_result(result: SystemdServiceResult, dry_run: bool = False) -> None:
    mode = "dry-run" if dry_run else "ok"
    print(f"[{mode}] action={result.action}")
    print(f"target={result.target_path}")
    print(f"changed={str(result.changed).lower()}")
    if result.backup_path:
        print(f"backup={result.backup_path}")
    if dry_run and result.action == "install":
        print(result.rendered_service, end="")
