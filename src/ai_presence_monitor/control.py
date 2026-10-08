from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .config import AppConfig

CONTROL_VERSION = 1
DEFAULT_SCHEDULED_PROMPT_DELAY_MINUTES = 210
DEFAULT_SCHEDULED_PROMPT_TEXT = "continue"
MAX_SCHEDULED_PROMPT_DELAY_MINUTES = 10_080
MAX_SCHEDULED_PROMPT_TEXT_LENGTH = 4_000
MAX_CONTROL_PROFILE_ID_LENGTH = 512
SCHEDULED_PROMPT_STATES = frozenset(
    {
        "disabled",
        "armed",
        "dispatching",
        "dispatch_started",
        "input_emitted",
        "failed_or_uncertain",
    }
)
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
    scheduled_prompt_enabled: bool = False
    scheduled_prompt_delay_minutes: int = DEFAULT_SCHEDULED_PROMPT_DELAY_MINUTES
    scheduled_prompt_text: str = DEFAULT_SCHEDULED_PROMPT_TEXT
    scheduled_prompt_require_red_inactivity: bool = False
    scheduled_prompt_thread_id: str | None = None
    scheduled_prompt_due_at: float | None = None
    scheduled_prompt_id: str | None = None
    scheduled_prompt_last_state: str = "disabled"
    scheduled_prompt_last_attempt_at: float | None = None

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

    def load(self, profile_id: str | None = None) -> ControlSettings:
        clean_profile_id = _clean_profile_id(profile_id)
        payload = self._read_payload()
        global_settings = self._settings_from_values(
            self._global_values(payload),
            defaults=self.defaults,
        )
        if clean_profile_id is None:
            return global_settings
        profile_defaults = _profile_defaults(global_settings)
        profiles = self._profile_values(payload)
        values = profiles.get(clean_profile_id)
        if values is None:
            return profile_defaults
        return self._settings_from_values(values, defaults=profile_defaults)

    def list_profile_ids(self) -> tuple[str, ...]:
        payload = self._read_payload()
        profiles = self._profile_values(payload)
        return tuple(sorted(profiles))

    def save(
        self,
        settings: ControlSettings,
        profile_id: str | None = None,
    ) -> None:
        _validate_scheduled_prompt(settings)
        clean_profile_id = _clean_profile_id(profile_id)
        existing = self._read_payload()
        global_settings = self._settings_from_values(
            self._global_values(existing),
            defaults=self.defaults,
        )
        profiles = dict(self._profile_values(existing))
        if clean_profile_id is None:
            global_settings = settings
        else:
            profiles[clean_profile_id] = asdict(settings)
        payload = {
            "version": CONTROL_VERSION,
            "settings": asdict(global_settings),
            "profiles": profiles,
        }
        self._write_payload(payload)

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
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
        return payload

    def _global_values(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = payload.get("settings", payload)
        if not isinstance(values, dict):
            raise ControlError(f"Controle invalido em {self.path}: settings ausente.")
        return values

    def _profile_values(
        self,
        payload: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        raw_profiles = payload.get("profiles", {})
        if not isinstance(raw_profiles, dict):
            raise ControlError(f"Controle invalido em {self.path}: profiles invalido.")
        profiles: dict[str, dict[str, Any]] = {}
        for profile_id, values in raw_profiles.items():
            clean_profile_id = _clean_profile_id(profile_id)
            if clean_profile_id is None or clean_profile_id != profile_id:
                raise ControlError(
                    f"Controle invalido em {self.path}: perfil invalido."
                )
            if not isinstance(values, dict):
                raise ControlError(
                    f"Controle invalido em {self.path}: perfil sem settings."
                )
            profiles[clean_profile_id] = values
        return profiles

    def _settings_from_values(
        self,
        values: dict[str, Any],
        *,
        defaults: ControlSettings,
    ) -> ControlSettings:
        settings = ControlSettings(
            task_automation_enabled=_bool_value(
                values,
                "task_automation_enabled",
                defaults.task_automation_enabled,
            ),
            native_input_enabled=_bool_value(
                values,
                "native_input_enabled",
                defaults.native_input_enabled,
            ),
            gui_fallback_enabled=_bool_value(
                values,
                "gui_fallback_enabled",
                defaults.gui_fallback_enabled,
            ),
            remote_input_enabled=_bool_value(
                values,
                "remote_input_enabled",
                defaults.remote_input_enabled,
            ),
            sync_activity_enabled=_bool_value(
                values,
                "sync_activity_enabled",
                defaults.sync_activity_enabled,
            ),
            codex_thread_id=_optional_string(
                values,
                "codex_thread_id",
                defaults.codex_thread_id,
            ),
            codex_remote=_optional_string(
                values,
                "codex_remote",
                defaults.codex_remote,
            ),
            remote_auth_token_env=_optional_string(
                values,
                "remote_auth_token_env",
                defaults.remote_auth_token_env,
            ),
            scheduled_prompt_enabled=_bool_value(
                values,
                "scheduled_prompt_enabled",
                defaults.scheduled_prompt_enabled,
            ),
            scheduled_prompt_delay_minutes=_int_value(
                values,
                "scheduled_prompt_delay_minutes",
                defaults.scheduled_prompt_delay_minutes,
                minimum=1,
                maximum=MAX_SCHEDULED_PROMPT_DELAY_MINUTES,
            ),
            scheduled_prompt_text=_required_string(
                values,
                "scheduled_prompt_text",
                defaults.scheduled_prompt_text,
                maximum_length=MAX_SCHEDULED_PROMPT_TEXT_LENGTH,
            ),
            scheduled_prompt_require_red_inactivity=_bool_value(
                values,
                "scheduled_prompt_require_red_inactivity",
                defaults.scheduled_prompt_require_red_inactivity,
            ),
            scheduled_prompt_thread_id=_optional_string(
                values,
                "scheduled_prompt_thread_id",
                defaults.scheduled_prompt_thread_id,
            ),
            scheduled_prompt_due_at=_optional_number(
                values,
                "scheduled_prompt_due_at",
                defaults.scheduled_prompt_due_at,
            ),
            scheduled_prompt_id=_optional_string(
                values,
                "scheduled_prompt_id",
                defaults.scheduled_prompt_id,
            ),
            scheduled_prompt_last_state=_choice_value(
                values,
                "scheduled_prompt_last_state",
                defaults.scheduled_prompt_last_state,
                choices=SCHEDULED_PROMPT_STATES,
            ),
            scheduled_prompt_last_attempt_at=_optional_number(
                values,
                "scheduled_prompt_last_attempt_at",
                defaults.scheduled_prompt_last_attempt_at,
            ),
        )
        _validate_scheduled_prompt(settings)
        return settings

    def _write_payload(self, payload: dict[str, Any]) -> None:
        parent_existed = self.path.parent.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed:
            _chmod(self.path.parent, 0o700)
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


def _profile_defaults(settings: ControlSettings) -> ControlSettings:
    return replace(
        settings,
        scheduled_prompt_enabled=False,
        scheduled_prompt_thread_id=None,
        scheduled_prompt_due_at=None,
        scheduled_prompt_id=None,
        scheduled_prompt_last_state="disabled",
        scheduled_prompt_last_attempt_at=None,
    )


def _clean_profile_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ControlError("O identificador do perfil precisa ser texto.")
    clean = value.strip()
    if not clean:
        raise ControlError("O identificador do perfil nao pode ficar vazio.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise ControlError("O identificador do perfil precisa ter uma linha.")
    if len(clean) > MAX_CONTROL_PROFILE_ID_LENGTH:
        raise ControlError(
            "O identificador do perfil excede o limite de "
            f"{MAX_CONTROL_PROFILE_ID_LENGTH} caracteres."
        )
    return clean


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


def _required_string(
    values: dict[str, Any],
    key: str,
    default: str,
    *,
    maximum_length: int,
) -> str:
    value = values.get(key, default)
    if not isinstance(value, str):
        raise ControlError(f"Controle {key!r} precisa ser texto.")
    clean = value.strip()
    if not clean:
        raise ControlError(f"Controle {key!r} nao pode ficar vazio.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise ControlError(f"Controle {key!r} precisa ter uma unica linha.")
    if len(clean) > maximum_length:
        raise ControlError(
            f"Controle {key!r} excede o limite de {maximum_length} caracteres."
        )
    return clean


def _int_value(
    values: dict[str, Any],
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = values.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ControlError(f"Controle {key!r} precisa ser inteiro.")
    if not minimum <= value <= maximum:
        raise ControlError(
            f"Controle {key!r} precisa estar entre {minimum} e {maximum}."
        )
    return value


def _optional_number(
    values: dict[str, Any],
    key: str,
    default: float | None,
) -> float | None:
    value = values.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControlError(f"Controle {key!r} precisa ser numero ou null.")
    number = float(value)
    if number < 0:
        raise ControlError(f"Controle {key!r} nao pode ser negativo.")
    return number


def _choice_value(
    values: dict[str, Any],
    key: str,
    default: str,
    *,
    choices: frozenset[str],
) -> str:
    value = values.get(key, default)
    if not isinstance(value, str) or value not in choices:
        raise ControlError(
            f"Controle {key!r} precisa ser um destes valores: "
            f"{', '.join(sorted(choices))}."
        )
    return value


def _validate_scheduled_prompt(settings: ControlSettings) -> None:
    if (
        isinstance(settings.scheduled_prompt_delay_minutes, bool)
        or not isinstance(settings.scheduled_prompt_delay_minutes, int)
        or not 1
        <= settings.scheduled_prompt_delay_minutes
        <= MAX_SCHEDULED_PROMPT_DELAY_MINUTES
    ):
        raise ControlError(
            "O atraso do prompt temporizado precisa estar entre 1 e "
            f"{MAX_SCHEDULED_PROMPT_DELAY_MINUTES} minutos."
        )
    text = settings.scheduled_prompt_text
    if not isinstance(text, str) or not text.strip():
        raise ControlError("O texto do prompt temporizado nao pode ficar vazio.")
    if any(character in text for character in ("\r", "\n", "\x00")):
        raise ControlError("O texto do prompt temporizado precisa ter uma linha.")
    if len(text.strip()) > MAX_SCHEDULED_PROMPT_TEXT_LENGTH:
        raise ControlError(
            "O texto do prompt temporizado excede o limite de "
            f"{MAX_SCHEDULED_PROMPT_TEXT_LENGTH} caracteres."
        )
    if settings.scheduled_prompt_last_state not in SCHEDULED_PROMPT_STATES:
        raise ControlError("O estado do prompt temporizado e invalido.")
    for label, value in (
        ("vencimento", settings.scheduled_prompt_due_at),
        ("ultima tentativa", settings.scheduled_prompt_last_attempt_at),
    ):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < 0
        ):
            raise ControlError(f"O campo {label} do prompt temporizado e invalido.")
    if not settings.scheduled_prompt_enabled:
        return
    if not settings.native_input_enabled:
        raise ControlError(
            "Prompt temporizado habilitado exige entrada nativa habilitada."
        )
    if not settings.scheduled_prompt_thread_id:
        raise ControlError("Prompt temporizado exige uma sessao Codex exata.")
    if settings.scheduled_prompt_due_at is None:
        raise ControlError("Prompt temporizado habilitado exige vencimento.")
    if not settings.scheduled_prompt_id:
        raise ControlError("Prompt temporizado habilitado exige identificador.")
    if settings.scheduled_prompt_last_state != "armed":
        raise ControlError(
            "Prompt temporizado habilitado precisa estar no estado 'armed'."
        )


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        # Windows ACLs are not represented by POSIX modes.
        pass
