from __future__ import annotations

import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

from .identity import normalize_scope

APP_DIR_NAME = "ai-presence-monitor"
PROJECT_ENV_NAME = ".ai-presence-monitor.env"


def user_config_dir(platform_name: str | None = None) -> Path:
    if (platform_name or sys.platform).lower() in {"win32", "windows"}:
        windows_config = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        base = Path(windows_config) if windows_config else Path.home() / "AppData" / "Roaming"
        return base / APP_DIR_NAME
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home).expanduser() if xdg_config_home else Path.home() / ".config"
    return base / APP_DIR_NAME


def user_state_dir(platform_name: str | None = None) -> Path:
    if (platform_name or sys.platform).lower() in {"win32", "windows"}:
        windows_state = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = (
            Path(windows_state)
            if windows_state
            else Path.home() / "AppData" / "Local"
        )
        return base / APP_DIR_NAME
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    base = (
        Path(xdg_state_home).expanduser()
        if xdg_state_home
        else Path.home() / ".local" / "state"
    )
    return base / APP_DIR_NAME


def resolve_env_path(env_file: str | Path | None = None, cwd: Path | None = None) -> Path:
    explicit = env_file or os.environ.get("PRESENCE_ENV_FILE")
    if explicit:
        return Path(explicit).expanduser().resolve()

    current_dir = (cwd or Path.cwd()).resolve()
    project_env = current_dir / PROJECT_ENV_NAME
    if project_env.exists():
        return project_env

    # Compatibilidade para executar diretamente do checkout do monitor.
    legacy_env = current_dir / ".env"
    if (
        legacy_env.exists()
        and (current_dir / "pyproject.toml").exists()
        and (
            (current_dir / "src" / "ai_presence_monitor").is_dir()
            or (current_dir / "ai_presence_monitor").is_dir()
        )
    ):
        return legacy_env.resolve()
    return (user_config_dir() / ".env").resolve()


def resolve_data_path(raw_path: str, env_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (env_path.parent / path).resolve()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_dotenv(path: Path, override: bool = False) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())

        if key and (override or key not in os.environ):
            os.environ[key] = value


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name) or default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} precisa ser um inteiro, recebido: {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} precisa ser um numero, recebido: {raw!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "sim", "s", "on"}


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class AppConfig:
    env_path: Path
    db_path: Path
    default_protocol: str
    computer_name: str
    monitor_interval_seconds: int
    work_window_enabled: bool
    work_window_start: str
    work_window_end: str
    work_window_timezone: str
    outside_work_window_behavior: str
    alert_repeat_enabled: bool
    alert_repeat_seconds: int
    alert_repeat_levels: tuple[str, ...]
    discord_point_webhook_url: str | None
    discord_alert_webhook_url: str | None
    discord_red_webhook_url: str | None
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    red_notification_mode: str
    red_alert_command: str | None
    phone_webhook_url: str | None
    codex_worker_id: str | None
    codex_ai_name: str
    codex_protocol: str | None
    codex_task: str | None
    codex_worker_scope: str
    codex_auto_start: bool
    codex_hook_fail_closed: bool
    remote_questions_enabled: bool = False
    discord_question_webhook_url: str | None = None
    discord_bot_token: str | None = None
    discord_question_channel_id: str | None = None
    discord_allowed_user_ids: tuple[str, ...] = ()
    question_poll_interval_seconds: int = 5
    question_timeout_seconds: int = 1800
    gui_answer_enabled: bool = False
    codex_gui_window_title: str | None = None
    codex_gui_click_x_ratio: float = 0.5
    codex_gui_click_y_ratio: float = 0.9
    gui_confirmation_timeout_seconds: int = 120
    continue_message: str = "continue"
    continue_delay_seconds: int = 60
    continue_sync_activity: bool = True
    red_alert_max_duration_seconds: int = 15
    control_path: Path | None = None
    task_automation_enabled: bool = False
    native_input_enabled: bool = True
    gui_fallback_enabled: bool = False
    remote_input_enabled: bool = False
    codex_thread_id: str | None = None
    codex_remote: str | None = None
    codex_remote_auth_token_env: str | None = None
    continue_transport: str = "auto"
    continue_destination: str = "local"
    experimental_windows_enabled: bool = False


