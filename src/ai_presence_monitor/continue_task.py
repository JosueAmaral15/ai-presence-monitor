from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .codex_input import CodexInputError, CodexQueueClient
from .config import AppConfig
from .control import ControlSettings
from .gui_answer import GuiAnswerDispatcher, GuiDispatchError, WindowTarget
from .platform_integration import UnsupportedPlatformError, get_platform_factory
from .store import PresenceStore, WorkerState


class ContinueTaskError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContinueTaskResult:
    worker_id: str
    message: str
    delay_seconds: int
    input_emitted: bool
    activity_synced: bool
    sync_reason: str
    transport: str
    destination: str
    thread_id: str | None
    target: WindowTarget | None
    worker: WorkerState | None


def countdown(
    seconds: int,
    *,
    sleep: Callable[[float], None] = time.sleep,
    output: Callable[[str], None] = print,
) -> None:
    for remaining in range(seconds, 0, -1):
        output(f"Aguardando {remaining}s antes de enviar a mensagem...")
        sleep(1)


def execute_continue_task(
    *,
    config: AppConfig,
    worker_id: str,
    message: str | None = None,
    delay_seconds: int | None = None,
    window_id: str | None = None,
    title_pattern: str | None = None,
    allow_title_change: bool = False,
    sync_activity: bool | None = None,
    input_transport: str | None = None,
    input_destination: str | None = None,
    thread_id: str | None = None,
    remote: str | None = None,
    remote_auth_token_env: str | None = None,
    dry_run: bool = False,
    store: PresenceStore | None = None,
    dispatcher: GuiAnswerDispatcher | None = None,
    queue_client: CodexQueueClient | None = None,
    controls: ControlSettings | None = None,
    wait: Callable[[int], None] = countdown,
    now: float | None = None,
) -> ContinueTaskResult:
    text = config.continue_message if message is None else message
    if not text.strip():
        raise ContinueTaskError("A mensagem de continuidade nao pode ficar vazia.")

    delay = config.continue_delay_seconds if delay_seconds is None else delay_seconds
    if delay < 0:
        raise ContinueTaskError("O atraso de continuidade nao pode ser negativo.")

    active_controls = controls or ControlSettings.from_config(config)
    should_sync = (
        active_controls.sync_activity_enabled
        if sync_activity is None
        else sync_activity
    )
    mode = (input_transport or config.continue_transport).strip().lower()
    if mode not in {"auto", "native", "gui"}:
        raise ContinueTaskError(
            "Transporte invalido. Use auto, native ou gui."
        )

    presence_store = store
    resolved_thread = (
        _clean_optional(thread_id)
        or active_controls.codex_thread_id
        or config.codex_thread_id
    )
    native_client = queue_client or CodexQueueClient()
    if (
        resolved_thread is None
        and not dry_run
        and mode in {"auto", "native"}
        and active_controls.native_input_enabled
    ):
        presence_store = presence_store or PresenceStore(config.db_path)
        resolved_thread = presence_store.latest_codex_session_id(worker_id)

    selected_transport = _select_transport(
        mode=mode,
        controls=active_controls,
        thread_id=resolved_thread,
        native_available=dry_run or native_client.is_available(),
    )
    destination = (input_destination or config.continue_destination).strip().lower()
    if remote is not None:
        destination = "client"
    if destination not in {"local", "client"}:
        raise ContinueTaskError("Destino invalido. Use local ou client.")
    if selected_transport == "gui" and destination != "local":
        raise ContinueTaskError("O fallback GUI nao oferece destino client.")
    if destination == "client":
        if not active_controls.remote_input_enabled:
            raise ContinueTaskError("A entrada em computador cliente esta desativada.")
        resolved_remote = _clean_optional(remote) or active_controls.codex_remote
        resolved_auth_env = (
            _clean_optional(remote_auth_token_env)
            or active_controls.remote_auth_token_env
        )
        if not resolved_remote:
            raise ContinueTaskError("Configure o endpoint do computador cliente.")
    else:
        resolved_remote = None
        resolved_auth_env = None

    pattern = title_pattern or config.codex_gui_window_title
    if selected_transport == "gui":
        if not pattern:
            raise ContinueTaskError(
                "Informe --window-title ou PRESENCE_CODEX_GUI_WINDOW_TITLE."
            )
        if allow_title_change and not window_id:
            raise ContinueTaskError(
                "--allow-title-change exige um --window-id explicito."
            )
    if dry_run:
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=False,
            activity_synced=False,
            sync_reason="dry_run",
            transport=selected_transport,
            destination=destination,
            thread_id=resolved_thread,
            target=None,
            worker=None,
        )

    target: WindowTarget | None = None
    try:
        if selected_transport == "native":
            assert resolved_thread is not None
            wait(delay)
            native_client.send(
                thread_id=resolved_thread,
                text=text,
                remote=resolved_remote,
                remote_auth_token_env=resolved_auth_env,
            )
        else:
            assert pattern is not None
            actor = dispatcher or get_platform_factory().create_gui_dispatcher(
                x_ratio=config.codex_gui_click_x_ratio,
                y_ratio=config.codex_gui_click_y_ratio,
            )
            target = actor.capture_target(
                title_pattern=pattern,
                window_id=window_id,
            )
            wait(delay)
            actor.dispatch_text(
                target=target,
                text=text,
                allow_title_change=allow_title_change,
            )
    except (CodexInputError, GuiDispatchError, UnsupportedPlatformError) as exc:
        raise ContinueTaskError(str(exc)) from exc

    if not should_sync:
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=True,
            activity_synced=False,
            sync_reason="disabled",
            transport=selected_transport,
            destination=destination,
            thread_id=resolved_thread,
            target=target,
            worker=None,
        )

    presence_store = presence_store or PresenceStore(config.db_path)
    current_worker = presence_store.get_worker(worker_id)
    if current_worker is None:
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=True,
            activity_synced=False,
            sync_reason="worker_missing",
            transport=selected_transport,
            destination=destination,
            thread_id=resolved_thread,
            target=target,
            worker=None,
        )
    if current_worker.status != "active":
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=True,
            activity_synced=False,
            sync_reason="worker_idle",
            transport=selected_transport,
            destination=destination,
            thread_id=resolved_thread,
            target=target,
            worker=current_worker,
        )

    updated_worker = presence_store.record_observation(
        worker_id=current_worker.worker_id,
        computer=current_worker.computer,
        ia_name=current_worker.ia_name,
        protocol=current_worker.protocol,
        source="automation:continue",
        message=(
            "entrada automatizada de continuidade emitida "
            f"transport={selected_transport}"
        ),
        task=current_worker.current_task,
        auto_start=False,
        now=now,
    )
    if updated_worker is None:
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=True,
            activity_synced=False,
            sync_reason="worker_inactive",
            transport=selected_transport,
            destination=destination,
            thread_id=resolved_thread,
            target=target,
            worker=current_worker,
        )
    return ContinueTaskResult(
        worker_id=worker_id,
        message=text,
        delay_seconds=delay,
        input_emitted=True,
        activity_synced=True,
        sync_reason="synced",
        transport=selected_transport,
        destination=destination,
        thread_id=resolved_thread,
        target=target,
        worker=updated_worker,
    )


def _select_transport(
    *,
    mode: str,
    controls: ControlSettings,
    thread_id: str | None,
    native_available: bool,
) -> str:
    if mode == "native":
        if not controls.native_input_enabled:
            raise ContinueTaskError("O transporte nativo esta desativado.")
        if not thread_id:
            raise ContinueTaskError(
                "O transporte nativo exige --thread, PRESENCE_CODEX_THREAD_ID "
                "ou um hook recente do mesmo worker."
            )
        if not native_available:
            raise ContinueTaskError("O executavel codex nao esta disponivel no PATH.")
        return "native"
    if mode == "gui":
        if not controls.gui_fallback_enabled:
            raise ContinueTaskError("O fallback GUI esta desativado.")
        return "gui"

    if controls.native_input_enabled and thread_id and native_available:
        return "native"
    if controls.gui_fallback_enabled:
        return "gui"
    if controls.native_input_enabled and not thread_id:
        raise ContinueTaskError(
            "Nenhuma sessao Codex foi informada ou observada, e o fallback GUI "
            "esta desativado."
        )
    raise ContinueTaskError("Nenhum transporte de entrada esta habilitado.")


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
