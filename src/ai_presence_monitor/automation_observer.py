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
            PromptRuleObserverResult((), None, ()),
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
    queue_client = client or CodexQueueClient(executable=codex_executable)
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
