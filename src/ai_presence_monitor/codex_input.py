from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from .control import ControlSettings


class CodexInputError(RuntimeError):
    pass


CodexInputState = Literal["dispatch_started", "input_emitted"]


@dataclass(frozen=True)
class CodexInputResult:
    thread_id: str
    remote: str | None
    state: CodexInputState
    process_id: int | None = None


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
ProcessLauncher = Callable[..., subprocess.Popen[str]]


def _default_runner(
    command: list[str],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, **kwargs)


def _default_launcher(
    command: list[str],
    **kwargs: Any,
) -> subprocess.Popen[str]:
    return subprocess.Popen(command, **kwargs)


class CodexQueueClient:
    def __init__(
        self,
        *,
        executable: str = "codex",
        timeout_seconds: int = 15,
        runner: ProcessRunner = _default_runner,
        launcher: ProcessLauncher = _default_launcher,
    ):
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.runner = runner
        self.launcher = launcher

    def is_available(self) -> bool:
        return self._resolve_executable() is not None

    def send(
        self,
        *,
        thread_id: str,
        text: str,
        remote: str | None = None,
        remote_auth_token_env: str | None = None,
        detached: bool = False,
    ) -> CodexInputResult:
        clean_thread = _single_line(thread_id, "thread ID")
        clean_text = text.strip()
        if not clean_text:
            raise CodexInputError("A mensagem para o Codex nao pode ficar vazia.")
        executable = self._resolve_executable()
        if executable is None:
            raise CodexInputError(
                f"Executavel Codex nao encontrado no PATH: {self.executable!r}."
            )

        clean_remote = _optional_single_line(remote, "endpoint remoto")
        clean_auth_env = _optional_single_line(
            remote_auth_token_env,
            "nome da variavel de token",
        )
        if clean_remote and not re.match(r"^(?:ws|wss|unix)://.+", clean_remote):
            raise CodexInputError(
                "Endpoint remoto invalido; use ws://, wss:// ou unix://."
            )
        if clean_remote and not clean_auth_env:
            raise CodexInputError(
                "Entrada remota exige o nome da variavel de ambiente do token."
            )
        if clean_auth_env and not clean_remote:
            raise CodexInputError(
                "A variavel de token remoto so pode ser usada com um endpoint remoto."
            )
        if clean_auth_env and not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*",
            clean_auth_env,
        ):
            raise CodexInputError("O nome da variavel de token remoto e invalido.")
        if clean_auth_env and not os.environ.get(clean_auth_env):
            raise CodexInputError(
                f"A variavel de ambiente {clean_auth_env!r} nao esta definida."
            )

        command = [
            executable,
            "queue",
            "--thread",
            clean_thread,
            "--message",
            clean_text,
        ]
        if clean_remote:
            command.extend(["--remote", clean_remote])
            assert clean_auth_env is not None
            command.extend(["--remote-auth-token-env", clean_auth_env])

        if detached:
            return self._launch_detached(
                command,
                thread_id=clean_thread,
                remote=clean_remote,
            )

        kwargs: dict[str, object] = {
            "capture_output": True,
            "text": True,
            "timeout": self.timeout_seconds,
            "check": False,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = self.runner(command, **kwargs)
        except subprocess.TimeoutExpired as exc:
            raise CodexInputError(
                "O envio nativo expirou; o resultado e incerto e nao sera repetido."
            ) from exc
        except OSError as exc:
            raise CodexInputError(f"Falha ao iniciar o Codex CLI: {exc}") from exc
        if completed.returncode != 0:
            detail = _command_error(
                completed.stderr or completed.stdout,
                message=clean_text,
            )
            raise CodexInputError(
                "O Codex CLI recusou o envio; o resultado e incerto e nao sera "
                f"repetido. {detail}"
            )
        return CodexInputResult(
            thread_id=clean_thread,
            remote=clean_remote,
            state="input_emitted",
        )

    def _launch_detached(
        self,
        command: list[str],
        *,
        thread_id: str,
        remote: str | None,
    ) -> CodexInputResult:
        kwargs: dict[str, object] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "text": True,
            "close_fds": True,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        else:
            kwargs["start_new_session"] = True
        try:
            process = self.launcher(command, **kwargs)
        except OSError as exc:
            raise CodexInputError(f"Falha ao iniciar o Codex CLI: {exc}") from exc
        return CodexInputResult(
            thread_id=thread_id,
            remote=remote,
            state="dispatch_started",
            process_id=process.pid,
        )

    def _resolve_executable(self) -> str | None:
        candidate = Path(self.executable).expanduser()
        if candidate.parent != Path("."):
            return str(candidate) if candidate.is_file() else None
        return shutil.which(self.executable)


def resolve_native_destination(
    *,
    settings: ControlSettings,
    destination: str,
    thread_id: str | None = None,
) -> tuple[str, str | None, str | None]:
    if not settings.native_input_enabled:
        raise CodexInputError("O transporte nativo esta desativado.")
    target_thread = (thread_id or settings.codex_thread_id or "").strip()
    if not target_thread:
        raise CodexInputError("Informe a sessao exata do Codex.")
    if destination == "local":
        return target_thread, None, None
    if destination != "remote":
        raise CodexInputError(f"Destino desconhecido: {destination!r}.")
    if not settings.remote_input_enabled:
        raise CodexInputError("A entrada em computador cliente esta desativada.")
    if not settings.codex_remote:
        raise CodexInputError("Configure o endpoint do computador cliente.")
    if not settings.remote_auth_token_env:
        raise CodexInputError(
            "Entrada remota exige o nome da variavel de ambiente do token."
        )
    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*",
        settings.remote_auth_token_env,
    ):
        raise CodexInputError("O nome da variavel de token remoto e invalido.")
    return (
        target_thread,
        settings.codex_remote,
        settings.remote_auth_token_env,
    )


def send_native_message(
    *,
    settings: ControlSettings,
    message: str,
    destination: str,
    thread_id: str | None = None,
    client: CodexQueueClient | None = None,
    detached: bool | None = None,
) -> CodexInputResult:
    target_thread, remote, auth_env = resolve_native_destination(
        settings=settings,
        destination=destination,
        thread_id=thread_id,
    )
    return (client or CodexQueueClient()).send(
        thread_id=target_thread,
        text=message,
        remote=remote,
        remote_auth_token_env=auth_env,
        detached=(
            is_current_codex_session(target_thread)
            if detached is None
            else detached
        ),
    )


def is_current_codex_session(thread_id: str) -> bool:
    clean_thread = thread_id.strip()
    if not clean_thread:
        return False
    return clean_thread in {
        value.strip()
        for name in ("CODEX_SESSION_ID", "CODEX_THREAD_ID")
        if (value := os.environ.get(name)) and value.strip()
    }


def _single_line(value: str, label: str) -> str:
    clean = value.strip()
    if not clean:
        raise CodexInputError(f"{label.capitalize()} nao pode ficar vazio.")
    if any(character in clean for character in ("\r", "\n", "\x00")):
        raise CodexInputError(f"{label.capitalize()} precisa ter uma unica linha.")
    return clean


def _optional_single_line(value: str | None, label: str) -> str | None:
    if value is None or not value.strip():
        return None
    return _single_line(value, label)


def _command_error(value: str | None, *, message: str) -> str:
    if not value:
        return "Sem detalhe adicional."
    clean = " ".join(value.replace(message, "<message>").split())
    return clean[:400]
