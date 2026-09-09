from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .config import AppConfig
from .discord_questions import (
    DiscordQuestionClient,
    DiscordQuestionError,
    ReplyGuidanceReason,
)
from .gui_answer import GuiAnswerDispatcher, GuiDispatchError, WindowTarget
from .platform_integration import UnsupportedPlatformError, get_platform_factory
from .store import PresenceStore, RemoteQuestion

CURSOR_KEY_PREFIX = "discord-question-channel:"


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
        actor = dispatcher or get_platform_factory().create_gui_dispatcher(
            x_ratio=config.codex_gui_click_x_ratio,
            y_ratio=config.codex_gui_click_y_ratio,
        )
        return actor.capture_target(title_pattern=pattern, window_id=window_id)
    except (GuiDispatchError, UnsupportedPlatformError) as exc:
        raise RemoteQuestionError(str(exc)) from exc


def ask_remote_question(
    *,
    config: AppConfig,
    store: PresenceStore,
    worker_id: str,
    prompt: str,
    timeout_seconds: int | None = None,
    window_id: str | None = None,
    title_pattern: str | None = None,
    client: DiscordQuestionClient | None = None,
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

    target = capture_gui_target(
        config,
        window_id=window_id,
        title_pattern=title_pattern,
        dispatcher=dispatcher,
    )
    question = store.create_question(
        worker_id=worker_id,
        prompt=clean_prompt,
        timeout_seconds=timeout,
        target_window_id=target.window_id if target else None,
        target_window_title=target.title if target else None,
        target_window_pattern=target.pattern if target else None,
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
    actor = dispatcher
    if config.gui_answer_enabled and actor is None:
        try:
            actor = get_platform_factory().create_gui_dispatcher(
                x_ratio=config.codex_gui_click_x_ratio,
                y_ratio=config.codex_gui_click_y_ratio,
            )
        except UnsupportedPlatformError as exc:
            raise RemoteQuestionError(str(exc)) from exc

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

        if not config.gui_answer_enabled:
            continue
        assert actor is not None
        try:
            actor.dispatch(question)
            store.mark_input_emitted(question.question_id, now=checked_at)
            dispatched += 1
        except GuiDispatchError as exc:
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
        actor = dispatcher or get_platform_factory().create_gui_dispatcher(
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
