from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .codex_evidence import (
    CodexLimitObservation,
    collect_codex_limit_observation,
    record_codex_limit_observation,
)
from .codex_input import CodexQueueClient
from .control import ControlStore
from .prompt_rules import PromptRuleRunResult, process_prompt_rules
from .store import PresenceStore


@dataclass(frozen=True)
class UsageRuleTarget:
    profile_id: str
    session_id: str


@dataclass(frozen=True)
class PromptRuleObserverResult:
    targets: tuple[UsageRuleTarget, ...]
    observation_state: str | None
    rule_results: tuple[PromptRuleRunResult, ...]


def due_usage_rule_targets(
    *,
    control_store: ControlStore,
    presence_store: PresenceStore,
    now: float | None = None,
) -> tuple[UsageRuleTarget, ...]:
    checked_at = time.time() if now is None else now
    targets: list[UsageRuleTarget] = []
    for profile_id in control_store.list_profile_ids():
        settings = control_store.load(profile_id)
        if not settings.task_automation_enabled:
            continue
        if presence_store.get_worker(profile_id) is None:
            continue
        for rule in settings.prompt_rules:
            if (
                rule.enabled
                and rule.require_usage_available
                and rule.thread_id is not None
                and rule.next_due_at is not None
                and rule.next_due_at <= checked_at
            ):
                target = UsageRuleTarget(profile_id, rule.thread_id)
                if target not in targets:
                    targets.append(target)
    return tuple(targets)


def observe_prompt_rules_once(
    *,
    control_store: ControlStore,
    presence_store: PresenceStore,
    evidence_ttl_seconds: int,
    request_timeout: float = 10.0,
    codex_executable: str = "codex",
    now: float | None = None,
    collector: Callable[..., CodexLimitObservation] = collect_codex_limit_observation,
    client: CodexQueueClient | None = None,
) -> PromptRuleObserverResult:
    checked_at = time.time() if now is None else now
    targets = due_usage_rule_targets(
        control_store=control_store,
        presence_store=presence_store,
        now=checked_at,
    )
    if not targets:
        return PromptRuleObserverResult((), None, ())

    observation = collector(
        codex_executable=codex_executable,
        request_timeout=request_timeout,
        ttl_seconds=evidence_ttl_seconds,
        observed_at=checked_at,
    )
    results: list[PromptRuleRunResult] = []
    for target in targets:
        record_codex_limit_observation(
            db_path=presence_store.db_path,
            worker_id=target.profile_id,
            session_id=target.session_id,
            observation=observation,
        )
        results.append(
            process_prompt_rules(
                store=control_store,
                profile_id=target.profile_id,
                presence_store=presence_store,
                now=checked_at,
                client=client,
                usage_gated_only=True,
            )
        )
    return PromptRuleObserverResult(targets, observation.state, tuple(results))
