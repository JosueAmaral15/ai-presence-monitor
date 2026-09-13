from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, cast

from .answer_dispatch import (
    AnswerDispatcher,
    AnswerDispatchError,
    AnswerTransport,
    GuiQuestionAnswerDispatcher,
    NativeCodexAnswerDispatcher,
)
from .codex_input import CodexInputError, CodexQueueClient, resolve_native_destination
from .config import AppConfig
from .control import ControlSettings
from .discord_questions import (
    DiscordQuestionClient,
    DiscordQuestionError,
    ReplyGuidanceReason,
)
from .gui_answer import GuiAnswerDispatcher, GuiDispatchError, WindowTarget
from .platform_integration import UnsupportedPlatformError, get_platform_factory
from .store import PresenceStore, RemoteQuestion

CURSOR_KEY_PREFIX = "discord-question-channel:"
ANSWER_TRANSPORTS = frozenset({"native", "gui", "store"})
ANSWER_DESTINATIONS = frozenset({"local", "client"})


class RemoteQuestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplyObserverResult:
    fetched: int
    accepted: int
    dispatched: int
    dispatch_failed: int
    guided: int
    guidance_failed: int


@dataclass(frozen=True)
class QuestionTarget:
    transport: AnswerTransport
    session_id: str | None = None
    destination: str | None = None
    remote: str | None = None
    remote_auth_token_env: str | None = None
    window: WindowTarget | None = None


def validate_remote_question_config(config: AppConfig) -> None:
    if not config.remote_questions_enabled:
        raise RemoteQuestionError(
            "Respostas remotas estao desativadas. "
            "Defina PRESENCE_REMOTE_QUESTIONS_ENABLED=true."
        )
    missing = []
    if not config.discord_question_webhook_url:
        missing.append("DISCORD_QUESTION_WEBHOOK_URL")
    if not config.discord_bot_token:
        missing.append("DISCORD_BOT_TOKEN")
    if not config.discord_question_channel_id:
        missing.append("DISCORD_QUESTION_CHANNEL_ID")
    if not config.discord_allowed_user_ids:
        missing.append("DISCORD_ALLOWED_USER_IDS")
    if missing:
        raise RemoteQuestionError(
            "Configuracao incompleta para respostas Discord: " + ", ".join(missing)
        )


def build_discord_client(config: AppConfig) -> DiscordQuestionClient:
    validate_remote_question_config(config)
    assert config.discord_question_webhook_url is not None
    assert config.discord_bot_token is not None
    assert config.discord_question_channel_id is not None
    return DiscordQuestionClient(
        webhook_url=config.discord_question_webhook_url,
        bot_token=config.discord_bot_token,
        channel_id=config.discord_question_channel_id,
    )


def capture_gui_target(
    config: AppConfig,
    *,
    window_id: str | None = None,
    title_pattern: str | None = None,
    dispatcher: GuiAnswerDispatcher | None = None,
) -> WindowTarget | None:
    if not config.gui_answer_enabled:
        return None
    pattern = title_pattern or config.codex_gui_window_title
    if not pattern:
        raise RemoteQuestionError(
            "PRESENCE_CODEX_GUI_WINDOW_TITLE e obrigatorio quando a entrega GUI esta ativa."
        )
    try:
        actor = dispatcher or get_platform_factory(
            experimental_windows_enabled=config.experimental_windows_enabled,
        ).create_gui_dispatcher(
            x_ratio=config.codex_gui_click_x_ratio,
            y_ratio=config.codex_gui_click_y_ratio,
        )
        return actor.capture_target(title_pattern=pattern, window_id=window_id)
    except (GuiDispatchError, UnsupportedPlatformError) as exc:
        raise RemoteQuestionError(str(exc)) from exc


