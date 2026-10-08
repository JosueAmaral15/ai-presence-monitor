from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace
from typing import Literal

from .codex_input import CodexInputError, CodexQueueClient, send_native_message
from .control import (
    DEFAULT_PROMPT_RULE_OCCURRENCES,
    DEFAULT_SCHEDULED_PROMPT_TEXT,
    MAX_PROMPT_RULE_OCCURRENCES,
    MAX_SCHEDULED_PROMPT_DELAY_MINUTES,
    MAX_SCHEDULED_PROMPT_TEXT_LENGTH,
    PROMPT_RULE_TRIGGERS,
    ControlError,
    ControlSettings,
    ControlStore,
    PromptRule,
)
from .protocols import get_protocol
from .store import PresenceStore

PromptRuleRunState = Literal[
    "disabled",
    "automation_disabled",
    "waiting",
    "waiting_for_event",
    "waiting_for_confirmation",
    "dispatch_started",
    "input_emitted",
    "failed_or_uncertain",
]


@dataclass(frozen=True)
class PromptRuleRunResult:
    state: PromptRuleRunState
    rule_id: str | None = None
    due_at: float | None = None


def configure_prompt_rule(
    existing: PromptRule | None,
    *,
    enabled: bool,
    thread_id: str | None,
    trigger: str,
    delay_minutes: int,
    text: str,
    repeat_enabled: bool,
    repeat_interval_minutes: int,
    max_occurrences: int = DEFAULT_PROMPT_RULE_OCCURRENCES,
    now: float | None = None,
    rule_id: str | None = None,
) -> PromptRule:
    clean_trigger = _validate_trigger(trigger)
    delay = _validate_positive_minutes(delay_minutes, "atraso")
    interval = _validate_positive_minutes(repeat_interval_minutes, "intervalo")
    clean_text = _validate_text(text, allow_default=not enabled)
    clean_thread = (thread_id or "").strip() or None
    occurrence_limit = _validate_occurrence_limit(max_occurrences)
    stable_id = (existing.rule_id if existing else rule_id) or uuid.uuid4().hex

    configuration = (
        enabled,
        clean_thread,
        clean_trigger,
        delay,
        clean_text,
        repeat_enabled,
        interval,
        occurrence_limit,
    )
    if existing is not None:
        previous = (
            existing.enabled,
            existing.thread_id,
            existing.trigger,
            existing.delay_minutes,
            existing.text,
            existing.repeat_enabled,
            existing.repeat_interval_minutes,
            existing.max_occurrences,
        )
        if configuration == previous:
            return existing

    if not enabled:
        return PromptRule(
            rule_id=stable_id,
            enabled=False,
            thread_id=clean_thread,
            trigger=clean_trigger,
            delay_minutes=delay,
            text=clean_text,
            repeat_enabled=repeat_enabled,
            repeat_interval_minutes=interval,
            max_occurrences=occurrence_limit,
            last_state="disabled",
        )
    if clean_thread is None:
        raise ControlError("Selecione uma sessao Codex exata para a regra de prompt.")

    current_time = time.time() if now is None else now
    waiting_for_event = clean_trigger == "red_inactivity"
    return PromptRule(
        rule_id=stable_id,
        enabled=True,
        thread_id=clean_thread,
        trigger=clean_trigger,
        delay_minutes=delay,
        text=clean_text,
        repeat_enabled=repeat_enabled,
        repeat_interval_minutes=interval,
        max_occurrences=occurrence_limit,
        next_due_at=None if waiting_for_event else current_time + delay * 60,
        last_state="waiting_for_event" if waiting_for_event else "armed",
    )


def replace_prompt_rules(
    settings: ControlSettings,
    rules: tuple[PromptRule, ...] | list[PromptRule],
) -> ControlSettings:
    return replace(settings, prompt_rules=tuple(rules))


