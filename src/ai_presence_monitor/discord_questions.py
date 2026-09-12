from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

from . import __version__

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordQuestionError(RuntimeError):
    pass


ReplyGuidanceReason = Literal[
    "missing_reference",
    "unmatched_reference",
    "empty_content",
]


@dataclass(frozen=True)
class PostedDiscordQuestion:
    message_id: str
    channel_id: str


def _require_snowflake(value: str | None, label: str) -> str:
    if not value or not value.isdigit():
        raise DiscordQuestionError(f"{label} precisa ser um ID numerico do Discord.")
    return value


def _webhook_wait_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["wait"] = "true"
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(query),
            parsed.fragment,
        )
    )


class DiscordQuestionClient:
    def __init__(
        self,
        *,
        webhook_url: str,
        bot_token: str,
        channel_id: str,
        timeout_seconds: int = 15,
    ):
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.channel_id = _require_snowflake(channel_id, "DISCORD_QUESTION_CHANNEL_ID")
        self.timeout_seconds = timeout_seconds

    def post_question(
        self,
        *,
        question_id: str,
        worker_id: str,
        prompt: str,
    ) -> PostedDiscordQuestion:
        content = (
            "**Pergunta do AI-worker**\n"
            f"ID: `{question_id}`\n"
            f"Worker: `{worker_id}`\n\n"
            f"{prompt}\n\n"
            "Use **Responder** nesta mensagem. Somente usuarios autorizados "
            "serao aceitos."
        )
        if len(content) > 2000:
            raise DiscordQuestionError(
                "A pergunta excede o limite de 2000 caracteres do Discord."
            )
        response = self._request_json(
            _webhook_wait_url(self.webhook_url),
            method="POST",
            payload={
                "content": content,
                "allowed_mentions": {"parse": []},
            },
            label="pergunta Discord",
        )
        if not isinstance(response, dict):
            raise DiscordQuestionError("Discord nao retornou os dados da pergunta.")
        message_id = _require_snowflake(
            _string_value(response.get("id")),
            "ID da mensagem publicada",
        )
        channel_id = _require_snowflake(
            _string_value(response.get("channel_id")),
            "ID do canal retornado",
        )
        if channel_id != self.channel_id:
            raise DiscordQuestionError(
                "O webhook publicou em canal diferente de DISCORD_QUESTION_CHANNEL_ID."
            )
        return PostedDiscordQuestion(message_id=message_id, channel_id=channel_id)

    def post_reply_guidance(
        self,
        *,
        author_id: str,
        pending_count: int,
        reasons: tuple[ReplyGuidanceReason, ...],
    ) -> None:
        allowed_author_id = _require_snowflake(author_id, "ID do usuario autorizado")
        if pending_count <= 0:
            raise DiscordQuestionError(
                "A orientacao exige ao menos uma pergunta pendente."
            )

        question_label = "pergunta ativa" if pending_count == 1 else "perguntas ativas"
        lines = [
            f"<@{allowed_author_id}> **Resposta nao associada.**",
            f"Ha {pending_count} {question_label} dentro do prazo.",
            "Selecione a mensagem **Pergunta do AI-worker**, use **Responder** "
            "e confirme que o Discord mostra a resposta vinculada.",
        ]
        if "missing_reference" in reasons:
            lines.append(
                "A mensagem recebida nao tinha referencia a pergunta escolhida."
            )
        if "unmatched_reference" in reasons:
            lines.append(
                "A mensagem selecionada nao corresponde a uma pergunta que ainda "
                "esteja pendente; responda diretamente a uma pergunta ativa."
            )
        if "empty_content" in reasons:
            lines.append(
                "O Discord entregou o texto vazio ao bot. Se voce enviou texto, "
                "habilite **Message Content Intent** no aplicativo do bot e tente "
                "novamente."
            )

        self._request_json(
            _webhook_wait_url(self.webhook_url),
            method="POST",
            payload={
                "content": "\n".join(lines),
                "allowed_mentions": {
                    "parse": [],
                    "users": [allowed_author_id],
                    "replied_user": False,
                },
            },
            label="orientacao de resposta Discord",
        )

    def fetch_messages(self, *, after: str | None = None) -> list[dict[str, Any]]:
        if after is not None:
            _require_snowflake(after, "Cursor do observer")

        first_query: dict[str, str | int] = {"limit": 100}
        if after:
            first_query["after"] = after
        first_page = self._fetch_message_page(first_query)
        collected = list(first_page)

        # Discord devolve mensagens da mais nova para a mais antiga. Se houver
        # uma pagina cheia depois do cursor, percorremos para tras para nao
        # saltar mensagens intermediarias.
        page = first_page
        for _ in range(9):
            page_ids = _message_ids(page)
            if after is None or len(page) < 100 or not page_ids:
                break
            boundary = min(page_ids, key=int)
            older_page = self._fetch_message_page(
                {"limit": 100, "before": boundary}
            )
            collected.extend(
                item
                for item in older_page
                if (
                    (message_id := _string_value(item.get("id")))
                    and message_id.isdigit()
                    and int(message_id) > int(after)
                )
            )
            older_ids = _message_ids(older_page)
            if (
                len(older_page) < 100
                or not older_ids
                or min(map(int, older_ids)) <= int(after)
            ):
                break
            page = older_page
        else:
            raise DiscordQuestionError(
                "Mais de 1000 mensagens aguardavam processamento; "
                "intervencao manual necessaria."
            )

        unique = {
            item["id"]: item
            for item in collected
            if isinstance(item.get("id"), str) and item["id"].isdigit()
        }
        return sorted(unique.values(), key=lambda item: int(item["id"]))

    def _fetch_message_page(
        self,
        query: dict[str, str | int],
    ) -> list[dict[str, Any]]:
        url = (
            f"{DISCORD_API_BASE}/channels/{self.channel_id}/messages?"
            + urllib.parse.urlencode(query)
        )
        response = self._request_json(
            url,
            method="GET",
            headers={"Authorization": f"Bot {self.bot_token}"},
            label="leitura de respostas Discord",
        )
        if not isinstance(response, list):
            raise DiscordQuestionError(
                "Discord retornou uma lista de mensagens invalida."
            )
        return [item for item in response if isinstance(item, dict)]

    def _request_json(
        self,
        url: str,
        *,
        method: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        label: str,
    ) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {
            "Accept": "application/json",
            "User-Agent": f"ai-presence-monitor/{__version__}",
        }
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            url,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise DiscordQuestionError(
                f"Falha HTTP em {label}: status {exc.code}."
            ) from exc
        except urllib.error.URLError as exc:
            raise DiscordQuestionError(f"Falha de rede em {label}: {exc.reason}.") from exc

        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DiscordQuestionError(f"Resposta JSON invalida em {label}.") from exc


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _message_ids(messages: list[dict[str, Any]]) -> list[str]:
    return [
        value
        for item in messages
        if (value := _string_value(item.get("id"))) and value.isdigit()
    ]
