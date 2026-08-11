from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .config import AppConfig
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
    target: WindowTarget | None
    worker: WorkerState | None


def countdown(
    seconds: int,
    *,
    sleep: Callable[[float], None] = time.sleep,
    output: Callable[[str], None] = print,
) -> None:
    for remaining in range(seconds, 0, -1):
        output(
            f"Aguardando {remaining}s antes de clicar, escrever e enviar..."
        )
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
    dry_run: bool = False,
    store: PresenceStore | None = None,
    dispatcher: GuiAnswerDispatcher | None = None,
    wait: Callable[[int], None] = countdown,
    now: float | None = None,
) -> ContinueTaskResult:
    text = config.continue_message if message is None else message
    if not text.strip():
        raise ContinueTaskError("A mensagem de continuidade nao pode ficar vazia.")

    delay = config.continue_delay_seconds if delay_seconds is None else delay_seconds
    if delay < 0:
        raise ContinueTaskError("O atraso de continuidade nao pode ser negativo.")

    pattern = title_pattern or config.codex_gui_window_title
    if not pattern:
        raise ContinueTaskError(
            "Informe --window-title ou PRESENCE_CODEX_GUI_WINDOW_TITLE."
        )
    if allow_title_change and not window_id:
        raise ContinueTaskError(
            "--allow-title-change exige um --window-id explicito."
        )

    should_sync = (
        config.continue_sync_activity
        if sync_activity is None
        else sync_activity
    )
    if dry_run:
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=False,
            activity_synced=False,
            sync_reason="dry_run",
            target=None,
            worker=None,
        )

    try:
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
    except (GuiDispatchError, UnsupportedPlatformError) as exc:
        raise ContinueTaskError(str(exc)) from exc

    if not should_sync:
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=True,
            activity_synced=False,
            sync_reason="disabled",
            target=target,
            worker=None,
        )

    presence_store = store or PresenceStore(config.db_path)
    current_worker = presence_store.get_worker(worker_id)
    if current_worker is None:
        return ContinueTaskResult(
            worker_id=worker_id,
            message=text,
            delay_seconds=delay,
            input_emitted=True,
            activity_synced=False,
            sync_reason="worker_missing",
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
            target=target,
            worker=current_worker,
        )

    updated_worker = presence_store.record_observation(
        worker_id=current_worker.worker_id,
        computer=current_worker.computer,
        ia_name=current_worker.ia_name,
        protocol=current_worker.protocol,
        source="automation:continue",
        message="entrada automatizada de continuidade emitida",
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
        target=target,
        worker=updated_worker,
    )
