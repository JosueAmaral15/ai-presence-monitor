from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Callable, Literal

from .codex_app_server import (
    RateLimitSnapshot,
    RateLimitWindowSnapshot,
    read_codex_rate_limits,
)
from .codex_input import CodexInputError, CodexQueueClient, send_native_message
from .control import (
    MAX_SCHEDULED_PROMPT_TEXT_LENGTH,
    QUOTA_RECOVERY_WINDOWS,
    ControlError,
    ControlSettings,
    ControlStore,
    QuotaRecoveryRule,
)
from .store import PresenceStore

QuotaWindowState = Literal["available", "exhausted", "unknown"]
QuotaRecoveryRunState = Literal[
    "disabled",
    "automation_disabled",
    "armed",
    "waiting_for_availability",
    "dispatch_started",
    "input_emitted",
    "failed_or_uncertain",
    "unknown",
]

FIVE_HOUR_MINUTES = 5 * 60
WEEKLY_MINUTES = 7 * 24 * 60


@dataclass(frozen=True)
class QuotaRecoveryTarget:
    profile_id: str


@dataclass(frozen=True)
class QuotaRecoveryRunResult:
    profile_id: str
    window: str
    state: QuotaRecoveryRunState


@dataclass(frozen=True)
class QuotaRecoveryObserverResult:
    targets: tuple[QuotaRecoveryTarget, ...]
    window_states: tuple[tuple[str, QuotaWindowState], ...]
    rule_results: tuple[QuotaRecoveryRunResult, ...]


def configure_quota_recovery_rule(
    existing: QuotaRecoveryRule | None,
    *,
    window: str,
    enabled: bool,
    thread_id: str | None,
    text: str,
) -> QuotaRecoveryRule:
    if window not in QUOTA_RECOVERY_WINDOWS:
        raise ControlError("A janela de recuperacao de cota e invalida.")
    clean_thread = (thread_id or "").strip() or None
    clean_text = text.strip()
    if (
        not clean_text
        or len(clean_text) > MAX_SCHEDULED_PROMPT_TEXT_LENGTH
        or any(character in clean_text for character in ("\r", "\n", "\x00"))
    ):
        raise ControlError("O texto da recuperacao de cota e invalido.")
    if enabled and clean_thread is None:
        raise ControlError("Selecione uma sessao Codex exata para recuperar a cota.")

    configuration = (window, enabled, clean_thread, clean_text)
    if existing is not None:
        previous = (
            existing.window,
            existing.enabled,
            existing.thread_id,
            existing.text,
        )
        if configuration == previous:
            return existing
    return QuotaRecoveryRule(
        window=window,
        enabled=enabled,
        thread_id=clean_thread,
        text=clean_text,
        last_state="armed" if enabled else "disabled",
    )


def replace_quota_recovery_rules(
    settings: ControlSettings,
    rules: tuple[QuotaRecoveryRule, ...] | list[QuotaRecoveryRule],
) -> ControlSettings:
    return replace(settings, quota_recovery_rules=tuple(rules))


def enabled_quota_recovery_targets(
    *,
    control_store: ControlStore,
    presence_store: PresenceStore,
) -> tuple[QuotaRecoveryTarget, ...]:
    targets: list[QuotaRecoveryTarget] = []
    for profile_id in control_store.list_profile_ids():
        settings = control_store.load(profile_id)
        if not settings.task_automation_enabled:
            continue
        if presence_store.get_worker(profile_id) is None:
            continue
        if any(rule.enabled for rule in settings.quota_recovery_rules):
            targets.append(QuotaRecoveryTarget(profile_id))
    return tuple(targets)


def classify_quota_windows(
    snapshot: RateLimitSnapshot,
) -> dict[str, QuotaWindowState]:
    states: dict[str, QuotaWindowState] = {
        "five_hour": "unknown",
        "weekly": "unknown",
    }
    for window in (snapshot.primary, snapshot.secondary):
        name = _window_name(window)
        if name is None or window is None or window.used_percent is None:
            continue
        states[name] = "exhausted" if window.used_percent >= 100 else "available"
    return states


