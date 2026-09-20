from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable, Protocol


class CodexAppServerError(RuntimeError):
    """Raised when the bounded read-only app-server probe cannot continue."""


class JsonRpcTransport(Protocol):
    def send(self, payload: dict[str, object]) -> None: ...

    def receive(self, timeout_seconds: float) -> dict[str, object]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class ThreadSnapshot:
    thread_id: str
    status: str | None
    active_flags: tuple[str, ...]


@dataclass(frozen=True)
class RateLimitWindowSnapshot:
    used_percent: int | None
    resets_at: int | None
    window_duration_minutes: int | None


@dataclass(frozen=True)
class RateLimitSnapshot:
    ordinary_usage_allowed: bool | None
    reached_type: str | None
    plan_type: str | None
    primary: RateLimitWindowSnapshot | None
    secondary: RateLimitWindowSnapshot | None
    has_credits: bool | None
    unlimited_credits: bool | None
    spend_control_reached: bool | None


@dataclass(frozen=True)
class SanitizedCodexEvent:
    method: str
    thread_id: str | None = None
    turn_id: str | None = None
    status: str | None = None
    active_flags: tuple[str, ...] = ()
    error_type: str | None = None
    http_status_code: int | None = None
    total_tokens: int | None = None
    last_tokens: int | None = None
    model_context_window: int | None = None