def load_config(env_file: str | Path | None = None, override_env: bool = False) -> AppConfig:
    env_path = resolve_env_path(env_file)
    load_dotenv(env_path, override=override_env)

    return AppConfig(
        env_path=env_path,
        db_path=resolve_data_path(_env_str("PRESENCE_DB_PATH", "presence.db"), env_path),
        default_protocol=_env_str("PRESENCE_DEFAULT_PROTOCOL", "protocol1"),
        computer_name=_env_str("PRESENCE_COMPUTER_NAME", socket.gethostname()),
        monitor_interval_seconds=_env_int("PRESENCE_MONITOR_INTERVAL_SECONDS", 30),
        work_window_enabled=_env_bool("PRESENCE_WORK_WINDOW_ENABLED", False),
        work_window_start=_env_str("PRESENCE_WORK_WINDOW_START", "13:00"),
        work_window_end=_env_str("PRESENCE_WORK_WINDOW_END", "18:00"),
        work_window_timezone=_env_str("PRESENCE_WORK_WINDOW_TIMEZONE", "America/Sao_Paulo"),
        outside_work_window_behavior=_env_str(
            "PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR",
            "suppress_alerts",
        ).lower(),
        alert_repeat_enabled=_env_bool("PRESENCE_ALERT_REPEAT_ENABLED", False),
        alert_repeat_seconds=_env_int("PRESENCE_ALERT_REPEAT_SECONDS", 300),
        alert_repeat_levels=_env_csv(
            "PRESENCE_ALERT_REPEAT_LEVELS",
            ("yellow", "orange"),
        ),
        discord_point_webhook_url=os.environ.get("DISCORD_POINT_WEBHOOK_URL") or None,
        discord_alert_webhook_url=os.environ.get("DISCORD_ALERT_WEBHOOK_URL") or None,
        discord_red_webhook_url=os.environ.get("DISCORD_RED_WEBHOOK_URL") or None,
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID") or None,
        red_notification_mode=os.environ.get("RED_NOTIFICATION_MODE", "alarm").lower(),
        red_alert_command=os.environ.get("RED_ALERT_COMMAND") or None,
        red_alert_max_duration_seconds=_env_int(
            "RED_ALERT_MAX_DURATION_SECONDS",
            15,
        ),
        phone_webhook_url=os.environ.get("PHONE_WEBHOOK_URL") or None,
        codex_worker_id=os.environ.get("PRESENCE_CODEX_WORKER_ID") or None,
        codex_ai_name=_env_str("PRESENCE_CODEX_AI_NAME", "codex"),
        codex_protocol=os.environ.get("PRESENCE_CODEX_PROTOCOL") or None,
        codex_task=os.environ.get("PRESENCE_CODEX_TASK") or None,
        codex_worker_scope=normalize_scope(
            _env_str("PRESENCE_CODEX_WORKER_SCOPE", "global")
        ),
        codex_auto_start=_env_bool("PRESENCE_CODEX_AUTO_START", False),
        codex_hook_fail_closed=_env_bool("PRESENCE_CODEX_HOOK_FAIL_CLOSED", False),
        remote_questions_enabled=_env_bool(
            "PRESENCE_REMOTE_QUESTIONS_ENABLED",
            False,
        ),
        discord_question_webhook_url=(
            os.environ.get("DISCORD_QUESTION_WEBHOOK_URL") or None
        ),
        discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN") or None,
        discord_question_channel_id=(
            os.environ.get("DISCORD_QUESTION_CHANNEL_ID") or None
        ),
        discord_allowed_user_ids=_env_csv("DISCORD_ALLOWED_USER_IDS", ()),
        question_poll_interval_seconds=_env_int(
            "PRESENCE_QUESTION_POLL_INTERVAL_SECONDS",
            5,
        ),
        question_timeout_seconds=_env_int(
            "PRESENCE_QUESTION_TIMEOUT_SECONDS",
            1800,
        ),
        gui_answer_enabled=_env_bool("PRESENCE_GUI_ANSWER_ENABLED", False),
        codex_gui_window_title=(
            os.environ.get("PRESENCE_CODEX_GUI_WINDOW_TITLE") or None
        ),
        codex_gui_click_x_ratio=_env_float(
            "PRESENCE_CODEX_GUI_CLICK_X_RATIO",
            0.5,
        ),
        codex_gui_click_y_ratio=_env_float(
            "PRESENCE_CODEX_GUI_CLICK_Y_RATIO",
            0.9,
        ),
        gui_confirmation_timeout_seconds=_env_int(
            "PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS",
            120,
        ),
        continue_message=_env_str("PRESENCE_CONTINUE_MESSAGE", "continue"),
        continue_delay_seconds=_env_int("PRESENCE_CONTINUE_DELAY_SECONDS", 60),
        continue_sync_activity=_env_bool(
            "PRESENCE_CONTINUE_SYNC_ACTIVITY",
            True,
        ),
        control_path=(
            resolve_data_path(os.environ["PRESENCE_CONTROL_PATH"], env_path)
            if os.environ.get("PRESENCE_CONTROL_PATH")
            else user_state_dir() / "control.json"
        ),
        task_automation_enabled=_env_bool(
            "PRESENCE_TASK_AUTOMATION_ENABLED",
            False,
        ),
        native_input_enabled=_env_bool(
            "PRESENCE_NATIVE_INPUT_ENABLED",
            True,
        ),
        gui_fallback_enabled=_env_bool(
            "PRESENCE_GUI_FALLBACK_ENABLED",
            False,
        ),
        remote_input_enabled=_env_bool(
            "PRESENCE_REMOTE_INPUT_ENABLED",
            False,
        ),
        codex_thread_id=os.environ.get("PRESENCE_CODEX_THREAD_ID") or None,
        codex_remote=os.environ.get("PRESENCE_CODEX_REMOTE") or None,
        codex_remote_auth_token_env=(
            os.environ.get("PRESENCE_CODEX_REMOTE_AUTH_TOKEN_ENV") or None
        ),
        continue_transport=_env_str(
            "PRESENCE_CONTINUE_TRANSPORT",
            "auto",
        ).lower(),
        continue_destination=_env_str(
            "PRESENCE_CONTINUE_DESTINATION",
            "local",
        ).lower(),
        experimental_windows_enabled=_env_bool(
            "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED",
            False,
        ),
    )