def resolve_question_target(
    *,
    config: AppConfig,
    store: PresenceStore,
    worker_id: str,
    answer_transport: str | None = None,
    thread_id: str | None = None,
    destination: str | None = None,
    window_id: str | None = None,
    title_pattern: str | None = None,
    controls: ControlSettings | None = None,
    dispatcher: GuiAnswerDispatcher | None = None,
    now: float | None = None,
) -> QuestionTarget:
    settings = controls or ControlSettings.from_config(config)
    transport = (answer_transport or config.question_answer_transport).strip().lower()
    if transport not in ANSWER_TRANSPORTS:
        raise RemoteQuestionError(
            "Transporte de resposta invalido; use native, gui ou store."
        )
    if transport == "store":
        return QuestionTarget(transport="store")
    if transport == "gui":
        if not settings.gui_fallback_enabled:
            raise RemoteQuestionError(
                "O fallback GUI esta desativado. Habilite-o explicitamente antes da pergunta."
            )
        window = capture_gui_target(
            config,
            window_id=window_id,
            title_pattern=title_pattern,
            dispatcher=dispatcher,
        )
        if window is None:
            raise RemoteQuestionError("A entrega GUI nao produziu um alvo de janela.")
        return QuestionTarget(transport="gui", window=window)

    if not settings.native_input_enabled:
        raise RemoteQuestionError("O transporte nativo esta desativado.")
    target_session = _resolve_question_session(
        config=config,
        store=store,
        worker_id=worker_id,
        explicit_thread=thread_id,
        configured_thread=settings.codex_thread_id,
        now=now,
    )
    target_destination = (
        destination or config.question_answer_destination
    ).strip().lower()
    if target_destination not in ANSWER_DESTINATIONS:
        raise RemoteQuestionError(
            "Destino da resposta invalido; use local ou client."
        )
    try:
        _, remote, auth_env = resolve_native_destination(
            settings=settings,
            destination="remote" if target_destination == "client" else "local",
            thread_id=target_session,
        )
    except CodexInputError as exc:
        raise RemoteQuestionError(str(exc)) from exc
    return QuestionTarget(
        transport="native",
        session_id=target_session,
        destination=target_destination,
        remote=remote,
        remote_auth_token_env=auth_env,
    )


def ask_remote_question(
    *,
    config: AppConfig,
    store: PresenceStore,
    worker_id: str,
    prompt: str,
    timeout_seconds: int | None = None,
    answer_transport: str | None = None,
    thread_id: str | None = None,
    destination: str | None = None,
    window_id: str | None = None,
    title_pattern: str | None = None,
    client: DiscordQuestionClient | None = None,
    controls: ControlSettings | None = None,
    dispatcher: GuiAnswerDispatcher | None = None,
    now: float | None = None,
) -> RemoteQuestion:
    validate_remote_question_config(config)
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise RemoteQuestionError("A pergunta nao pode ficar vazia.")
    timeout = (
        config.question_timeout_seconds
        if timeout_seconds is None
        else timeout_seconds
    )
    if timeout <= 0:
        raise RemoteQuestionError("O prazo da pergunta precisa ser maior que zero.")

    target = resolve_question_target(
        config=config,
        store=store,
        worker_id=worker_id,
        answer_transport=answer_transport,
        thread_id=thread_id,
        destination=destination,
        window_id=window_id,
        title_pattern=title_pattern,
        controls=controls,
        dispatcher=dispatcher,
        now=now,
    )
    question = store.create_question(
        worker_id=worker_id,
        prompt=clean_prompt,
        timeout_seconds=timeout,
        answer_transport=target.transport,
        target_session_id=target.session_id,
        target_destination=target.destination,
        target_remote=target.remote,
        target_remote_auth_token_env=target.remote_auth_token_env,
        target_window_id=target.window.window_id if target.window else None,
        target_window_title=target.window.title if target.window else None,
        target_window_pattern=target.window.pattern if target.window else None,
        now=now,
    )

    transport = client or build_discord_client(config)
    try:
        posted = transport.post_question(
            question_id=question.question_id,
            worker_id=question.worker_id,
            prompt=question.prompt,
        )
        return store.mark_question_published(
            question.question_id,
            channel_id=posted.channel_id,
            external_message_id=posted.message_id,
            now=now,
        )
    except (DiscordQuestionError, OSError, ValueError) as exc:
        store.mark_question_error(
            question.question_id,
            status="publish_failed",
            error=str(exc),
            allowed_statuses=("pending",),
            now=now,
        )
        raise RemoteQuestionError(str(exc)) from exc


