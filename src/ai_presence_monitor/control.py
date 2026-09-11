from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .config import AppConfig

CONTROL_VERSION = 1
CONTROL_NAMES = (
    "task-automation",
    "native-input",
    "gui-fallback",
    "remote-input",
    "activity-sync",
)


class ControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlSettings:
    task_automation_enabled: bool = False
    native_input_enabled: bool = True
    gui_fallback_enabled: bool = False
    remote_input_enabled: bool = False
    sync_activity_enabled: bool = True
    codex_thread_id: str | None = None
    codex_remote: str | None = None
    remote_auth_token_env: str | None = None

    @classmethod
    def from_config(cls, config: AppConfig) -> ControlSettings:
        return cls(
            task_automation_enabled=config.task_automation_enabled,
            native_input_enabled=config.native_input_enabled,
            gui_fallback_enabled=(
                config.gui_fallback_enabled or config.gui_answer_enabled
            ),
            remote_input_enabled=config.remote_input_enabled,
            sync_activity_enabled=config.continue_sync_activity,
            codex_thread_id=config.codex_thread_id,
            codex_remote=config.codex_remote,
            remote_auth_token_env=config.codex_remote_auth_token_env,
        )

    def with_control(self, name: str, enabled: bool) -> ControlSettings:
        if name == "task-automation":
            return replace(self, task_automation_enabled=enabled)
        if name == "native-input":
            return replace(self, native_input_enabled=enabled)
        if name == "gui-fallback":
            return replace(self, gui_fallback_enabled=enabled)
        if name == "remote-input":
            return replace(self, remote_input_enabled=enabled)
        if name == "activity-sync":
            return replace(self, sync_activity_enabled=enabled)
        raise ControlError(f"Controle desconhecido: {name}")

    def with_target(
        self,
        *,
        thread_id: str | None,
        remote: str | None,
        remote_auth_token_env: str | None,
    ) -> ControlSettings:
        return replace(
            self,
            codex_thread_id=_clean_optional(thread_id),
            codex_remote=_clean_optional(remote),
            remote_auth_token_env=_clean_optional(remote_auth_token_env),
        )


class ControlStore:
    def __init__(self, path: Path, defaults: ControlSettings):
        self.path = path.expanduser()
        self.defaults = defaults

    @classmethod
    def from_config(cls, config: AppConfig) -> ControlStore:
        path = config.control_path or config.env_path.parent / "control.json"
        return cls(path, ControlSettings.from_config(config))

    def load(self) -> ControlSettings:
        if not self.path.exists():
            return self.defaults
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlError(f"Nao foi possivel ler {self.path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ControlError(f"Controle invalido em {self.path}: esperado objeto JSON.")
        version = payload.get("version", CONTROL_VERSION)
        if version != CONTROL_VERSION:
            raise ControlError(
                f"Versao de controle nao suportada em {self.path}: {version!r}."
            )
        values = payload.get("settings", payload)
        if not isinstance(values, dict):
            raise ControlError(f"Controle invalido em {self.path}: settings ausente.")
        return ControlSettings(
            task_automation_enabled=_bool_value(
                values,
                "task_automation_enabled",
                self.defaults.task_automation_enabled,
            ),
            native_input_enabled=_bool_value(
                values,
                "native_input_enabled",
                self.defaults.native_input_enabled,
            ),
            gui_fallback_enabled=_bool_value(
                values,
                "gui_fallback_enabled",
                self.defaults.gui_fallback_enabled,
            ),
            remote_input_enabled=_bool_value(
                values,
                "remote_input_enabled",
                self.defaults.remote_input_enabled,
            ),
            sync_activity_enabled=_bool_value(
                values,
                "sync_activity_enabled",
                self.defaults.sync_activity_enabled,
            ),
            codex_thread_id=_optional_string(
                values,
                "codex_thread_id",
                self.defaults.codex_thread_id,
            ),
            codex_remote=_optional_string(
                values,
                "codex_remote",
                self.defaults.codex_remote,
            ),
            remote_auth_token_env=_optional_string(
                values,
                "remote_auth_token_env",
                self.defaults.remote_auth_token_env,
            ),
        )

    def save(self, settings: ControlSettings) -> None:
        parent_existed = self.path.parent.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed:
            _chmod(self.path.parent, 0o700)
        payload = {
            "version": CONTROL_VERSION,
            "settings": asdict(settings),
        }
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            _chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.path)
            _chmod(self.path, 0o600)
        except OSError as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ControlError(
                f"Nao foi possivel gravar {self.path}: {exc}"
            ) from exc
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None


def _bool_value(values: dict[str, Any], key: str, default: bool) -> bool:
    value = values.get(key, default)
    if not isinstance(value, bool):
        raise ControlError(f"Controle {key!r} precisa ser booleano.")
    return value


def _optional_string(
    values: dict[str, Any],
    key: str,
    default: str | None,
) -> str | None:
    value = values.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ControlError(f"Controle {key!r} precisa ser texto ou null.")
    return _clean_optional(value)


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        # Windows ACLs are not represented by POSIX modes.
        pass
