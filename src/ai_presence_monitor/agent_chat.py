from __future__ import annotations

from dataclasses import dataclass

from .codex_input import CodexInputError, CodexQueueClient, send_native_message
from .control import ControlSettings
from .discord_questions import DiscordQuestionClient, DiscordQuestionError
from .store import AgentConversation, AgentMessage, PresenceStore

MAX_CHAT_CONTENT_LENGTH = 16_000
MAX_CHAT_TITLE_LENGTH = 200
MAX_CHAT_AGENT_LENGTH = 200
MAX_CHAT_SESSION_LENGTH = 512
CHAT_ROLES = frozenset({"human", "agent", "system"})
CHAT_DIRECTIONS = frozenset({"to_agent", "from_agent", "local"})
CHAT_TRANSPORTS = frozenset({"native", "discord", "local"})
CHAT_STATES = frozenset(
    {
        "queued",
        "dispatch_started",
        "input_emitted",
        "delivery_confirmed",
        "received",
        "published",
        "failed",
        "expired",
    }
)


class AgentChatError(RuntimeError):
    pass


class AgentChatPartialDeliveryError(AgentChatError):
    pass


@dataclass(frozen=True)
class ChatDispatchResult:
    conversation: AgentConversation
    message: AgentMessage


def ensure_conversation(
    store: PresenceStore,
    *,
    worker_id: str,
    agent_name: str,
    session_id: str,
    title: str | None = None,
) -> AgentConversation:
    return store.get_or_create_conversation(
        worker_id=_required_line(worker_id, "worker", 512),
        agent_name=_required_line(agent_name, "agent", MAX_CHAT_AGENT_LENGTH),
        session_id=_required_line(session_id, "session", MAX_CHAT_SESSION_LENGTH),
        title=_optional_line(title, "title", MAX_CHAT_TITLE_LENGTH),
    )


def publish_agent_message(
    store: PresenceStore,
    *,
    worker_id: str,
    agent_name: str,
    session_id: str,
    content: str,
    correlation_kind: str | None = None,
    correlation_id: str | None = None,
    discord_client: DiscordQuestionClient | None = None,
) -> ChatDispatchResult:
    conversation = ensure_conversation(
        store,
        worker_id=worker_id,
        agent_name=agent_name,
        session_id=session_id,
    )
    message = append_message(
        store,
        conversation_id=conversation.conversation_id,
        role="agent",
        direction="from_agent",
        transport="local",
        content=content,
        state="published",
        correlation_kind=correlation_kind,
        correlation_id=correlation_id,
    )
    if discord_client is not None:
        message = _mirror_to_discord(
            store,
            message=message,
            worker_id=worker_id,
            agent_name=agent_name,
            client=discord_client,
        )
    return ChatDispatchResult(conversation, message)


def send_human_message(
    store: PresenceStore,
    *,
    settings: ControlSettings,
    worker_id: str,
    agent_name: str,
    session_id: str,
    content: str,
    destination: str = "local",
    client: CodexQueueClient | None = None,
    discord_client: DiscordQuestionClient | None = None,
) -> ChatDispatchResult:
    conversation = ensure_conversation(
        store,
        worker_id=worker_id,
        agent_name=agent_name,
        session_id=session_id,
    )
    transport = "native"
    message = append_message(
        store,
        conversation_id=conversation.conversation_id,
        role="human",
        direction="to_agent",
        transport=transport,
        content=content,
        state="queued",
    )
    try:
        result = send_native_message(
            settings=settings,
            message=message.content,
            destination=destination,
            thread_id=session_id,
            client=client,
            detached=True,
        )
    except CodexInputError:
        store.update_agent_message_state(
            message.message_id,
            state="failed",
            error_code="transport_error",
        )
        raise AgentChatError("A mensagem foi persistida, mas o transporte falhou.")
    updated = store.update_agent_message_state(
        message.message_id,
        state=result.state,
    )
    if discord_client is not None:
        try:
            updated = _mirror_to_discord(
                store,
                message=updated,
                worker_id=worker_id,
                agent_name=agent_name,
                client=discord_client,
            )
        except AgentChatError as exc:
            raise AgentChatPartialDeliveryError(
                "A entrega ao Codex foi iniciada, mas o espelhamento no Discord "
                "falhou ou ficou incerto. Nao repita automaticamente."
            ) from exc
    return ChatDispatchResult(conversation, updated)


