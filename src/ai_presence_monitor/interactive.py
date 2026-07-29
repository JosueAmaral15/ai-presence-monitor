from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from .cli import (
    _ask_user,
    _continue_task,
    _init_db,
    _observe_replies_once,
    _record_event,
    _run_monitor,
    _run_reply_observer,
    _show_protocols,
    _show_questions,
    _show_status,
)
from .codex_hook_installer import (
    default_user_hooks_path,
    install_codex_hook,
    print_result as print_hook_install_result,
    uninstall_codex_hook,
)
from .config import AppConfig, load_config, resolve_env_path
from .protocols import PROTOCOLS


DEFAULT_ENV_FILE = resolve_env_path()

ENV_FIELDS = (
    "PRESENCE_DB_PATH",
    "PRESENCE_DEFAULT_PROTOCOL",
    "PRESENCE_COMPUTER_NAME",
    "PRESENCE_MONITOR_INTERVAL_SECONDS",
    "PRESENCE_WORK_WINDOW_ENABLED",
    "PRESENCE_WORK_WINDOW_START",
    "PRESENCE_WORK_WINDOW_END",
    "PRESENCE_WORK_WINDOW_TIMEZONE",
    "PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR",
    "PRESENCE_ALERT_REPEAT_ENABLED",
    "PRESENCE_ALERT_REPEAT_SECONDS",
    "PRESENCE_ALERT_REPEAT_LEVELS",
    "DISCORD_POINT_WEBHOOK_URL",
    "DISCORD_ALERT_WEBHOOK_URL",
    "DISCORD_RED_WEBHOOK_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "RED_NOTIFICATION_MODE",
    "RED_ALERT_COMMAND",
    "PHONE_WEBHOOK_URL",
    "PRESENCE_CODEX_WORKER_ID",
    "PRESENCE_CODEX_AI_NAME",
    "PRESENCE_CODEX_PROTOCOL",
    "PRESENCE_CODEX_TASK",
    "PRESENCE_CODEX_WORKER_SCOPE",
    "PRESENCE_CODEX_AUTO_START",
    "PRESENCE_CODEX_HOOK_FAIL_CLOSED",
    "PRESENCE_REMOTE_QUESTIONS_ENABLED",
    "DISCORD_QUESTION_WEBHOOK_URL",
    "DISCORD_BOT_TOKEN",
    "DISCORD_QUESTION_CHANNEL_ID",
    "DISCORD_ALLOWED_USER_IDS",
    "PRESENCE_QUESTION_POLL_INTERVAL_SECONDS",
    "PRESENCE_QUESTION_TIMEOUT_SECONDS",
    "PRESENCE_GUI_ANSWER_ENABLED",
    "PRESENCE_CODEX_GUI_WINDOW_TITLE",
    "PRESENCE_CODEX_GUI_CLICK_X_RATIO",
    "PRESENCE_CODEX_GUI_CLICK_Y_RATIO",
    "PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS",
    "PRESENCE_CONTINUE_MESSAGE",
    "PRESENCE_CONTINUE_DELAY_SECONDS",
    "PRESENCE_CONTINUE_SYNC_ACTIVITY",
)


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _quote_env(value: str) -> str:
    if value == "":
        return ""
    if any(char.isspace() for char in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Gerado pelo AI Presence Monitor",
        "PRESENCE_DB_PATH=" + _quote_env(values["PRESENCE_DB_PATH"]),
        "PRESENCE_DEFAULT_PROTOCOL=" + _quote_env(values["PRESENCE_DEFAULT_PROTOCOL"]),
        "PRESENCE_COMPUTER_NAME=" + _quote_env(values["PRESENCE_COMPUTER_NAME"]),
        "PRESENCE_MONITOR_INTERVAL_SECONDS="
        + _quote_env(values["PRESENCE_MONITOR_INTERVAL_SECONDS"]),
        "",
        "PRESENCE_WORK_WINDOW_ENABLED="
        + _quote_env(values["PRESENCE_WORK_WINDOW_ENABLED"]),
        "PRESENCE_WORK_WINDOW_START="
        + _quote_env(values["PRESENCE_WORK_WINDOW_START"]),
        "PRESENCE_WORK_WINDOW_END=" + _quote_env(values["PRESENCE_WORK_WINDOW_END"]),
        "PRESENCE_WORK_WINDOW_TIMEZONE="
        + _quote_env(values["PRESENCE_WORK_WINDOW_TIMEZONE"]),
        "PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR="
        + _quote_env(values["PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR"]),
        "PRESENCE_ALERT_REPEAT_ENABLED="
        + _quote_env(values["PRESENCE_ALERT_REPEAT_ENABLED"]),
        "PRESENCE_ALERT_REPEAT_SECONDS="
        + _quote_env(values["PRESENCE_ALERT_REPEAT_SECONDS"]),
        "PRESENCE_ALERT_REPEAT_LEVELS="
        + _quote_env(values["PRESENCE_ALERT_REPEAT_LEVELS"]),
        "",
        "DISCORD_POINT_WEBHOOK_URL=" + _quote_env(values["DISCORD_POINT_WEBHOOK_URL"]),
        "DISCORD_ALERT_WEBHOOK_URL=" + _quote_env(values["DISCORD_ALERT_WEBHOOK_URL"]),
        "DISCORD_RED_WEBHOOK_URL=" + _quote_env(values["DISCORD_RED_WEBHOOK_URL"]),
        "",
        "TELEGRAM_BOT_TOKEN=" + _quote_env(values["TELEGRAM_BOT_TOKEN"]),
        "TELEGRAM_CHAT_ID=" + _quote_env(values["TELEGRAM_CHAT_ID"]),
        "",
        "RED_NOTIFICATION_MODE=" + _quote_env(values["RED_NOTIFICATION_MODE"]),
        "RED_ALERT_COMMAND=" + _quote_env(values["RED_ALERT_COMMAND"]),
        "PHONE_WEBHOOK_URL=" + _quote_env(values["PHONE_WEBHOOK_URL"]),
        "",
        "PRESENCE_CODEX_WORKER_ID=" + _quote_env(values["PRESENCE_CODEX_WORKER_ID"]),
        "PRESENCE_CODEX_AI_NAME=" + _quote_env(values["PRESENCE_CODEX_AI_NAME"]),
        "PRESENCE_CODEX_PROTOCOL=" + _quote_env(values["PRESENCE_CODEX_PROTOCOL"]),
        "PRESENCE_CODEX_TASK=" + _quote_env(values["PRESENCE_CODEX_TASK"]),
        "PRESENCE_CODEX_WORKER_SCOPE="
        + _quote_env(values["PRESENCE_CODEX_WORKER_SCOPE"]),
        "PRESENCE_CODEX_AUTO_START=" + _quote_env(values["PRESENCE_CODEX_AUTO_START"]),
        "PRESENCE_CODEX_HOOK_FAIL_CLOSED="
        + _quote_env(values["PRESENCE_CODEX_HOOK_FAIL_CLOSED"]),
        "",
        "PRESENCE_REMOTE_QUESTIONS_ENABLED="
        + _quote_env(values["PRESENCE_REMOTE_QUESTIONS_ENABLED"]),
        "DISCORD_QUESTION_WEBHOOK_URL="
        + _quote_env(values["DISCORD_QUESTION_WEBHOOK_URL"]),
        "DISCORD_BOT_TOKEN=" + _quote_env(values["DISCORD_BOT_TOKEN"]),
        "DISCORD_QUESTION_CHANNEL_ID="
        + _quote_env(values["DISCORD_QUESTION_CHANNEL_ID"]),
        "DISCORD_ALLOWED_USER_IDS="
        + _quote_env(values["DISCORD_ALLOWED_USER_IDS"]),
        "PRESENCE_QUESTION_POLL_INTERVAL_SECONDS="
        + _quote_env(values["PRESENCE_QUESTION_POLL_INTERVAL_SECONDS"]),
        "PRESENCE_QUESTION_TIMEOUT_SECONDS="
        + _quote_env(values["PRESENCE_QUESTION_TIMEOUT_SECONDS"]),
        "",
        "PRESENCE_GUI_ANSWER_ENABLED="
        + _quote_env(values["PRESENCE_GUI_ANSWER_ENABLED"]),
        "PRESENCE_CODEX_GUI_WINDOW_TITLE="
        + _quote_env(values["PRESENCE_CODEX_GUI_WINDOW_TITLE"]),
        "PRESENCE_CODEX_GUI_CLICK_X_RATIO="
        + _quote_env(values["PRESENCE_CODEX_GUI_CLICK_X_RATIO"]),
        "PRESENCE_CODEX_GUI_CLICK_Y_RATIO="
        + _quote_env(values["PRESENCE_CODEX_GUI_CLICK_Y_RATIO"]),
        "PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS="
        + _quote_env(values["PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS"]),
        "",
        "PRESENCE_CONTINUE_MESSAGE="
        + _quote_env(values["PRESENCE_CONTINUE_MESSAGE"]),
        "PRESENCE_CONTINUE_DELAY_SECONDS="
        + _quote_env(values["PRESENCE_CONTINUE_DELAY_SECONDS"]),
        "PRESENCE_CONTINUE_SYNC_ACTIVITY="
        + _quote_env(values["PRESENCE_CONTINUE_SYNC_ACTIVITY"]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(0o600)


def _prompt_text(
    label: str,
    default: str = "",
    *,
    required: bool = False,
    secret: bool = False,
    allow_clear: bool = True,
) -> str:
    while True:
        suffix = ""
        if default:
            suffix = " [enter para manter]" if secret else f" [{default}]"
        if allow_clear and default:
            suffix += " (digite - para limpar)"

        prompt = f"{label}{suffix}: "
        answer = getpass.getpass(prompt) if secret else input(prompt)
        answer = answer.strip()

        if allow_clear and answer == "-":
            return ""
        if answer == "" and default:
            return default
        if answer or not required:
            return answer
        print("Valor obrigatorio.")


def _prompt_int(label: str, default: int) -> int:
    while True:
        raw = _prompt_text(label, str(default), required=True, allow_clear=False)
        try:
            value = int(raw)
        except ValueError:
            print("Digite um numero inteiro.")
            continue
        if value <= 0:
            print("Digite um numero maior que zero.")
            continue
        return value


def _prompt_ratio(label: str, default: float) -> float:
    while True:
        raw = _prompt_text(label, str(default), required=True, allow_clear=False)
        try:
            value = float(raw)
        except ValueError:
            print("Digite um numero entre 0 e 1.")
            continue
        if 0 <= value <= 1:
            return value
        print("Digite um numero entre 0 e 1.")


def _coerce_int(value: str | None, default: int) -> int:
    try:
        return int(value or default)
    except ValueError:
        return default


def _coerce_float(value: str | None, default: float) -> float:
    try:
        return float(value or default)
    except ValueError:
        return default


def _prompt_choice(label: str, choices: list[str], default: str) -> str:
    choices_text = "/".join(choices)
    while True:
        value = _prompt_text(
            f"{label} ({choices_text})",
            default,
            required=True,
            allow_clear=False,
        )
        if value in choices:
            return value
        print(f"Opcao invalida. Use uma destas: {choices_text}.")


def _prompt_yes_no(label: str, default: bool = False) -> bool:
    default_text = "S/n" if default else "s/N"
    while True:
        value = _prompt_text(
            f"{label} ({default_text})",
            "s" if default else "n",
            allow_clear=False,
        )
        value = value.lower()
        if value in {"s", "sim", "y", "yes"}:
            return True
        if value in {"n", "nao", "não", "no"}:
            return False
        print("Responda com s ou n.")


def configure_env(env_file: Path) -> None:
    current = {key: "" for key in ENV_FIELDS}
    current.update(_read_env(env_file))

    print("\nConfiguracao do AI Presence Monitor")
    print(f"Arquivo: {env_file}")
    print("Para limpar um valor existente, digite - quando indicado.\n")

    values = dict(current)
    values["PRESENCE_DB_PATH"] = _prompt_text(
        "Caminho do banco SQLite",
        current.get("PRESENCE_DB_PATH") or "./presence.db",
        required=True,
    )
    values["PRESENCE_DEFAULT_PROTOCOL"] = _prompt_choice(
        "Protocolo padrao",
        sorted(PROTOCOLS),
        current.get("PRESENCE_DEFAULT_PROTOCOL") or "protocol1",
    )
    values["PRESENCE_COMPUTER_NAME"] = _prompt_text(
        "Nome do computador nos alertas",
        current.get("PRESENCE_COMPUTER_NAME", ""),
    )
    values["PRESENCE_MONITOR_INTERVAL_SECONDS"] = str(
        _prompt_int(
            "Intervalo do monitor em segundos",
            _coerce_int(current.get("PRESENCE_MONITOR_INTERVAL_SECONDS"), 30),
        )
    )

    print("\nExpediente e repeticao")
    values["PRESENCE_WORK_WINDOW_ENABLED"] = (
        "true"
        if _prompt_yes_no(
            "Limitar alertas ao expediente",
            current.get("PRESENCE_WORK_WINDOW_ENABLED", "").lower() == "true",
        )
        else "false"
    )
    values["PRESENCE_WORK_WINDOW_START"] = _prompt_text(
        "Inicio do expediente (HH:MM)",
        current.get("PRESENCE_WORK_WINDOW_START") or "13:00",
        required=True,
        allow_clear=False,
    )
    values["PRESENCE_WORK_WINDOW_END"] = _prompt_text(
        "Fim do expediente (HH:MM)",
        current.get("PRESENCE_WORK_WINDOW_END") or "18:00",
        required=True,
        allow_clear=False,
    )
    values["PRESENCE_WORK_WINDOW_TIMEZONE"] = _prompt_text(
        "Timezone do expediente",
        current.get("PRESENCE_WORK_WINDOW_TIMEZONE") or "America/Sao_Paulo",
        required=True,
        allow_clear=False,
    )
    values["PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR"] = _prompt_choice(
        "Comportamento fora do expediente",
        ["suppress_alerts", "allow_alerts"],
        current.get("PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR") or "suppress_alerts",
    )
    values["PRESENCE_ALERT_REPEAT_ENABLED"] = (
        "true"
        if _prompt_yes_no(
            "Repetir alertas enquanto houver atraso",
            current.get("PRESENCE_ALERT_REPEAT_ENABLED", "").lower() == "true",
        )
        else "false"
    )
    values["PRESENCE_ALERT_REPEAT_SECONDS"] = str(
        _prompt_int(
            "Intervalo de repeticao em segundos",
            _coerce_int(current.get("PRESENCE_ALERT_REPEAT_SECONDS"), 300),
        )
    )
    values["PRESENCE_ALERT_REPEAT_LEVELS"] = _prompt_text(
        "Niveis repetidos separados por virgula",
        current.get("PRESENCE_ALERT_REPEAT_LEVELS") or "yellow,orange,red",
        required=True,
        allow_clear=False,
    )

    print("\nDiscord")
    values["DISCORD_POINT_WEBHOOK_URL"] = _prompt_text(
        "Webhook do canal de ponto",
        current.get("DISCORD_POINT_WEBHOOK_URL", ""),
        secret=True,
    )
    values["DISCORD_ALERT_WEBHOOK_URL"] = _prompt_text(
        "Webhook do canal de alertas",
        current.get("DISCORD_ALERT_WEBHOOK_URL", ""),
        secret=True,
    )
    values["DISCORD_RED_WEBHOOK_URL"] = _prompt_text(
        "Webhook dedicado para alerta vermelho",
        current.get("DISCORD_RED_WEBHOOK_URL", ""),
        secret=True,
    )

    print("\nTelegram opcional")
    if _prompt_yes_no(
        "Configurar Telegram",
        bool(current.get("TELEGRAM_BOT_TOKEN") or current.get("TELEGRAM_CHAT_ID")),
    ):
        values["TELEGRAM_BOT_TOKEN"] = _prompt_text(
            "Token do bot Telegram",
            current.get("TELEGRAM_BOT_TOKEN", ""),
            secret=True,
        )
        values["TELEGRAM_CHAT_ID"] = _prompt_text(
            "Chat ID do Telegram",
            current.get("TELEGRAM_CHAT_ID", ""),
        )
    else:
        values["TELEGRAM_BOT_TOKEN"] = ""
        values["TELEGRAM_CHAT_ID"] = ""

    print("\nAlerta vermelho")
    values["RED_NOTIFICATION_MODE"] = _prompt_choice(
        "Modo do alerta vermelho",
        ["alarm", "phone", "none"],
        current.get("RED_NOTIFICATION_MODE") or "alarm",
    )
    if values["RED_NOTIFICATION_MODE"] == "alarm":
        values["RED_ALERT_COMMAND"] = _prompt_text(
            "Comando local de alarme",
            current.get("RED_ALERT_COMMAND", ""),
        )
        values["PHONE_WEBHOOK_URL"] = current.get("PHONE_WEBHOOK_URL", "")
    elif values["RED_NOTIFICATION_MODE"] == "phone":
        values["PHONE_WEBHOOK_URL"] = _prompt_text(
            "Webhook externo de telefonia",
            current.get("PHONE_WEBHOOK_URL", ""),
            secret=True,
        )
        values["RED_ALERT_COMMAND"] = current.get("RED_ALERT_COMMAND", "")
    else:
        values["RED_ALERT_COMMAND"] = ""
        values["PHONE_WEBHOOK_URL"] = ""

    print("\nObserver do Codex opcional")
    if _prompt_yes_no(
        "Configurar observer de hooks do Codex",
        bool(
            current.get("PRESENCE_CODEX_WORKER_ID")
            or current.get("PRESENCE_CODEX_TASK")
            or current.get("PRESENCE_CODEX_AUTO_START", "").lower() == "true"
            or current.get("PRESENCE_CODEX_HOOK_FAIL_CLOSED", "").lower() == "true"
        ),
    ):
        values["PRESENCE_CODEX_AI_NAME"] = _prompt_text(
            "Nome da IA Codex",
            current.get("PRESENCE_CODEX_AI_NAME") or "codex",
            allow_clear=False,
        )
        values["PRESENCE_CODEX_WORKER_ID"] = _prompt_text(
            "Worker ID fixo para Codex",
            current.get("PRESENCE_CODEX_WORKER_ID", ""),
        )
        values["PRESENCE_CODEX_PROTOCOL"] = _prompt_choice(
            "Protocolo do observer Codex",
            sorted(PROTOCOLS),
            current.get("PRESENCE_CODEX_PROTOCOL") or values["PRESENCE_DEFAULT_PROTOCOL"],
        )
        values["PRESENCE_CODEX_TASK"] = _prompt_text(
            "Tarefa padrao do Codex",
            current.get("PRESENCE_CODEX_TASK", ""),
        )
        values["PRESENCE_CODEX_WORKER_SCOPE"] = _prompt_choice(
            "Isolamento do worker Codex",
            ["global", "project", "session", "project-session"],
            current.get("PRESENCE_CODEX_WORKER_SCOPE") or "project",
        )
        values["PRESENCE_CODEX_AUTO_START"] = (
            "true"
            if _prompt_yes_no(
                "Hook pode criar/reativar worker automaticamente",
                (current.get("PRESENCE_CODEX_AUTO_START", "").lower() == "true"),
            )
            else "false"
        )
        values["PRESENCE_CODEX_HOOK_FAIL_CLOSED"] = (
            "true"
            if _prompt_yes_no(
                "Falha do hook deve bloquear/errar o Codex",
                (current.get("PRESENCE_CODEX_HOOK_FAIL_CLOSED", "").lower() == "true"),
            )
            else "false"
        )
    else:
        values["PRESENCE_CODEX_WORKER_ID"] = ""
        values["PRESENCE_CODEX_AI_NAME"] = "codex"
        values["PRESENCE_CODEX_PROTOCOL"] = ""
        values["PRESENCE_CODEX_TASK"] = ""
        values["PRESENCE_CODEX_WORKER_SCOPE"] = "project"
        values["PRESENCE_CODEX_AUTO_START"] = "false"
        values["PRESENCE_CODEX_HOOK_FAIL_CLOSED"] = "false"

    print("\nPerguntas e respostas remotas pelo Discord")
    remote_enabled = _prompt_yes_no(
        "Ativar perguntas e respostas remotas",
        current.get("PRESENCE_REMOTE_QUESTIONS_ENABLED", "").lower() == "true",
    )
    values["PRESENCE_REMOTE_QUESTIONS_ENABLED"] = (
        "true" if remote_enabled else "false"
    )
    if remote_enabled:
        values["DISCORD_QUESTION_WEBHOOK_URL"] = _prompt_text(
            "Webhook do canal de perguntas",
            current.get("DISCORD_QUESTION_WEBHOOK_URL", ""),
            required=True,
            secret=True,
        )
        values["DISCORD_BOT_TOKEN"] = _prompt_text(
            "Token do bot Discord",
            current.get("DISCORD_BOT_TOKEN", ""),
            required=True,
            secret=True,
        )
        values["DISCORD_QUESTION_CHANNEL_ID"] = _prompt_text(
            "ID do canal de perguntas",
            current.get("DISCORD_QUESTION_CHANNEL_ID", ""),
            required=True,
        )
        values["DISCORD_ALLOWED_USER_IDS"] = _prompt_text(
            "IDs de usuarios autorizados, separados por virgula",
            current.get("DISCORD_ALLOWED_USER_IDS", ""),
            required=True,
        )
        values["PRESENCE_QUESTION_POLL_INTERVAL_SECONDS"] = str(
            _prompt_int(
                "Intervalo do observer de respostas em segundos",
                _coerce_int(
                    current.get("PRESENCE_QUESTION_POLL_INTERVAL_SECONDS"),
                    5,
                ),
            )
        )
        values["PRESENCE_QUESTION_TIMEOUT_SECONDS"] = str(
            _prompt_int(
                "Prazo padrao de uma pergunta em segundos",
                _coerce_int(current.get("PRESENCE_QUESTION_TIMEOUT_SECONDS"), 1800),
            )
        )
    else:
        values["DISCORD_QUESTION_WEBHOOK_URL"] = ""
        values["DISCORD_BOT_TOKEN"] = ""
        values["DISCORD_QUESTION_CHANNEL_ID"] = ""
        values["DISCORD_ALLOWED_USER_IDS"] = ""
        values["PRESENCE_QUESTION_POLL_INTERVAL_SECONDS"] = "5"
        values["PRESENCE_QUESTION_TIMEOUT_SECONDS"] = "1800"

    print("\nEntrega opcional na interface do Codex")
    gui_enabled = remote_enabled and _prompt_yes_no(
        "Ativar controle de mouse e teclado para entregar respostas",
        current.get("PRESENCE_GUI_ANSWER_ENABLED", "").lower() == "true",
    )
    values["PRESENCE_GUI_ANSWER_ENABLED"] = "true" if gui_enabled else "false"
    if gui_enabled:
        values["PRESENCE_CODEX_GUI_CLICK_X_RATIO"] = str(
            _prompt_ratio(
                "Posicao horizontal relativa do prompt",
                _coerce_float(
                    current.get("PRESENCE_CODEX_GUI_CLICK_X_RATIO"),
                    0.5,
                ),
            )
        )
        values["PRESENCE_CODEX_GUI_CLICK_Y_RATIO"] = str(
            _prompt_ratio(
                "Posicao vertical relativa do prompt",
                _coerce_float(
                    current.get("PRESENCE_CODEX_GUI_CLICK_Y_RATIO"),
                    0.9,
                ),
            )
        )
        values["PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS"] = str(
            _prompt_int(
                "Prazo para o hook confirmar a entrega em segundos",
                _coerce_int(
                    current.get("PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS"),
                    120,
                ),
            )
        )
    else:
        values["PRESENCE_CODEX_GUI_CLICK_X_RATIO"] = (
            current.get("PRESENCE_CODEX_GUI_CLICK_X_RATIO") or "0.5"
        )
        values["PRESENCE_CODEX_GUI_CLICK_Y_RATIO"] = (
            current.get("PRESENCE_CODEX_GUI_CLICK_Y_RATIO") or "0.9"
        )
        values["PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS"] = (
            current.get("PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS") or "120"
        )

    print("\nAutomacao local de continuidade")
    values["PRESENCE_CONTINUE_MESSAGE"] = _prompt_text(
        "Mensagem padrao de continuidade",
        current.get("PRESENCE_CONTINUE_MESSAGE") or "continue",
        required=True,
        allow_clear=False,
    )
    values["PRESENCE_CONTINUE_DELAY_SECONDS"] = str(
        _prompt_int(
            "Atraso padrao de continuidade em segundos",
            _coerce_int(current.get("PRESENCE_CONTINUE_DELAY_SECONDS"), 60),
        )
    )
    values["PRESENCE_CONTINUE_SYNC_ACTIVITY"] = (
        "true"
        if _prompt_yes_no(
            "Sincronizar continue bem-sucedido com worker ativo",
            current.get("PRESENCE_CONTINUE_SYNC_ACTIVITY", "true").lower()
            == "true",
        )
        else "false"
    )
    values["PRESENCE_CODEX_GUI_WINDOW_TITLE"] = _prompt_text(
        "Padrao do titulo da janela do Codex",
        current.get("PRESENCE_CODEX_GUI_WINDOW_TITLE", ""),
        required=gui_enabled,
    )

    _write_env(env_file, values)
    print(f"\nConfiguracao salva em {env_file}")


def _load_current_config(env_file: Path) -> AppConfig:
    return load_config(str(env_file), override_env=True)


def _prompt_event_args(
    config: AppConfig,
    event_type: str,
    dry_run: bool,
) -> argparse.Namespace:
    protocol = _prompt_choice(
        "Protocolo",
        sorted(PROTOCOLS),
        config.default_protocol,
    )
    ai_name = _prompt_text("Nome da IA/agente", "codex", allow_clear=False)
    computer = _prompt_text("Nome do computador", config.computer_name, allow_clear=False)
    worker = _prompt_text("ID do worker", f"{computer}:{ai_name}", allow_clear=False)
    task = _prompt_text("Tarefa/algoritmo", "")
    message = _prompt_text("Mensagem", "")

    notify = False
    if event_type == "touch":
        notify = _prompt_yes_no("Postar este touch no canal de ponto", False)

    return argparse.Namespace(
        worker=worker,
        computer=computer,
        ai=ai_name,
        protocol=protocol,
        task=task or None,
        message=message or None,
        notify=notify,
        dry_run=dry_run,
    )


def _run_event(env_file: Path, event_type: str, dry_run: bool) -> None:
    config = _load_current_config(env_file)
    args = _prompt_event_args(config, event_type, dry_run)
    _record_event(args, config, event_type)


def _run_monitor_once(env_file: Path, dry_run: bool) -> None:
    config = _load_current_config(env_file)
    args = argparse.Namespace(once=True, interval=None, dry_run=dry_run)
    _run_monitor(args, config)


def _run_monitor_loop(env_file: Path, dry_run: bool) -> None:
    config = _load_current_config(env_file)
    interval = _prompt_int("Intervalo do loop em segundos", config.monitor_interval_seconds)
    args = argparse.Namespace(once=False, interval=interval, dry_run=dry_run)
    print("Monitor rodando. Pressione Ctrl+C para voltar ao menu.")
    try:
        _run_monitor(args, config)
    except KeyboardInterrupt:
        print("\nMonitor interrompido.")


def _ask_user_interactive(env_file: Path, dry_run: bool) -> None:
    config = _load_current_config(env_file)
    ai_name = _prompt_text("Nome da IA/agente", "codex", allow_clear=False)
    computer = _prompt_text("Nome do computador", config.computer_name, allow_clear=False)
    worker = _prompt_text(
        "ID exato do worker",
        config.codex_worker_id or f"{computer}:{ai_name}",
        allow_clear=False,
    )
    question = _prompt_text("Pergunta ao usuario", required=True, allow_clear=False)
    timeout = _prompt_int(
        "Prazo da pergunta em segundos",
        config.question_timeout_seconds,
    )
    args = argparse.Namespace(
        worker=worker,
        computer=computer,
        ai=ai_name,
        protocol=config.default_protocol,
        scope=None,
        project=None,
        session=None,
        task=None,
        message=None,
        question=question,
        timeout=timeout,
        window_id=None,
        window_title=None,
        dry_run=dry_run,
    )
    _ask_user(args, config)


def _run_reply_observer_loop(env_file: Path, dry_run: bool) -> None:
    config = _load_current_config(env_file)
    interval = _prompt_int(
        "Intervalo do observer em segundos",
        config.question_poll_interval_seconds,
    )
    args = argparse.Namespace(once=False, interval=interval, dry_run=dry_run)
    print("Observer de respostas rodando. Pressione Ctrl+C para voltar ao menu.")
    try:
        _run_reply_observer(args, config)
    except KeyboardInterrupt:
        print("\nObserver de respostas interrompido.")


def _continue_task_interactive(env_file: Path, dry_run: bool) -> None:
    config = _load_current_config(env_file)
    ai_name = _prompt_text("Nome da IA/agente", "codex", allow_clear=False)
    computer = _prompt_text(
        "Nome do computador",
        config.computer_name,
        allow_clear=False,
    )
    worker = _prompt_text(
        "ID exato do worker a sincronizar",
        config.codex_worker_id or f"{computer}:{ai_name}",
        allow_clear=False,
    )
    message = _prompt_text(
        "Mensagem de continuidade",
        config.continue_message,
        required=True,
        allow_clear=False,
    )
    delay = _prompt_int(
        "Atraso antes do envio em segundos",
        config.continue_delay_seconds,
    )
    window_title = _prompt_text(
        "Padrao do titulo da janela do Codex",
        config.codex_gui_window_title or "",
        required=True,
        allow_clear=False,
    )
    window_id = _prompt_text("ID X11 exato, opcional", "")
    sync_activity = _prompt_yes_no(
        "Sincronizar o envio com a atividade do worker",
        config.continue_sync_activity,
    )
    args = argparse.Namespace(
        worker=worker,
        computer=computer,
        ai=ai_name,
        protocol=config.default_protocol,
        scope=None,
        project=None,
        session=None,
        message=message,
        delay=delay,
        window_id=window_id or None,
        window_title=window_title,
        sync_activity=sync_activity,
        dry_run=dry_run,
    )
    _continue_task(args, config)


def _install_codex_hook_interactive(env_file: Path, dry_run: bool) -> None:
    target = Path(
        _prompt_text(
            "Caminho do hooks.json do Codex",
            str(default_user_hooks_path()),
            required=True,
            allow_clear=False,
        )
    ).expanduser()
    result = install_codex_hook(
        target_path=target,
        env_file=env_file,
        dry_run=dry_run,
    )
    print_hook_install_result(result, dry_run=dry_run)
    print("Depois da instalacao, revise e confie no hook dentro do Codex com /hooks.")


def _uninstall_codex_hook_interactive(dry_run: bool) -> None:
    target = Path(
        _prompt_text(
            "Caminho do hooks.json do Codex",
            str(default_user_hooks_path()),
            required=True,
            allow_clear=False,
        )
    ).expanduser()
    result = uninstall_codex_hook(target_path=target, dry_run=dry_run)
    print_hook_install_result(result, dry_run=dry_run)


def _menu() -> None:
    print("\nAI Presence Monitor")
    print("1. Configurar .env")
    print("2. Inicializar banco")
    print("3. Registrar inicio de tarefa")
    print("4. Registrar ponto/heartbeat")
    print("5. Registrar atividade silenciosa/touch")
    print("6. Registrar fim de tarefa")
    print("7. Ver status")
    print("8. Rodar monitor uma vez")
    print("9. Rodar monitor continuamente")
    print("10. Listar protocolos")
    print("11. Alternar modo teste")
    print("12. Instalar hook do Codex")
    print("13. Remover hook do Codex")
    print("14. Perguntar ao usuario pelo Discord")
    print("15. Observar respostas uma vez")
    print("16. Observar respostas continuamente")
    print("17. Listar perguntas e respostas")
    print("18. Agendar e enviar continue ao Codex")
    print("0. Sair")


def run_interactive(env_file: Path, dry_run: bool = False) -> None:
    env_file = env_file.expanduser()
    if not env_file.exists():
        print(f"Arquivo de configuracao nao encontrado: {env_file}")
        if _prompt_yes_no("Deseja configurar agora", True):
            configure_env(env_file)

    while True:
        print(f"\nArquivo .env: {env_file}")
        print(f"Modo teste sem envio: {'ligado' if dry_run else 'desligado'}")
        _menu()
        option = _prompt_text("Escolha uma opcao", required=True, allow_clear=False)

        try:
            if option == "1":
                configure_env(env_file)
            elif option == "2":
                _init_db(_load_current_config(env_file))
            elif option == "3":
                _run_event(env_file, "start", dry_run)
            elif option == "4":
                _run_event(env_file, "heartbeat", dry_run)
            elif option == "5":
                _run_event(env_file, "touch", dry_run)
            elif option == "6":
                _run_event(env_file, "finish", dry_run)
            elif option == "7":
                _show_status(_load_current_config(env_file))
            elif option == "8":
                _run_monitor_once(env_file, dry_run)
            elif option == "9":
                _run_monitor_loop(env_file, dry_run)
            elif option == "10":
                _show_protocols()
            elif option == "11":
                dry_run = not dry_run
            elif option == "12":
                _install_codex_hook_interactive(env_file, dry_run)
            elif option == "13":
                _uninstall_codex_hook_interactive(dry_run)
            elif option == "14":
                _ask_user_interactive(env_file, dry_run)
            elif option == "15":
                _observe_replies_once(_load_current_config(env_file), dry_run=dry_run)
            elif option == "16":
                _run_reply_observer_loop(env_file, dry_run)
            elif option == "17":
                args = argparse.Namespace(status=None, limit=50)
                _show_questions(args, _load_current_config(env_file))
            elif option == "18":
                _continue_task_interactive(env_file, dry_run)
            elif option == "0":
                return
            else:
                print("Opcao invalida.")
        except KeyboardInterrupt:
            print("\nOperacao interrompida.")
        except Exception as exc:  # noqa: BLE001 - mostra erro no menu sem derrubar a sessao.
            print(f"Erro: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Menu interativo do AI Presence Monitor.")
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help=f"Arquivo .env. Padrao: {DEFAULT_ENV_FILE}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inicia em modo teste, sem enviar notificacoes reais.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run_interactive(Path(args.env_file), dry_run=args.dry_run)