def observe_discord_replies_once(
    *,
    config: AppConfig,
    store: PresenceStore,
    client: DiscordQuestionClient | None = None,
    dispatcher: GuiAnswerDispatcher | None = None,
    native_client: CodexQueueClient | None = None,
    controls: ControlSettings | None = None,
    now: float | None = None,
) -> ReplyObserverResult:
    validate_remote_question_config(config)
    checked_at = time.time() if now is None else now
    store.expire_questions(checked_at)
    transport = client or build_discord_client(config)
    assert config.discord_question_channel_id is not None
    cursor_key = CURSOR_KEY_PREFIX + config.discord_question_channel_id
    cursor = store.get_observer_state(cursor_key)
    pending_by_message_id = {
        question.external_message_id: question
        for question in store.list_questions(status="pending", limit=1000)
        if (
            question.channel_id == config.discord_question_channel_id
            and question.external_message_id is not None
            and question.external_message_id.isdigit()
        )
    }
    if cursor is None:
        pending_message_ids = list(pending_by_message_id)
        if pending_message_ids:
            cursor = min(pending_message_ids, key=int)

    try:
        messages = transport.fetch_messages(after=cursor)
    except DiscordQuestionError as exc:
        raise RemoteQuestionError(str(exc)) from exc

    accepted = 0
    dispatched = 0
    dispatch_failed = 0
    guided = 0
    guidance_failed = 0
    settings = controls or ControlSettings.from_config(config)
    gui_actor = dispatcher

    last_message_id = cursor
    for message in messages:
        message_id = _snowflake(message.get("id"))
        if message_id is None:
            continue
        last_message_id = _max_snowflake(last_message_id, message_id)
        candidate = _allowed_human_message(message, config)
        if candidate is None:
            continue

        referenced_message_id, author_id, content = candidate
        guidance_reasons = _reply_guidance_reasons(
            referenced_message_id=referenced_message_id,
            content=content,
            pending_message_ids=set(pending_by_message_id),
        )
        if guidance_reasons:
            if pending_by_message_id:
                try:
                    transport.post_reply_guidance(
                        author_id=author_id,
                        pending_count=len(pending_by_message_id),
                        reasons=guidance_reasons,
                    )
                    guided += 1
                except (DiscordQuestionError, OSError, ValueError):
                    guidance_failed += 1
            continue

        assert referenced_message_id is not None
        question = store.record_question_answer(
            external_message_id=referenced_message_id,
            channel_id=config.discord_question_channel_id,
            reply_message_id=message_id,
            answered_by=author_id,
            answer=content,
            now=checked_at,
        )
        if question is None:
            continue
        accepted += 1
        pending_by_message_id.pop(referenced_message_id, None)

        try:
            question_transport = _stored_question_transport(question)
            if question_transport == "store":
                continue
            answer_dispatcher, gui_actor = _build_answer_dispatcher(
                config=config,
                transport=question_transport,
                controls=settings,
                gui_dispatcher=gui_actor,
                native_client=native_client,
            )
            answer_dispatcher.dispatch(question)
            store.mark_input_emitted(question.question_id, now=checked_at)
            dispatched += 1
        except (AnswerDispatchError, UnsupportedPlatformError) as exc:
            store.mark_question_error(
                question.question_id,
                status="dispatch_failed",
                error=str(exc),
                allowed_statuses=("answered",),
                now=checked_at,
            )
            dispatch_failed += 1

    if last_message_id is not None and last_message_id != cursor:
        store.set_observer_state(cursor_key, last_message_id, now=checked_at)
    return ReplyObserverResult(
        fetched=len(messages),
        accepted=accepted,
        dispatched=dispatched,
        dispatch_failed=dispatch_failed,
        guided=guided,
        guidance_failed=guidance_failed,
    )