def process_prompt_rules(
    *,
    store: ControlStore,
    profile_id: str | None,
    presence_store: PresenceStore,
    now: float | None = None,
    client: CodexQueueClient | None = None,
) -> PromptRuleRunResult:
    checked_at = time.time() if now is None else now
    settings = store.load(profile_id)
    if not settings.prompt_rules:
        return PromptRuleRunResult("disabled")
    if not settings.task_automation_enabled:
        return PromptRuleRunResult("automation_disabled")

    waiting: PromptRuleRunResult | None = None
    for original in settings.prompt_rules:
        rule = original
        if not rule.enabled:
            continue
        if rule.awaiting_confirmation:
            observed_at = _later_session_observation(
                presence_store,
                profile_id=profile_id,
                thread_id=rule.thread_id,
                after=rule.last_attempt_at,
            )
            if observed_at is None:
                waiting = waiting or PromptRuleRunResult(
                    "waiting_for_confirmation",
                    rule_id=rule.rule_id,
                )
                continue
            rule = replace(
                rule,
                awaiting_confirmation=False,
                next_due_at=observed_at + rule.repeat_interval_minutes * 60,
                last_state="armed",
            )
            settings = _save_rule(store, profile_id, settings, rule)

        if rule.trigger == "red_inactivity" and rule.next_due_at is None:
            event_at = _red_inactivity_event_at(
                presence_store,
                worker_id=profile_id,
            )
            if event_at is None or checked_at < event_at:
                waiting = waiting or PromptRuleRunResult(
                    "waiting_for_event",
                    rule_id=rule.rule_id,
                )
                continue
            rule = replace(
                rule,
                next_due_at=event_at + rule.delay_minutes * 60,
                last_state="armed",
            )
            settings = _save_rule(store, profile_id, settings, rule)

        due_at = rule.next_due_at
        if due_at is None or due_at > checked_at:
            waiting = waiting or PromptRuleRunResult(
                "waiting",
                rule_id=rule.rule_id,
                due_at=due_at,
            )
            continue

        claimed = replace(
            rule,
            enabled=False,
            next_due_at=None,
            awaiting_confirmation=False,
            last_state="dispatching",
            last_attempt_at=checked_at,
        )
        settings = _save_rule(store, profile_id, settings, claimed)
        try:
            result = send_native_message(
                settings=settings,
                message=rule.text,
                destination="local",
                thread_id=rule.thread_id,
                client=client,
                detached=True,
            )
        except CodexInputError:
            _complete_dispatch(
                store,
                profile_id=profile_id,
                rule_id=rule.rule_id,
                state="failed_or_uncertain",
                checked_at=checked_at,
                repeat=False,
                occurrence_count=rule.occurrence_count,
            )
            return PromptRuleRunResult(
                "failed_or_uncertain",
                rule_id=rule.rule_id,
            )

        occurrence_count = rule.occurrence_count + 1
        should_repeat = rule.repeat_enabled and occurrence_count < rule.max_occurrences
        _complete_dispatch(
            store,
            profile_id=profile_id,
            rule_id=rule.rule_id,
            state=result.state,
            checked_at=checked_at,
            repeat=should_repeat,
            occurrence_count=occurrence_count,
        )
        return PromptRuleRunResult(result.state, rule_id=rule.rule_id)

    return waiting or PromptRuleRunResult("disabled")


def _save_rule(
    store: ControlStore,
    profile_id: str | None,
    settings: ControlSettings,
    updated: PromptRule,
) -> ControlSettings:
    rules = tuple(
        updated if rule.rule_id == updated.rule_id else rule
        for rule in settings.prompt_rules
    )
    saved = replace(settings, prompt_rules=rules)
    store.save(saved, profile_id)
    return saved


def _complete_dispatch(
    store: ControlStore,
    *,
    profile_id: str | None,
    rule_id: str,
    state: str,
    checked_at: float,
    repeat: bool,
    occurrence_count: int,
) -> None:
    settings = store.load(profile_id)
    current = next(
        (rule for rule in settings.prompt_rules if rule.rule_id == rule_id),
        None,
    )
    if current is None or current.last_state != "dispatching":
        return
    updated = replace(
        current,
        enabled=repeat,
        occurrence_count=occurrence_count,
        last_state="waiting_for_confirmation" if repeat else state,
        last_dispatch_at=checked_at if state != "failed_or_uncertain" else None,
        awaiting_confirmation=repeat,
    )
    _save_rule(store, profile_id, settings, updated)


def _later_session_observation(
    store: PresenceStore,
    *,
    profile_id: str | None,
    thread_id: str | None,
    after: float | None,
) -> float | None:
    if profile_id is None or thread_id is None or after is None:
        return None
    for session in store.list_codex_sessions(worker_id=profile_id):
        if session.session_id == thread_id and session.observed_at > after:
            return session.observed_at
    return None


def _red_inactivity_event_at(
    store: PresenceStore,
    *,
    worker_id: str | None,
) -> float | None:
    if worker_id is None:
        return None
    worker = store.get_worker(worker_id)
    if worker is None or worker.status != "active":
        return None
    try:
        protocol = get_protocol(worker.protocol)
    except ValueError:
        return None
    red_threshold = next(
        (threshold for threshold in protocol.thresholds if threshold.level == "red"),
        None,
    )
    if red_threshold is None:
        return None
    clock = getattr(worker, protocol.monitored_clock, None)
    if clock is None:
        return None
    return float(clock) + red_threshold.after_seconds


def _validate_trigger(value: str) -> str:
    clean = value.strip()
    if clean not in PROMPT_RULE_TRIGGERS:
        raise ControlError("Gatilho de regra de prompt invalido.")
    return clean


def _validate_positive_minutes(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ControlError(f"O {label} da regra precisa ser inteiro.")
    if not 1 <= value <= MAX_SCHEDULED_PROMPT_DELAY_MINUTES:
        raise ControlError(
            f"O {label} da regra precisa estar entre 1 e "
            f"{MAX_SCHEDULED_PROMPT_DELAY_MINUTES} minutos."
        )
    return value


def _validate_occurrence_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ControlError("O limite de ocorrencias precisa ser inteiro.")
    if not 1 <= value <= MAX_PROMPT_RULE_OCCURRENCES:
        raise ControlError(
            "O limite de ocorrencias precisa estar entre 1 e "
            f"{MAX_PROMPT_RULE_OCCURRENCES}."
        )
    return value


def _validate_text(value: str, *, allow_default: bool) -> str:
    clean = value.strip()
    if not clean and allow_default:
        return DEFAULT_SCHEDULED_PROMPT_TEXT
    if not clean:
        raise ControlError("O texto da regra de prompt nao pode ficar vazio.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise ControlError("O texto da regra de prompt precisa ter uma linha.")
    if len(clean) > MAX_SCHEDULED_PROMPT_TEXT_LENGTH:
        raise ControlError(
            "O texto da regra excede o limite de "
            f"{MAX_SCHEDULED_PROMPT_TEXT_LENGTH} caracteres."
        )
    return clean
