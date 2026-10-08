from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace
from typing import Literal

from .codex_input import CodexInputError, CodexQueueClient, send_native_message
from .control import (
    DEFAULT_SCHEDULED_PROMPT_TEXT,
    MAX_SCHEDULED_PROMPT_DELAY_MINUTES,
    MAX_SCHEDULED_PROMPT_TEXT_LENGTH,
    ControlError,
    ControlSettings,
    ControlStore,
)

ScheduledPromptRunState = Literal[
    "disabled",
    "waiting",
    "dispatch_started",
    "input_emitted",
    "failed_or_uncertain",
]


@dataclass(frozen=True)
class ScheduledPromptRunResult:
    state: ScheduledPromptRunState
    due_at: float | None = None


def configure_scheduled_prompt(
    settings: ControlSettings,
    *,
    enabled: bool,
    delay_minutes: int,
    text: str,
    thread_id: str | None,
    now: float | None = None,
    schedule_id: str | None = None,
) -> ControlSettings:
    delay = _validate_delay(delay_minutes)
    clean_text = _validate_text(text, allow_default=not enabled)
    target_thread = (thread_id or "").strip() or None

    if not enabled:
        return replace(
            settings,
            scheduled_prompt_enabled=False,
            scheduled_prompt_delay_minutes=delay,
            scheduled_prompt_text=clean_text,
            scheduled_prompt_thread_id=None,
            scheduled_prompt_due_at=None,
            scheduled_prompt_id=None,
            scheduled_prompt_last_state="disabled",
        )

    if not settings.native_input_enabled:
        raise ControlError(
            "Habilite a entrada nativa antes de programar um prompt."
        )
    if target_thread is None:
        raise ControlError("Selecione uma sessao Codex exata para o prompt.")

    unchanged = (
        settings.scheduled_prompt_enabled
        and settings.scheduled_prompt_delay_minutes == delay
        and settings.scheduled_prompt_text == clean_text
        and settings.scheduled_prompt_thread_id == target_thread
        and settings.scheduled_prompt_due_at is not None
        and settings.scheduled_prompt_id is not None
        and settings.scheduled_prompt_last_state == "armed"
    )
    if unchanged:
        return settings

    current_time = time.time() if now is None else now
    return replace(
        settings,
        scheduled_prompt_enabled=True,
        scheduled_prompt_delay_minutes=delay,
        scheduled_prompt_text=clean_text,
        scheduled_prompt_thread_id=target_thread,
        scheduled_prompt_due_at=current_time + delay * 60,
        scheduled_prompt_id=schedule_id or uuid.uuid4().hex,
        scheduled_prompt_last_state="armed",
        scheduled_prompt_last_attempt_at=None,
    )


def process_due_scheduled_prompt(
    *,
    store: ControlStore,
    now: float | None = None,
    client: CodexQueueClient | None = None,
) -> ScheduledPromptRunResult:
    checked_at = time.time() if now is None else now
    settings = store.load()
    if not settings.scheduled_prompt_enabled:
        return ScheduledPromptRunResult("disabled")
    due_at = settings.scheduled_prompt_due_at
    if due_at is None or due_at > checked_at:
        return ScheduledPromptRunResult("waiting", due_at=due_at)

    schedule_id = settings.scheduled_prompt_id
    thread_id = settings.scheduled_prompt_thread_id
    if schedule_id is None or thread_id is None:
        raise ControlError("O prompt temporizado habilitado esta incompleto.")

    claimed = replace(
        settings,
        scheduled_prompt_enabled=False,
        scheduled_prompt_due_at=None,
        scheduled_prompt_last_state="dispatching",
        scheduled_prompt_last_attempt_at=checked_at,
    )
    store.save(claimed)

    try:
        result = send_native_message(
            settings=claimed,
            message=claimed.scheduled_prompt_text,
            destination="local",
            thread_id=thread_id,
            client=client,
            detached=True,
        )
    except CodexInputError:
        _complete_claim(
            store,
            schedule_id=schedule_id,
            state="failed_or_uncertain",
        )
        return ScheduledPromptRunResult("failed_or_uncertain")

    _complete_claim(store, schedule_id=schedule_id, state=result.state)
    return ScheduledPromptRunResult(result.state)


def _complete_claim(
    store: ControlStore,
    *,
    schedule_id: str,
    state: str,
) -> None:
    latest = store.load()
    if (
        latest.scheduled_prompt_id != schedule_id
        or latest.scheduled_prompt_enabled
        or latest.scheduled_prompt_last_state != "dispatching"
    ):
        return
    store.save(replace(latest, scheduled_prompt_last_state=state))


def _validate_delay(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ControlError("O atraso do prompt precisa ser um numero inteiro.")
    if not 1 <= value <= MAX_SCHEDULED_PROMPT_DELAY_MINUTES:
        raise ControlError(
            "O atraso do prompt precisa estar entre 1 e "
            f"{MAX_SCHEDULED_PROMPT_DELAY_MINUTES} minutos."
        )
    return value


def _validate_text(value: str, *, allow_default: bool) -> str:
    clean = value.strip()
    if not clean and allow_default:
        return DEFAULT_SCHEDULED_PROMPT_TEXT
    if not clean:
        raise ControlError("O texto do prompt nao pode ficar vazio.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise ControlError("O texto do prompt precisa ter uma unica linha.")
    if len(clean) > MAX_SCHEDULED_PROMPT_TEXT_LENGTH:
        raise ControlError(
            "O texto do prompt excede o limite de "
            f"{MAX_SCHEDULED_PROMPT_TEXT_LENGTH} caracteres."
        )
    return clean