def retry_gui_dispatch(
    *,
    config: AppConfig,
    store: PresenceStore,
    question_id: str,
    dispatcher: GuiAnswerDispatcher | None = None,
    now: float | None = None,
) -> RemoteQuestion:
    if not config.gui_answer_enabled:
        raise RemoteQuestionError(
            "Entrega GUI desativada. Defina PRESENCE_GUI_ANSWER_ENABLED=true."
        )
    question = store.require_question(question_id)
    if question.status not in {"answered", "dispatch_failed"}:
        raise RemoteQuestionError(
            f"A pergunta esta em estado {question.status!r}, sem resposta pronta para entrega."
        )
    try:
        actor = dispatcher or get_platform_factory(
            experimental_windows_enabled=config.experimental_windows_enabled,
        ).create_gui_dispatcher(
            x_ratio=config.codex_gui_click_x_ratio,
            y_ratio=config.codex_gui_click_y_ratio,
        )
        actor.dispatch(question)
    except (GuiDispatchError, UnsupportedPlatformError) as exc:
        if question.status == "answered":
            store.mark_question_error(
                question.question_id,
                status="dispatch_failed",
                error=str(exc),
                allowed_statuses=("answered",),
                now=now,
            )
        raise RemoteQuestionError(str(exc)) from exc
    return store.mark_input_emitted(
        question.question_id,
        now=now,
        allow_retry=question.status == "dispatch_failed",
    )


def retry_answer_dispatch(
    *,
    config: AppConfig,
    store: PresenceStore,
    question_id: str,
    dispatcher: GuiAnswerDispatcher | None = None,
    native_client: CodexQueueClient | None = None,
    controls: ControlSettings | None = None,
    now: float | None = None,
) -> RemoteQuestion:
    question = store.require_question(question_id)
    if question.status not in {"answered", "dispatch_failed"}:
        raise RemoteQuestionError(
            f"A pergunta esta em estado {question.status!r}, sem resposta pronta para entrega."
        )
    try:
        transport = _stored_question_transport(question)
    except AnswerDispatchError as exc:
        if question.status == "answered":
            store.mark_question_error(
                question.question_id,
                status="dispatch_failed",
                error=str(exc),
                allowed_statuses=("answered",),
                now=now,
            )
        raise RemoteQuestionError(str(exc)) from exc
    if transport == "store":
        raise RemoteQuestionError(
            "A pergunta esta em modo store e nao possui transporte de entrega."
        )
    try:
        actor, _ = _build_answer_dispatcher(
            config=config,
            transport=transport,
            controls=controls or ControlSettings.from_config(config),
            gui_dispatcher=dispatcher,
            native_client=native_client,
        )
        actor.dispatch(question)
    except (AnswerDispatchError, UnsupportedPlatformError) as exc:
        if question.status == "answered":
            store.mark_question_error(
                question.question_id,
                status="dispatch_failed",
                error=str(exc),
                allowed_statuses=("answered",),
                now=now,
            )
        raise RemoteQuestionError(str(exc)) from exc
    return store.mark_input_emitted(
        question.question_id,
        now=now,
        allow_retry=question.status == "dispatch_failed",
    )


def _build_answer_dispatcher(
    *,
    config: AppConfig,
    transport: AnswerTransport,
    controls: ControlSettings,
    gui_dispatcher: GuiAnswerDispatcher | None,
    native_client: CodexQueueClient | None,
) -> tuple[AnswerDispatcher, GuiAnswerDispatcher | None]:
    if transport == "native":
        return (
            NativeCodexAnswerDispatcher(
                controls=controls,
                client=native_client,
            ),
            gui_dispatcher,
        )
    if transport != "gui":
        raise AnswerDispatchError(f"Transporte sem dispatcher: {transport!r}.")
    actor = gui_dispatcher
    if actor is None:
        actor = get_platform_factory(
            experimental_windows_enabled=config.experimental_windows_enabled,
        ).create_gui_dispatcher(
            x_ratio=config.codex_gui_click_x_ratio,
            y_ratio=config.codex_gui_click_y_ratio,
        )
    return (
        GuiQuestionAnswerDispatcher(controls=controls, dispatcher=actor),
        actor,
    )


