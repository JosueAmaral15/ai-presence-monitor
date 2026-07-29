from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig, load_config
from .identity import scoped_worker_id
from .protocols import get_protocol
from .store import PresenceStore, WorkerState

EVENT_NAME_KEYS = ("hook_event_name", "hookEventName")
TOOL_NAME_KEYS = ("tool_name", "toolName", "tool", "name")
SAFE_METADATA_KEYS = (
    "session_id",
    "turn_id",
    "cwd",
    "hook_event_name",
    "hookEventName",
    "model",
    "permission_mode",
    "source",
    "tool_name",
    "toolName",
    "tool",
    "name",
)


@dataclass(frozen=True)
class CodexHookObservation:
    event_name: str
    worker_id: str
    computer: str
    ia_name: str
    protocol: str
    task: str | None
    message: str


def load_hook_payload(stdin_text: str) -> dict[str, Any]:
    if not stdin_text.strip():
        return {}
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        raise ValueError("O payload do hook precisa ser um objeto JSON.")
    return payload


def extract_event_name(payload: dict[str, Any]) -> str:
    for key in EVENT_NAME_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "UnknownHook"


def extract_tool_name(payload: dict[str, Any]) -> str | None:
    for key in TOOL_NAME_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def safe_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = {}
    for key in SAFE_METADATA_KEYS:
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata[key] = value
    return metadata


def default_task_from_payload(payload: dict[str, Any]) -> str | None:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        return None
    return Path(cwd).expanduser().resolve().name


def build_observation(payload: dict[str, Any], config: AppConfig) -> CodexHookObservation:
    event_name = extract_event_name(payload)
    tool_name = extract_tool_name(payload)
    protocol = config.codex_protocol or config.default_protocol
    get_protocol(protocol)

    ia_name = config.codex_ai_name or "codex"
    base_worker_id = config.codex_worker_id or f"{config.computer_name}:{ia_name}"
    cwd = payload.get("cwd")
    project_path = cwd if isinstance(cwd, str) and cwd.strip() else None
    raw_session_id = payload.get("session_id")
    session_id = (
        raw_session_id
        if isinstance(raw_session_id, str) and raw_session_id.strip()
        else None
    )
    worker_id = scoped_worker_id(
        base_worker_id,
        config.codex_worker_scope,
        project_path=project_path,
        session_id=session_id,
    )
    task = config.codex_task or default_task_from_payload(payload)

    message_parts = [f"codex hook {event_name}"]
    if tool_name:
        message_parts.append(f"tool={tool_name}")
    if session_id:
        message_parts.append(f"session={session_id}")

    metadata = safe_metadata(payload)
    if metadata:
        message_parts.append(
            "metadata=" + json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        )

    return CodexHookObservation(
        event_name=event_name,
        worker_id=worker_id,
        computer=config.computer_name,
        ia_name=ia_name,
        protocol=protocol,
        task=task,
        message=" | ".join(message_parts),
    )


def record_codex_hook_payload(
    *,
    payload: dict[str, Any],
    config: AppConfig,
    dry_run: bool = False,
    auto_start: bool | None = None,
) -> WorkerState | None:
    observation = build_observation(payload, config)
    if dry_run:
        return WorkerState(
            worker_id=observation.worker_id,
            computer=observation.computer,
            ia_name=observation.ia_name,
            protocol=observation.protocol,
            status="active",
            current_task=observation.task,
            last_signal_at=None,
            last_activity_at=None,
            last_message=observation.message,
            last_alert_level=None,
            last_alert_at=None,
            updated_at=0,
        )

    store = PresenceStore(config.db_path)
    worker = store.record_observation(
        worker_id=observation.worker_id,
        computer=observation.computer,
        ia_name=observation.ia_name,
        protocol=observation.protocol,
        source=f"codex:{observation.event_name}",
        message=observation.message,
        task=observation.task,
        auto_start=config.codex_auto_start if auto_start is None else auto_start,
    )
    if worker is not None and worker.last_activity_at is not None:
        store.confirm_deliveries(
            worker_id=worker.worker_id,
            observed_at=worker.last_activity_at,
            timeout_seconds=config.gui_confirmation_timeout_seconds,
        )
    return worker


def run_from_stdin(
    *,
    config: AppConfig,
    stdin_text: str,
    dry_run: bool = False,
    quiet: bool = True,
    fail_closed: bool | None = None,
    auto_start: bool | None = None,
) -> int:
    should_fail = config.codex_hook_fail_closed if fail_closed is None else fail_closed
    try:
        payload = load_hook_payload(stdin_text)
        worker = record_codex_hook_payload(
            payload=payload,
            config=config,
            dry_run=dry_run,
            auto_start=auto_start,
        )
    except Exception as exc:  # noqa: BLE001 - hooks devem proteger o loop do Codex.
        if not quiet:
            print(f"codex-hook: {exc}", file=sys.stderr)
        return 1 if should_fail else 0

    if not quiet:
        if worker is None:
            print("codex-hook: observacao ignorada; worker inexistente e auto-start desligado.")
        elif dry_run:
            print(f"codex-hook: dry-run worker={worker.worker_id} protocolo={worker.protocol}")
        else:
            print(f"codex-hook: atividade registrada worker={worker.worker_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Observer passivo para hooks do Codex.")
    parser.add_argument("--env-file", help="Arquivo .env do AI Presence Monitor.")
    parser.add_argument("--dry-run", action="store_true", help="Nao grava no banco.")
    parser.add_argument("--verbose", action="store_true", help="Mostra resultado no stdout/stderr.")
    parser.add_argument(
        "--fail-closed",
        action="store_true",
        help="Retorna erro se o hook nao conseguir registrar atividade.",
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Nao cria worker automaticamente quando ele ainda nao existe.",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Cria ou reativa worker automaticamente a partir do hook.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = load_config(args.env_file, override_env=True)
    raise SystemExit(
        run_from_stdin(
            config=config,
            stdin_text=sys.stdin.read(),
            dry_run=args.dry_run,
            quiet=not args.verbose,
            fail_closed=args.fail_closed or None,
            auto_start=True if args.auto_start else False if args.no_auto_start else None,
        )
    )


if __name__ == "__main__":
    main()