def project_remote_questions(
    store: PresenceStore,
    *,
    worker_id: str,
    agent_name: str,
    limit: int = 200,
) -> int:
    projected = 0
    for question in reversed(store.list_questions(worker_id=worker_id, limit=limit)):
        if question.target_session_id is None:
            continue
        conversation = ensure_conversation(
            store,
            worker_id=worker_id,
            agent_name=agent_name,
            session_id=question.target_session_id,
        )
        question_state = (
            "failed"
            if question.status in {"publish_failed", "dispatch_failed"}
            else "expired"
            if question.status == "expired"
            else "published"
        )
        question_message = append_message(
            store,
            conversation_id=conversation.conversation_id,
            role="agent",
            direction="from_agent",
            transport="discord",
            content=question.prompt,
            state=question_state,
            correlation_kind="remote_question",
            correlation_id=question.question_id,
            error_code="remote_question_error" if question_state == "failed" else None,
            created_at=question.created_at,
        )
        if question_message.state != question_state:
            store.update_agent_message_state(
                question_message.message_id,
                state=question_state,
                error_code=(
                    "remote_question_error" if question_state == "failed" else None
                ),
            )
        if question_message.discord_state is None:
            question_message = store.update_agent_message_discord(
                question_message.message_id,
                state="failed" if question_state == "failed" else "published",
                channel_id=question.channel_id,
                external_message_id=question.external_message_id,
                error_code=(
                    "remote_question_error" if question_state == "failed" else None
                ),
                now=question.updated_at,
            )
        projected += 1
        if question.answer is None:
            continue
        answer_state = {
            "delivery_confirmed": "delivery_confirmed",
            "input_emitted": "input_emitted",
            "dispatch_failed": "failed",
        }.get(question.status, "received")
        answer_message = append_message(
            store,
            conversation_id=conversation.conversation_id,
            role="human",
            direction="to_agent",
            transport="discord",
            content=question.answer,
            state=answer_state,
            correlation_kind="remote_answer",
            correlation_id=question.question_id,
            error_code="remote_dispatch_error" if answer_state == "failed" else None,
            created_at=question.answered_at or question.updated_at,
        )
        if answer_message.state != answer_state:
            store.update_agent_message_state(
                answer_message.message_id,
                state=answer_state,
                error_code="remote_dispatch_error"
                if answer_state == "failed"
                else None,
            )
        if answer_message.discord_state is None:
            store.update_agent_message_discord(
                answer_message.message_id,
                state="received",
                channel_id=question.channel_id,
                external_message_id=question.reply_message_id,
                now=question.answered_at or question.updated_at,
            )
        projected += 1
    return projected


def _mirror_to_discord(
    store: PresenceStore,
    *,
    message: AgentMessage,
    worker_id: str,
    agent_name: str,
    client: DiscordQuestionClient,
) -> AgentMessage:
    if message.discord_state in {"published", "received", "uncertain"}:
        return message
    pending = store.update_agent_message_discord(
        message.message_id,
        state="pending",
    )
    try:
        posted = client.post_chat_message(
            message_id=message.message_id,
            worker_id=worker_id,
            agent_name=agent_name,
            role="agent" if message.role == "agent" else "human",
            content=message.content,
        )
    except DiscordQuestionError as exc:
        state = "uncertain" if exc.retryable else "failed"
        error_code = (
            "discord_delivery_uncertain"
            if exc.retryable
            else "discord_delivery_rejected"
        )
        store.update_agent_message_discord(
            pending.message_id,
            state=state,
            error_code=error_code,
        )
        raise AgentChatError(
            "O espelhamento Discord falhou ou ficou incerto; o envio nao sera "
            "repetido automaticamente."
        ) from exc
    return store.update_agent_message_discord(
        pending.message_id,
        state="published",
        channel_id=posted.channel_id,
        external_message_id=posted.message_id,
    )


def append_message(
    store: PresenceStore,
    *,
    conversation_id: str,
    role: str,
    direction: str,
    transport: str,
    content: str,
    state: str,
    correlation_kind: str | None = None,
    correlation_id: str | None = None,
    error_code: str | None = None,
    created_at: float | None = None,
) -> AgentMessage:
    clean_role = _choice(role, "role", CHAT_ROLES)
    clean_direction = _choice(direction, "direction", CHAT_DIRECTIONS)
    clean_transport = _choice(transport, "transport", CHAT_TRANSPORTS)
    clean_state = _choice(state, "state", CHAT_STATES)
    clean_content = _required_text(content, "content", MAX_CHAT_CONTENT_LENGTH)
    clean_kind = _optional_line(correlation_kind, "correlation kind", 100)
    clean_id = _optional_line(correlation_id, "correlation ID", 512)
    if (clean_kind is None) != (clean_id is None):
        raise AgentChatError(
            "Correlation kind and correlation ID must be provided together."
        )
    return store.append_agent_message(
        conversation_id=_required_line(conversation_id, "conversation", 64),
        role=clean_role,
        direction=clean_direction,
        transport=clean_transport,
        content=clean_content,
        state=clean_state,
        correlation_kind=clean_kind,
        correlation_id=clean_id,
        error_code=_optional_line(error_code, "error code", 100),
        now=created_at,
    )


def _choice(value: str, label: str, choices: frozenset[str]) -> str:
    clean = value.strip()
    if clean not in choices:
        raise AgentChatError(f"Invalid chat {label}: {value!r}.")
    return clean


def _required_line(value: str, label: str, maximum: int) -> str:
    clean = value.strip()
    if not clean:
        raise AgentChatError(f"Chat {label} cannot be empty.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise AgentChatError(f"Chat {label} must use one line.")
    if len(clean) > maximum:
        raise AgentChatError(f"Chat {label} exceeds {maximum} characters.")
    return clean


def _required_text(value: str, label: str, maximum: int) -> str:
    clean = value.strip()
    if not clean:
        raise AgentChatError(f"Chat {label} cannot be empty.")
    if "\x00" in clean:
        raise AgentChatError(f"Chat {label} contains an invalid character.")
    if len(clean) > maximum:
        raise AgentChatError(f"Chat {label} exceeds {maximum} characters.")
    return clean


def _optional_line(value: str | None, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    return _required_line(clean, label, maximum)
