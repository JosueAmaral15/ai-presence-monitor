from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .codex_app_server import RateLimitSnapshot, read_codex_rate_limits
from .codex_evidence import codex_limit_observation_from_snapshot
from .codex_input import CodexQueueClient
from .control import ControlStore
from .prompt_rule_observer import (
    PromptRuleObserverResult,
    due_usage_rule_targets,
    observe_prompt_rules_once,
)
from .prompt_rules import PromptRuleRunResult, process_prompt_rules
from .quota_recovery import (
    QuotaRecoveryObserverResult,
    enabled_quota_recovery_targets,
    observe_quota_recovery_once,
)
from .store import PresenceStore


@dataclass(frozen=True)
class AutomationObserverResult:
    prompt_rules: PromptRuleObserverResult
    quota_recovery: QuotaRecoveryObserverResult


def observe_automations_once(
    *,
    control_store: ControlStore,
    presence_store: PresenceStore,
    evidence_ttl_seconds: int,
    request_timeout: float = 10.0,
    codex_executable: str = "codex",
    now: float | None = None,
    reader: Callable[..., RateLimitSnapshot] = read_codex_rate_limits,
    client: CodexQueueClient | None = None,
) -> AutomationObserverResult:
    checked_at = time.time() if now is None else now
    queue_client = client or CodexQueueClient(executable=codex_executable)
    preliminary_results = _process_usage_gated_rules(
        control_store=control_store,
        presence_store=presence_store,
        checked_at=checked_at,
        client=queue_client,
    )
    prompt_targets = due_usage_rule_targets(
        control_store=control_store,
        presence_store=presence_store,
        now=checked_at,
    )
    quota_targets = enabled_quota_recovery_targets(
        control_store=control_store,
        presence_store=presence_store,
    )
    if not prompt_targets and not quota_targets:
        return AutomationObserverResult(
            PromptRuleObserverResult(
                (),
                None,
                tuple(result for _, result in preliminary_results),
            ),
            QuotaRecoveryObserverResult((), (), ()),
        )

    snapshot = reader(
        codex_executable=codex_executable,
        request_timeout=request_timeout,
    )
    observation = codex_limit_observation_from_snapshot(
        snapshot,
        ttl_seconds=evidence_ttl_seconds,
        observed_at=checked_at,
    )
    prompt_result = observe_prompt_rules_once(
        control_store=control_store,
        presence_store=presence_store,
        evidence_ttl_seconds=evidence_ttl_seconds,
        request_timeout=request_timeout,
        codex_executable=codex_executable,
        now=checked_at,
        collector=lambda **_: observation,
        client=queue_client,
    )
    target_profiles = {target.profile_id for target in prompt_targets}
    preliminary_visible = tuple(
        result
        for profile_id, result in preliminary_results
        if profile_id not in target_profiles
    )
    prompt_result = PromptRuleObserverResult(
        prompt_result.targets,
        prompt_result.observation_state,
        preliminary_visible + prompt_result.rule_results,
    )
    quota_result = observe_quota_recovery_once(
        control_store=control_store,
        presence_store=presence_store,
        request_timeout=request_timeout,
        codex_executable=codex_executable,
        now=checked_at,
        reader=lambda **_: snapshot,
        client=queue_client,
    )
    return AutomationObserverResult(prompt_result, quota_result)


def _process_usage_gated_rules(
    *,
    control_store: ControlStore,
    presence_store: PresenceStore,
    checked_at: float,
    client: CodexQueueClient,
) -> tuple[tuple[str, PromptRuleRunResult], ...]:
    results: list[tuple[str, PromptRuleRunResult]] = []
    for profile_id in control_store.list_profile_ids():
        settings = control_store.load(profile_id)
        if not settings.task_automation_enabled:
            continue
        if not any(
            rule.enabled and rule.require_usage_available
            for rule in settings.prompt_rules
        ):
            continue
        result = process_prompt_rules(
            store=control_store,
            profile_id=profile_id,
            presence_store=presence_store,
            now=checked_at,
            client=client,
            usage_gated_only=True,
        )
        results.append((profile_id, result))
    return tuple(results)