@dataclass(frozen=True)
class CodexAppServerProbeResult:
    thread: ThreadSnapshot
    rate_limits: RateLimitSnapshot
    subscription_seconds: float
    events: tuple[SanitizedCodexEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_END_OF_STREAM = object()


class SubprocessJsonRpcTransport:
    """Newline-delimited JSON-RPC over a dedicated Codex child process."""

    def __init__(self, codex_executable: str = "codex") -> None:
        try:
            self._process = subprocess.Popen(
                [codex_executable, "app-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise CodexAppServerError(
                "Could not start the Codex app-server executable."
            ) from exc

        if self._process.stdin is None or self._process.stdout is None:
            self._process.terminate()
            raise CodexAppServerError("Codex app-server stdio is unavailable.")

        self._messages: queue.Queue[str | object] = queue.Queue()
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._messages.put(line)
        finally:
            self._messages.put(_END_OF_STREAM)

    def send(self, payload: dict[str, object]) -> None:
        if self._process.poll() is not None:
            raise CodexAppServerError("Codex app-server exited before the request.")
        assert self._process.stdin is not None
        try:
            self._process.stdin.write(
                json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n"
            )
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise CodexAppServerError("Could not write to Codex app-server.") from exc

    def receive(self, timeout_seconds: float) -> dict[str, object]:
        try:
            raw_message = self._messages.get(timeout=max(0.0, timeout_seconds))
        except queue.Empty as exc:
            raise TimeoutError("Timed out waiting for Codex app-server.") from exc

        if raw_message is _END_OF_STREAM:
            raise CodexAppServerError("Codex app-server closed its output stream.")
        try:
            payload = json.loads(str(raw_message))
        except json.JSONDecodeError as exc:
            raise CodexAppServerError(
                "Codex app-server returned an invalid JSON-RPC message."
            ) from exc
        if not isinstance(payload, dict):
            raise CodexAppServerError(
                "Codex app-server returned a non-object JSON-RPC message."
            )
        return payload

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=2.0)


class CodexAppServerClient:
    """A hard-allowlisted observational client with sanitized output only."""

    ALLOWED_REQUEST_METHODS = frozenset(
        {
            "initialize",
            "thread/read",
            "account/rateLimits/read",
            "thread/resume",
            "thread/unsubscribe",
        }
    )
    _ALLOWED_CLIENT_NOTIFICATIONS = frozenset({"initialized"})
    _ACTIVE_FLAGS = frozenset({"waitingOnApproval", "waitingOnUserInput"})
    _THREAD_STATUSES = frozenset({"notLoaded", "idle", "systemError", "active"})
    _TURN_STATUSES = frozenset({"completed", "interrupted", "failed", "inProgress"})
    _ERROR_TYPES = frozenset(
        {
            "activeTurnNotSteerable",
            "badRequest",
            "contextWindowExceeded",
            "cyberPolicy",
            "httpConnectionFailed",
            "internalServerError",
            "misalignmentPolicyViolation",
            "other",
            "rateLimitExceeded",
            "responseStreamConnectionFailed",
            "responseStreamDisconnected",
            "responseTooManyFailedAttempts",
            "sandboxError",
            "serverOverloaded",
            "sessionBudgetExceeded",
            "threadRollbackFailed",
            "unauthorized",
            "usageLimitExceeded",
        }
    )
    _RATE_LIMIT_REACHED_TYPES = frozenset(
        {
            "rate_limit_reached",
            "workspace_member_credits_depleted",
            "workspace_member_usage_limit_reached",
            "workspace_owner_credits_depleted",
            "workspace_owner_usage_limit_reached",
        }
    )
    _PLAN_TYPES = frozenset(
        {
            "business",
            "edu",
            "edu_plus",
            "edu_pro",
            "ent26",
            "enterprise",
            "enterprise_cbp_automation",
            "enterprise_cbp_usage_based",
            "free",
            "go",
            "plus",
            "pro",
            "prolite",
            "self_serve_business_prolite",
            "self_serve_business_usage_based",
            "team",
            "unknown",
        }
    )
    _SERVER_REQUEST_EVENTS = frozenset(
        {
            "applyPatchApproval",
            "execCommandApproval",
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
            "item/tool/requestUserInput",
            "mcpServer/elicitation/request",
        }
    )
    _OPT_OUT_NOTIFICATION_METHODS = (
        "command/exec/outputDelta",
        "item/agentMessage/delta",
        "item/commandExecution/outputDelta",
        "item/commandExecution/terminalInteraction",
        "item/fileChange/outputDelta",
        "item/fileChange/patchUpdated",
        "item/mcpToolCall/progress",
        "item/plan/delta",
        "item/reasoning/summaryPartAdded",
        "item/reasoning/summaryTextDelta",
        "item/reasoning/textDelta",
        "mcpServer/event/stream/notification",
        "process/outputDelta",
        "thread/realtime/item/transcript/delta",
        "thread/realtime/outputAudio/delta",
        "thread/realtime/sdp",
        "thread/realtime/transcript/delta",
        "thread/realtime/transcript/done",
        "turn/diff/updated",
        "turn/plan/updated",
    )

    def __init__(self, transport: JsonRpcTransport, *, request_timeout: float = 10.0) -> None:
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero.")
        self._transport = transport
        self._request_timeout = request_timeout
        self._next_request_id = 1
        self._initialized = False

    def initialize(self) -> None:
        self.request_read_only(
            "initialize",
            {
                "clientInfo": {
                    "name": "ai-presence-monitor-read-only-probe",
                    "version": "0.1",
                },
                "capabilities": {
                    "experimentalApi": False,
                    "optOutNotificationMethods": list(
                        self._OPT_OUT_NOTIFICATION_METHODS
                    ),
                },
            },
        )
        self._send_notification("initialized", {})
        self._initialized = True

    def request_read_only(
        self,
        method: str,
        params: dict[str, object],
        *,
        events: list[SanitizedCodexEvent] | None = None,
        expected_thread_id: str | None = None,
    ) -> dict[str, object]:
        if method not in self.ALLOWED_REQUEST_METHODS:
            raise CodexAppServerError(
                f"Codex app-server method is not allowed by the read-only probe: {method}"
            )
        self._validate_request_params(method, params)
        if method != "initialize" and not self._initialized:
            raise CodexAppServerError("Codex app-server client is not initialized.")

        request_id = self._next_request_id
        self._next_request_id += 1
        self._transport.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self._request_timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CodexAppServerError(
                    f"Timed out waiting for Codex app-server method {method}."
                )
            try:
                message = self._transport.receive(remaining)
            except TimeoutError as exc:
                raise CodexAppServerError(
                    f"Timed out waiting for Codex app-server method {method}."
                ) from exc

            if message.get("id") == request_id:
                if "error" in message:
                    error = message.get("error")
                    code = error.get("code") if isinstance(error, dict) else "unknown"
                    reason = _classify_rpc_error(error)
                    raise CodexAppServerError(
                        f"Codex app-server method {method} failed with error code "
                        f"{code} (reason={reason})."
                    )
                result = message.get("result")
                if not isinstance(result, dict):
                    raise CodexAppServerError(
                        f"Codex app-server method {method} returned no object result."
                    )
                return result

            event = sanitize_codex_message(
                message,
                expected_thread_id=expected_thread_id,
            )
            if event is not None and events is not None:
                events.append(event)

    def _validate_request_params(
        self,
        method: str,
        params: dict[str, object],
    ) -> None:
        if method == "initialize":
            client_info = _mapping(params.get("clientInfo"))
            capabilities = _mapping(params.get("capabilities"))
            valid = (
                set(params) == {"clientInfo", "capabilities"}
                and client_info
                == {
                    "name": "ai-presence-monitor-read-only-probe",
                    "version": "0.1",
                }
                and set(capabilities)
                == {"experimentalApi", "optOutNotificationMethods"}
                and capabilities.get("experimentalApi") is False
                and capabilities.get("optOutNotificationMethods")
                == list(self._OPT_OUT_NOTIFICATION_METHODS)
            )
        elif method == "thread/read":
            valid = (
                set(params) == {"threadId", "includeTurns"}
                and _is_valid_identifier(params.get("threadId"))
                and params.get("includeTurns") is False
            )
        elif method == "account/rateLimits/read":
            valid = params == {"excludeResetCreditDetails": True}
        elif method == "thread/resume":
            valid = (
                set(params) == {"threadId", "excludeTurns"}
                and _is_valid_identifier(params.get("threadId"))
                and params.get("excludeTurns") is True
            )
        else:
            valid = (
                set(params) == {"threadId"}
                and _is_valid_identifier(params.get("threadId"))
            )
        if not valid:
            raise CodexAppServerError(
                f"Unsafe parameters rejected for Codex app-server method {method}."
            )

    def _send_notification(self, method: str, params: dict[str, object]) -> None:
        if method not in self._ALLOWED_CLIENT_NOTIFICATIONS or params:
            raise CodexAppServerError(
                f"Codex app-server notification is not allowed: {method}"
            )
        self._transport.send({"method": method, "params": params})

    def read_thread(self, thread_id: str) -> ThreadSnapshot:
        clean_thread_id = _required_identifier(thread_id)
        result = self.request_read_only(
            "thread/read",
            {"threadId": clean_thread_id, "includeTurns": False},
        )
        thread = _mapping(result.get("thread"))
        returned_id = thread.get("id")
        if returned_id != clean_thread_id:
            raise CodexAppServerError(
                "Codex app-server returned metadata for a different thread."
            )
        status, active_flags = _sanitize_thread_status(thread.get("status"))
        return ThreadSnapshot(clean_thread_id, status, active_flags)

    def read_rate_limits(self) -> RateLimitSnapshot:
        result = self.request_read_only(
            "account/rateLimits/read",
            {"excludeResetCreditDetails": True},
        )
        return _sanitize_rate_limits(result)

    def observe_thread(
        self,
        thread_id: str,
        duration_seconds: float,
    ) -> tuple[SanitizedCodexEvent, ...]:
        if duration_seconds <= 0:
            return ()

        clean_thread_id = _required_identifier(thread_id)
        events: list[SanitizedCodexEvent] = []
        self.request_read_only(
            "thread/resume",
            {"threadId": clean_thread_id, "excludeTurns": True},
            events=events,
            expected_thread_id=clean_thread_id,
        )
        deadline = time.monotonic() + duration_seconds
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    message = self._transport.receive(remaining)
                except TimeoutError:
                    break
                event = sanitize_codex_message(
                    message,
                    expected_thread_id=clean_thread_id,
                )
                if event is not None:
                    events.append(event)
        finally:
            self.request_read_only(
                "thread/unsubscribe",
                {"threadId": clean_thread_id},
                events=events,
                expected_thread_id=clean_thread_id,
            )
        return tuple(events)


def probe_codex_app_server(
    thread_id: str,
    *,
    subscription_seconds: float = 0.0,
    codex_executable: str = "codex",
    request_timeout: float = 10.0,
    transport_factory: Callable[[str], JsonRpcTransport] = SubprocessJsonRpcTransport,
) -> CodexAppServerProbeResult:
    if subscription_seconds < 0:
        raise ValueError("subscription_seconds cannot be negative.")
    transport = transport_factory(codex_executable)
    try:
        client = CodexAppServerClient(transport, request_timeout=request_timeout)
        client.initialize()
        thread = client.read_thread(thread_id)
        rate_limits = client.read_rate_limits()
        events = client.observe_thread(thread_id, subscription_seconds)
        return CodexAppServerProbeResult(
            thread=thread,
            rate_limits=rate_limits,
            subscription_seconds=subscription_seconds,
            events=events,
        )
    finally:
        transport.close()


def read_codex_rate_limits(
    *,
    codex_executable: str = "codex",
    request_timeout: float = 10.0,
    transport_factory: Callable[[str], JsonRpcTransport] = SubprocessJsonRpcTransport,
) -> RateLimitSnapshot:
    transport = transport_factory(codex_executable)
    try:
        client = CodexAppServerClient(transport, request_timeout=request_timeout)
        client.initialize()
        return client.read_rate_limits()
    finally:
        transport.close()


def sanitize_codex_message(
    message: dict[str, object],
    *,
    expected_thread_id: str | None = None,
) -> SanitizedCodexEvent | None:
    method = message.get("method")
    if not isinstance(method, str):
        return None

    params = _mapping(message.get("params"))
    thread_id = _optional_identifier(params.get("threadId"))
    if expected_thread_id is not None and thread_id != expected_thread_id:
        return None

    if "id" in message and method in CodexAppServerClient._SERVER_REQUEST_EVENTS:
        request_status = (
            "waitingOnUserInput"
            if method == "item/tool/requestUserInput"
            else "waitingOnApproval"
        )
        return SanitizedCodexEvent(
            method=method,
            thread_id=thread_id,
            status=request_status,
        )

    if method == "thread/status/changed":
        thread_status, active_flags = _sanitize_thread_status(params.get("status"))
        return SanitizedCodexEvent(
            method=method,
            thread_id=thread_id,
            status=thread_status,
            active_flags=active_flags,
        )

    if method in {"turn/started", "turn/completed"}:
        turn = _mapping(params.get("turn"))
        error_type, http_status_code = _sanitize_codex_error(turn.get("error"))
        return SanitizedCodexEvent(
            method=method,
            thread_id=thread_id,
            turn_id=_optional_identifier(turn.get("id")),
            status=_enum_string(turn.get("status"), CodexAppServerClient._TURN_STATUSES),
            error_type=error_type,
            http_status_code=http_status_code,
        )

    if method == "thread/tokenUsage/updated":
        usage = _mapping(params.get("tokenUsage"))
        total = _mapping(usage.get("total"))
        last = _mapping(usage.get("last"))
        return SanitizedCodexEvent(
            method=method,
            thread_id=thread_id,
            turn_id=_optional_identifier(params.get("turnId")),
            total_tokens=_optional_int(total.get("totalTokens")),
            last_tokens=_optional_int(last.get("totalTokens")),
            model_context_window=_optional_int(usage.get("modelContextWindow")),
        )

    if method in {"item/started", "item/completed"}:
        item = _mapping(params.get("item"))
        if item.get("type") != "contextCompaction":
            return None
        return SanitizedCodexEvent(
            method="contextCompaction",
            thread_id=thread_id,
            turn_id=_optional_identifier(params.get("turnId")),
            status="started" if method == "item/started" else "completed",
        )

    if method == "thread/compacted":
        return SanitizedCodexEvent(method=method, thread_id=thread_id)

    return None


def _sanitize_thread_status(value: object) -> tuple[str | None, tuple[str, ...]]:
    status = _mapping(value)
    status_type = _enum_string(
        status.get("type"),
        CodexAppServerClient._THREAD_STATUSES,
    )
    raw_flags = status.get("activeFlags")
    flags: tuple[str, ...] = ()
    if isinstance(raw_flags, list):
        flags = tuple(
            flag
            for flag in raw_flags
            if isinstance(flag, str) and flag in CodexAppServerClient._ACTIVE_FLAGS
        )
    return status_type, flags


def _sanitize_codex_error(value: object) -> tuple[str | None, int | None]:
    error = _mapping(value)
    info = error.get("codexErrorInfo")
    if isinstance(info, str):
        return (
            info if info in CodexAppServerClient._ERROR_TYPES else "other",
            None,
        )
    if not isinstance(info, dict) or not info:
        return None, None
    error_type = next(
        (
            key
            for key in info
            if isinstance(key, str) and key in CodexAppServerClient._ERROR_TYPES
        ),
        "other",
    )
    details = _mapping(info.get(error_type)) if error_type is not None else {}
    return error_type, _optional_int(details.get("httpStatusCode"))


def _sanitize_rate_limits(result: dict[str, object]) -> RateLimitSnapshot:
    limits = _mapping(result.get("rateLimits"))
    credits = _mapping(limits.get("credits"))
    ordinary_usage_allowed = result.get("ordinaryUsageAllowed")
    return RateLimitSnapshot(
        ordinary_usage_allowed=(
            ordinary_usage_allowed if isinstance(ordinary_usage_allowed, bool) else None
        ),
        reached_type=_enum_string_or_other(
            limits.get("rateLimitReachedType"),
            CodexAppServerClient._RATE_LIMIT_REACHED_TYPES,
        ),
        plan_type=_enum_string(
            limits.get("planType"),
            CodexAppServerClient._PLAN_TYPES,
        ),
        primary=_sanitize_rate_limit_window(limits.get("primary")),
        secondary=_sanitize_rate_limit_window(limits.get("secondary")),
        has_credits=_optional_bool(credits.get("hasCredits")),
        unlimited_credits=_optional_bool(credits.get("unlimited")),
        spend_control_reached=_optional_bool(limits.get("spendControlReached")),
    )


def _sanitize_rate_limit_window(value: object) -> RateLimitWindowSnapshot | None:
    window = _mapping(value)
    if not window:
        return None
    return RateLimitWindowSnapshot(
        used_percent=_optional_int(window.get("usedPercent")),
        resets_at=_optional_int(window.get("resetsAt")),
        window_duration_minutes=_optional_int(window.get("windowDurationMins")),
    )


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if isinstance(key, str)}


def _required_identifier(value: str) -> str:
    clean = value.strip()
    if not _is_valid_identifier(clean):
        raise ValueError("thread_id must be a bounded protocol identifier.")
    return clean


_PROTOCOL_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _optional_identifier(value: object) -> str | None:
    if not _is_valid_identifier(value):
        return None
    return value if isinstance(value, str) else None


def _is_valid_identifier(value: object) -> bool:
    return isinstance(value, str) and _PROTOCOL_ID.fullmatch(value) is not None


def _enum_string(value: object, allowed: frozenset[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _enum_string_or_other(value: object, allowed: frozenset[str]) -> str | None:
    if not isinstance(value, str):
        return None
    return value if value in allowed else "other"


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _classify_rpc_error(value: object) -> str:
    error = _mapping(value)
    message = error.get("message")
    lowered = message.lower() if isinstance(message, str) else ""
    if all(signal in lowered for signal in ("thread", "already", "active")):
        return "thread_already_active"
    if "thread" in lowered and any(
        signal in lowered for signal in ("not found", "does not exist", "no rollout")
    ):
        return "thread_not_found"
    if any(
        signal in lowered for signal in ("invalid param", "missing field", "unknown field")
    ):
        return "invalid_parameters"
    return "unclassified"