def _stored_question_transport(question: RemoteQuestion) -> AnswerTransport:
    if question.answer_transport in ANSWER_TRANSPORTS:
        return cast(AnswerTransport, question.answer_transport)
    if question.answer_transport is not None:
        raise AnswerDispatchError(
            f"Transporte salvo invalido: {question.answer_transport!r}."
        )
    if question.target_session_id:
        return "native"
    if question.target_window_id or question.target_window_pattern:
        return "gui"
    return "store"


def _resolve_question_session(
    *,
    config: AppConfig,
    store: PresenceStore,
    worker_id: str,
    explicit_thread: str | None,
    configured_thread: str | None,
    now: float | None,
) -> str:
    if explicit_thread:
        return _single_line_target(explicit_thread)

    environment_targets = {
        value.strip()
        for name in ("CODEX_SESSION_ID", "CODEX_THREAD_ID")
        if (value := os.environ.get(name)) and value.strip()
    }
    if len(environment_targets) > 1:
        raise RemoteQuestionError(
            "As variaveis CODEX_SESSION_ID e CODEX_THREAD_ID apontam para sessoes diferentes."
        )
    if environment_targets:
        return _single_line_target(next(iter(environment_targets)))
    if configured_thread:
        return _single_line_target(configured_thread)

    if config.question_session_max_age_seconds <= 0:
        raise RemoteQuestionError(
            "PRESENCE_QUESTION_SESSION_MAX_AGE_SECONDS precisa ser maior que zero."
        )
    checked_at = time.time() if now is None else now
    sessions = [
        item
        for item in store.list_codex_sessions(worker_id=worker_id, limit=20)
        if item.observed_at >= checked_at - config.question_session_max_age_seconds
    ]
    if not sessions:
        raise RemoteQuestionError(
            "Nenhuma sessao Codex recente foi encontrada para o worker; informe --thread."
        )
    if len(sessions) > 1:
        raise RemoteQuestionError(
            "Mais de uma sessao Codex recente foi encontrada para o worker; informe --thread."
        )
    return sessions[0].session_id


def _single_line_target(value: str) -> str:
    clean = value.strip()
    if not clean or any(character in clean for character in ("\r", "\n", "\x00")):
        raise RemoteQuestionError("A sessao Codex precisa ter uma unica linha nao vazia.")
    return clean


def _allowed_human_message(
    message: dict[str, Any],
    config: AppConfig,
) -> tuple[str | None, str, str] | None:
    if _snowflake(message.get("channel_id")) != config.discord_question_channel_id:
        return None
    author = message.get("author")
    if (
        not isinstance(author, dict)
        or author.get("bot") is True
        or message.get("webhook_id") is not None
    ):
        return None
    author_id = _snowflake(author.get("id"))
    if author_id is None or author_id not in config.discord_allowed_user_ids:
        return None
    reference = message.get("message_reference")
    referenced_message_id = (
        _snowflake(reference.get("message_id"))
        if isinstance(reference, dict)
        else None
    )
    content = message.get("content")
    clean_content = content.strip() if isinstance(content, str) else ""
    return referenced_message_id, author_id, clean_content


def _reply_guidance_reasons(
    *,
    referenced_message_id: str | None,
    content: str,
    pending_message_ids: set[str],
) -> tuple[ReplyGuidanceReason, ...]:
    reasons: list[ReplyGuidanceReason] = []
    if referenced_message_id is None:
        reasons.append("missing_reference")
    elif referenced_message_id not in pending_message_ids:
        reasons.append("unmatched_reference")
    if not content:
        reasons.append("empty_content")
    return tuple(reasons)


def _snowflake(value: object) -> str | None:
    return value if isinstance(value, str) and value.isdigit() else None


def _max_snowflake(first: str | None, second: str) -> str:
    if first is None:
        return second
    return second if int(second) > int(first) else first