def observe_quota_recovery_once(
    *,
    control_store: ControlStore,
    presence_store: PresenceStore,
    request_timeout: float = 10.0,
    codex_executable: str = "codex",
    now: float | None = None,
    reader: Callable[..., RateLimitSnapshot] = read_codex_rate_limits,
    client: CodexQueueClient | None = None,
) -> QuotaRecoveryObserverResult:
    targets = enabled_quota_recovery_targets(
        control_store=control_store,
        presence_store=presence_store,
    )
    if not targets:
        return QuotaRecoveryObserverResult((), (), ())
    snapshot = reader(
        codex_executable=codex_executable,
        request_timeout=request_timeout,
    )
    window_states = classify_quota_windows(snapshot)
    queue_client = client or CodexQueueClient(executable=codex_executable)
    checked_at = time.time() if now is None else now
    results: list[QuotaRecoveryRunResult] = []
    for target in targets:
        results.extend(
            process_quota_recovery_snapshot(
                store=control_store,
                profile_id=target.profile_id,
                window_states=window_states,
                checked_at=checked_at,
                client=queue_client,
            )
        )
    return QuotaRecoveryObserverResult(
        targets,
        tuple(sorted(window_states.items())),
        tuple(results),
    )


def process_quota_recovery_snapshot(
    *,
    store: ControlStore,
    profile_id: str,
    window_states: dict[str, QuotaWindowState],
    checked_at: float,
    client: CodexQueueClient,
) -> tuple[QuotaRecoveryRunResult, ...]:
    settings = store.load(profile_id)
    if not settings.task_automation_enabled:
        return tuple(
            QuotaRecoveryRunResult(profile_id, rule.window, "automation_disabled")
            for rule in settings.quota_recovery_rules
            if rule.enabled
        )
    results: list[QuotaRecoveryRunResult] = []
    for original in settings.quota_recovery_rules:
        if not original.enabled:
            continue
        observed_state = window_states.get(original.window, "unknown")
        if observed_state == "unknown":
            results.append(
                QuotaRecoveryRunResult(profile_id, original.window, "unknown")
            )
            continue
        if observed_state == "exhausted":
            if original.last_state != "waiting_for_availability":
                updated = replace(
                    original,
                    last_state="waiting_for_availability",
                    exhausted_observed_at=checked_at,
                    last_attempt_at=None,
                    last_dispatch_at=None,
                )
                settings = _save_rule(store, profile_id, settings, updated)
            results.append(
                QuotaRecoveryRunResult(
                    profile_id,
                    original.window,
                    "waiting_for_availability",
                )
            )
            continue
        if original.last_state != "waiting_for_availability":
            results.append(
                QuotaRecoveryRunResult(profile_id, original.window, "armed")
            )
            continue

        claimed = replace(
            original,
            last_state="dispatching",
            last_attempt_at=checked_at,
        )
        settings = _save_rule(store, profile_id, settings, claimed)
        try:
            result = send_native_message(
                settings=settings,
                message=original.text,
                destination="local",
                thread_id=original.thread_id,
                client=client,
                detached=True,
            )
        except CodexInputError:
            _complete_dispatch(
                store,
                profile_id=profile_id,
                window=original.window,
                state="failed_or_uncertain",
                checked_at=checked_at,
            )
            results.append(
                QuotaRecoveryRunResult(
                    profile_id,
                    original.window,
                    "failed_or_uncertain",
                )
            )
            continue
        _complete_dispatch(
            store,
            profile_id=profile_id,
            window=original.window,
            state=result.state,
            checked_at=checked_at,
        )
        results.append(
            QuotaRecoveryRunResult(profile_id, original.window, result.state)
        )
    return tuple(results)


def _window_name(window: RateLimitWindowSnapshot | None) -> str | None:
    if window is None:
        return None
    if window.window_duration_minutes == FIVE_HOUR_MINUTES:
        return "five_hour"
    if window.window_duration_minutes == WEEKLY_MINUTES:
        return "weekly"
    return None


def _save_rule(
    store: ControlStore,
    profile_id: str,
    settings: ControlSettings,
    updated: QuotaRecoveryRule,
) -> ControlSettings:
    rules = tuple(
        updated if rule.window == updated.window else rule
        for rule in settings.quota_recovery_rules
    )
    saved = replace(settings, quota_recovery_rules=rules)
    store.save(saved, profile_id)
    return saved


def _complete_dispatch(
    store: ControlStore,
    *,
    profile_id: str,
    window: str,
    state: str,
    checked_at: float,
) -> None:
    settings = store.load(profile_id)
    current = next(
        (rule for rule in settings.quota_recovery_rules if rule.window == window),
        None,
    )
    if current is None or current.last_state != "dispatching":
        return
    updated = replace(
        current,
        last_state=state,
        last_dispatch_at=(checked_at if state != "failed_or_uncertain" else None),
    )
    _save_rule(store, profile_id, settings, updated)
