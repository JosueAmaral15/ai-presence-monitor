from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .codex_input import CodexInputError, CodexQueueClient
from .control import ControlSettings
from .gui_answer import GuiAnswerDispatcher, GuiDispatchError
from .store import RemoteQuestion

AnswerTransport = Literal["native", "gui", "store"]
AnswerDispatchState = Literal["input_emitted"]


class AnswerDispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnswerDispatchResult:
    transport: AnswerTransport
    state: AnswerDispatchState


class AnswerDispatcher(Protocol):
    def dispatch(self, question: RemoteQuestion) -> AnswerDispatchResult: ...


class NativeCodexAnswerDispatcher:
    def __init__(
        self,
        *,
        controls: ControlSettings,
        client: CodexQueueClient | None = None,
    ):
        self.controls = controls
        self.client = client or CodexQueueClient()

    def dispatch(self, question: RemoteQuestion) -> AnswerDispatchResult:
        if not self.controls.native_input_enabled:
            raise AnswerDispatchError("O transporte nativo esta desativado.")
        if not question.answer:
            raise AnswerDispatchError("A pergunta nao possui resposta para entregar.")
        if not question.target_session_id:
            raise AnswerDispatchError("A pergunta nao possui uma sessao Codex vinculada.")

        destination = question.target_destination or "local"
        remote = None
        auth_env = None
        if destination == "client":
            if not self.controls.remote_input_enabled:
                raise AnswerDispatchError(
                    "A entrada em computador cliente esta desativada."
                )
            remote = question.target_remote
            auth_env = question.target_remote_auth_token_env
            if not remote or not auth_env:
                raise AnswerDispatchError(
                    "A pergunta nao possui um destino remoto autenticado completo."
                )
        elif destination != "local":
            raise AnswerDispatchError(
                f"Destino da resposta desconhecido: {destination!r}."
            )

        try:
            result = self.client.send(
                thread_id=question.target_session_id,
                text=question.answer,
                remote=remote,
                remote_auth_token_env=auth_env,
                detached=False,
            )
        except CodexInputError as exc:
            raise AnswerDispatchError(str(exc)) from exc
        if result.state != "input_emitted":
            raise AnswerDispatchError(
                "O despacho nativo ficou pendente; o resultado e incerto e nao sera repetido."
            )
        return AnswerDispatchResult(transport="native", state="input_emitted")


class GuiQuestionAnswerDispatcher:
    def __init__(
        self,
        *,
        controls: ControlSettings,
        dispatcher: GuiAnswerDispatcher,
    ):
        self.controls = controls
        self.dispatcher = dispatcher

    def dispatch(self, question: RemoteQuestion) -> AnswerDispatchResult:
        if not self.controls.gui_fallback_enabled:
            raise AnswerDispatchError("O fallback GUI esta desativado.")
        try:
            self.dispatcher.dispatch(question)
        except GuiDispatchError as exc:
            raise AnswerDispatchError(str(exc)) from exc
        return AnswerDispatchResult(transport="gui", state="input_emitted")
