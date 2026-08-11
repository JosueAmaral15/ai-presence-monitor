from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .systemd_service import (
    install_reply_observer_service,
    install_user_service,
    uninstall_reply_observer_service,
    uninstall_user_service,
)

BACKGROUND_COMPONENTS = ("monitor", "reply-observer")


class BackgroundServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackgroundServiceResult:
    action: str
    component: str
    target_path: Path
    changed: bool
    backup_path: Path | None
    rendered_definition: str
    follow_up_commands: tuple[str, ...]


class BackgroundServiceManager(Protocol):
    def install(
        self,
        *,
        component: str,
        env_file: Path,
        target_path: Path | None = None,
        python_executable: str | None = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> BackgroundServiceResult: ...

    def uninstall(
        self,
        *,
        component: str,
        target_path: Path | None = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> BackgroundServiceResult: ...


def validate_component(component: str) -> None:
    if component not in BACKGROUND_COMPONENTS:
        raise BackgroundServiceError(
            f"Componente de execucao continua invalido: {component}."
        )


class LinuxBackgroundServiceManager:
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
        if component == "monitor":
            result = install_user_service(
                env_file=env_file,
                target_path=target_path,
                python_executable=python_executable,
                dry_run=dry_run,
                backup=backup,
            )
            unit = "ai-presence-monitor.service"
        else:
            result = install_reply_observer_service(
                env_file=env_file,
                target_path=target_path,
                python_executable=python_executable,
                dry_run=dry_run,
                backup=backup,
            )
            unit = "ai-presence-reply-observer.service"
        return BackgroundServiceResult(
            action="install",
            component=component,
            target_path=result.target_path,
            changed=result.changed,
            backup_path=result.backup_path,
            rendered_definition=result.rendered_service,
            follow_up_commands=(
                "systemctl --user daemon-reload",
                f"systemctl --user enable --now {unit}",
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
        if component == "monitor":
            result = uninstall_user_service(
                target_path=target_path,
                dry_run=dry_run,
                backup=backup,
            )
            unit = "ai-presence-monitor.service"
        else:
            result = uninstall_reply_observer_service(
                target_path=target_path,
                dry_run=dry_run,
                backup=backup,
            )
            unit = "ai-presence-reply-observer.service"
        return BackgroundServiceResult(
            action="uninstall",
            component=component,
            target_path=result.target_path,
            changed=result.changed,
            backup_path=result.backup_path,
            rendered_definition=result.rendered_service,
            follow_up_commands=(
                f"systemctl --user disable --now {unit}",
                "systemctl --user daemon-reload",
            ),
        )


def print_background_service_result(
    result: BackgroundServiceResult,
    *,
    dry_run: bool,
) -> None:
    mode = "dry-run" if dry_run else "ok"
    print(f"[{mode}] action={result.action}")
    print(f"component={result.component}")
    print(f"target={result.target_path}")
    print(f"changed={str(result.changed).lower()}")
    if result.backup_path:
        print(f"backup={result.backup_path}")
    if dry_run and result.action == "install":
        print(result.rendered_definition, end="")
    for command in result.follow_up_commands:
        print(f"Execute: {command}")
