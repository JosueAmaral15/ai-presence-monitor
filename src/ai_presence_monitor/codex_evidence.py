from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .codex_app_server import RateLimitSnapshot, read_codex_rate_limits
from .diagnostics import (
    DiagnosticEvidence,
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
)


@dataclass(frozen=True)
class CodexLimitObservation:
    state: str
    summary: str
    observed_at: float
    expires_at: float


_HOOK_EVIDENCE: dict[str, tuple[EvidenceKind, str, str]] = {
    "SessionStart": (
        EvidenceKind.THREAD_STATUS,
        "session_started",
        "Codex session started.",
    ),
    "UserPromptSubmit": (
        EvidenceKind.ACTIVITY,
        "prompt_submitted",
        "Codex accepted user input.",
    ),
    "PreToolUse": (
        EvidenceKind.ACTIVITY,
        "tool_started",
        "Codex started a tool call.",
    ),
    "PostToolUse": (
        EvidenceKind.ACTIVITY,
        "tool_completed",
        "Codex completed a tool call.",
    ),
    "Stop": (
        EvidenceKind.TURN_STATUS,
        "stopped",
        "Codex emitted a stop hook.",
    ),
    "Interrupt": (
        EvidenceKind.TURN_STATUS,
        "interrupted",
        "Codex emitted an interrupt hook.",
    ),
    "SessionEnd": (
        EvidenceKind.THREAD_STATUS,
        "session_ended",
        "Codex session ended.",
    ),
    "PreCompact": (
        EvidenceKind.CONTEXT_COMPACTION,
        "started",
        "Codex context compaction started.",
    ),
    "PostCompact": (
        EvidenceKind.CONTEXT_COMPACTION,
        "completed",
        "Codex context compaction completed.",
    ),
    "SubagentStart": (
        EvidenceKind.ACTIVITY,
        "subagent_started",
        "Codex started a subagent.",
    ),
    "SubagentStop": (
        EvidenceKind.ACTIVITY,
        "subagent_stopped",
        "Codex stopped a subagent.",
    ),
}

_LIMIT_SUMMARIES = {
    "rate_limit_reached": "Codex reported that an account rate limit was reached.",
    "workspace_owner_credits_depleted": "Codex reported depleted workspace owner credits.",
    "workspace_member_credits_depleted": "Codex reported depleted workspace member credits.",
    "workspace_owner_usage_limit_reached": "Codex reported a workspace owner usage limit.",
    "workspace_member_usage_limit_reached": "Codex reported a workspace member usage limit.",
}


def record_codex_hook_evidence(
    *,
    db_path: Path,
    worker_id: str,
    session_id: str | None,
    event_name: str,
    observed_at: float,
    ttl_seconds: int,
) -> DiagnosticEvidence | None:
    mapped = _HOOK_EVIDENCE.get(event_name)
    if mapped is None:
        return None
    _require_positive_seconds(ttl_seconds, "hook evidence TTL")
    kind, state, summary = mapped
    return DiagnosticStore(db_path).record_evidence(
        worker_id=worker_id,
        session_id=session_id,
        source=EvidenceSource.CODEX_HOOK,
        kind=kind,
        state=state,
        summary=summary,
        observed_at=observed_at,
        expires_at=observed_at + ttl_seconds,
    )


def collect_codex_limit_observation(
    *,
    codex_executable: str = "codex",
    request_timeout: float = 10.0,
    ttl_seconds: int = 600,
    observed_at: float | None = None,
    reader: Callable[..., RateLimitSnapshot] = read_codex_rate_limits,
) -> CodexLimitObservation:
    _require_positive_seconds(ttl_seconds, "limit evidence TTL")
    snapshot = reader(
        codex_executable=codex_executable,
        request_timeout=request_timeout,
    )
    state, summary = classify_rate_limits(snapshot)
    timestamp = time.time() if observed_at is None else observed_at
    return CodexLimitObservation(
        state=state,
        summary=summary,
        observed_at=timestamp,
        expires_at=timestamp + ttl_seconds,
    )


def record_codex_limit_observation(
    *,
    db_path: Path,
    worker_id: str,
    session_id: str | None,
    observation: CodexLimitObservation,
) -> DiagnosticEvidence:
    return DiagnosticStore(db_path).record_evidence(
        worker_id=worker_id,
        session_id=session_id,
        source=EvidenceSource.CODEX_APP_SERVER,
        kind=EvidenceKind.ACCOUNT_LIMIT,
        state=observation.state,
        summary=observation.summary,
        observed_at=observation.observed_at,
        expires_at=observation.expires_at,
    )


def classify_rate_limits(snapshot: RateLimitSnapshot) -> tuple[str, str]:
    if snapshot.reached_type is not None:
        summary = _LIMIT_SUMMARIES.get(snapshot.reached_type)
        if summary is not None:
            return snapshot.reached_type, summary
        return "account_limit_reached", "Codex reported an unclassified account limit."
    if snapshot.spend_control_reached is True:
        return "spend_control_reached", "Codex reported that spend control was reached."
    if snapshot.ordinary_usage_allowed is False:
        return "ordinary_usage_blocked", "Codex reported ordinary usage as blocked."
    if snapshot.ordinary_usage_allowed is True:
        return "usage_available", "Codex reported ordinary usage as available."
    return "usage_unknown", "Codex did not report ordinary usage availability."


def _require_positive_seconds(value: int, label: str) -> None:
    if value <= 0:
        raise ValueError(f"{label} must be greater than zero.")
