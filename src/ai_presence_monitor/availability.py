from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .codex_app_server import (
    CodexAppServerError,
    RateLimitSnapshot,
    read_codex_thread,
)

AvailabilityState = Literal["available", "unavailable", "unknown"]
SessionTargetState = Literal["available", "unknown"]


class AvailabilityProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def classify(self, snapshot: object) -> AvailabilityState: ...

    def validate_session(self, thread_id: str) -> SessionTargetState: ...


class AvailabilityProviderFactory(Protocol):
    def create(self, provider_id: str) -> AvailabilityProvider: ...


class UnsupportedAvailabilityProvider(ValueError):
    pass


@dataclass(frozen=True)
class CodexAvailabilityProvider:
    codex_executable: str = "codex"
    request_timeout: float = 10.0
    provider_id: str = "codex"

    def classify(self, snapshot: object) -> AvailabilityState:
        if not isinstance(snapshot, RateLimitSnapshot):
            return "unknown"
        if snapshot.ordinary_usage_allowed is True:
            return "available"
        if snapshot.ordinary_usage_allowed is False:
            return "unavailable"

        known_windows = tuple(
            window.used_percent
            for window in (snapshot.primary, snapshot.secondary)
            if window is not None and window.used_percent is not None
        )
        if not known_windows:
            return "unknown"
        if any(percent >= 100 for percent in known_windows):
            return "unavailable"
        if len(known_windows) == 2:
            return "available"
        return "unknown"

    def validate_session(self, thread_id: str) -> SessionTargetState:
        try:
            snapshot = read_codex_thread(
                thread_id,
                codex_executable=self.codex_executable,
                request_timeout=self.request_timeout,
            )
        except CodexAppServerError:
            return "unknown"
        return "available" if snapshot.thread_id == thread_id else "unknown"


@dataclass(frozen=True)
class DefaultAvailabilityProviderFactory:
    codex_executable: str = "codex"
    request_timeout: float = 10.0

    def create(self, provider_id: str) -> AvailabilityProvider:
        if provider_id == "codex":
            return CodexAvailabilityProvider(
                codex_executable=self.codex_executable,
                request_timeout=self.request_timeout,
            )
        raise UnsupportedAvailabilityProvider(
            f"Availability provider is not installed: {provider_id}"
        )
