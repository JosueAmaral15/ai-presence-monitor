from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass

from .store import RemoteQuestion


class GuiDispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class WindowTarget:
    window_id: str
    title: str
    pattern: str


class X11GuiAnswerDispatcher:
    def __init__(self, *, x_ratio: float, y_ratio: float):
        if not 0 <= x_ratio <= 1:
            raise GuiDispatchError("A proporcao horizontal precisa estar entre 0 e 1.")
        if not 0 <= y_ratio <= 1:
            raise GuiDispatchError("A proporcao vertical precisa estar entre 0 e 1.")
        self.x_ratio = x_ratio
        self.y_ratio = y_ratio

    def capture_target(
        self,
        *,
        title_pattern: str,
        window_id: str | None = None,
    ) -> WindowTarget:
        self._require_tool("xdotool")
        try:
            compiled = re.compile(title_pattern)
        except re.error as exc:
            raise GuiDispatchError(f"Padrao de titulo invalido: {exc}.") from exc

        result = self._run(
            ["xdotool", "search", "--onlyvisible", "--name", title_pattern],
            check=False,
        )
        visible_candidates = list(
            dict.fromkeys(
                line.strip()
                for line in result.stdout.decode("utf-8", errors="replace").splitlines()
                if line.strip().isdigit()
            )
        )
        if window_id:
            exact_window_id = self._validate_window_id(window_id)
            candidates = (
                [exact_window_id]
                if exact_window_id in visible_candidates
                else []
            )
        else:
            candidates = visible_candidates

        matches: list[WindowTarget] = []
        for candidate in candidates:
            title = self._window_title(candidate)
            if compiled.search(title):
                matches.append(
                    WindowTarget(
                        window_id=candidate,
                        title=title,
                        pattern=title_pattern,
                    )
                )

        if not matches:
            raise GuiDispatchError("Nenhuma janela visivel corresponde ao titulo configurado.")
        if len(matches) != 1:
            ids = ", ".join(target.window_id for target in matches)
            raise GuiDispatchError(
                f"Mais de uma janela corresponde ao titulo configurado: {ids}."
            )
        return matches[0]

    def dispatch(self, question: RemoteQuestion) -> None:
        if not question.answer:
            raise GuiDispatchError("A pergunta nao possui resposta para entregar.")
        if not question.target_window_id or not question.target_window_pattern:
            raise GuiDispatchError("A pergunta nao possui uma janela X11 vinculada.")

        self.dispatch_text(
            target=WindowTarget(
                window_id=question.target_window_id,
                title=question.target_window_title or "",
                pattern=question.target_window_pattern,
            ),
            text=question.answer,
        )

    def dispatch_text(self, *, target: WindowTarget, text: str) -> None:
        if not text:
            raise GuiDispatchError("O texto para entrega nao pode ficar vazio.")
        self._require_tool("xdotool")
        self._require_tool("xclip")
        validated_target = self.capture_target(
            title_pattern=target.pattern,
            window_id=target.window_id,
        )
        if target.title and validated_target.title != target.title:
            raise GuiDispatchError(
                "O titulo da janela alvo mudou desde a publicacao da pergunta."
            )
        geometry = self._window_geometry(validated_target.window_id)
        click_x = round(geometry["WIDTH"] * self.x_ratio)
        click_y = round(geometry["HEIGHT"] * self.y_ratio)

        previous_clipboard = self._read_clipboard()
        try:
            self._write_clipboard(text.encode("utf-8"))
            self._run(
                ["xdotool", "windowactivate", "--sync", validated_target.window_id]
            )
            self._run(
                [
                    "xdotool",
                    "mousemove",
                    "--sync",
                    "--window",
                    validated_target.window_id,
                    str(click_x),
                    str(click_y),
                ]
            )
            self._run(
                ["xdotool", "click", "--window", validated_target.window_id, "1"]
            )
            self._run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
            self._run(["xdotool", "key", "--clearmodifiers", "Return"])
            time.sleep(0.1)
        finally:
            self._write_clipboard(previous_clipboard or b"")

    def _window_title(self, window_id: str) -> str:
        result = self._run(["xdotool", "getwindowname", window_id])
        title = result.stdout.decode("utf-8", errors="replace").strip()
        if not title:
            raise GuiDispatchError(f"A janela {window_id} nao possui titulo.")
        return title

    def _window_geometry(self, window_id: str) -> dict[str, int]:
        result = self._run(["xdotool", "getwindowgeometry", "--shell", window_id])
        geometry: dict[str, int] = {}
        for raw_line in result.stdout.decode("ascii", errors="ignore").splitlines():
            if "=" not in raw_line:
                continue
            key, value = raw_line.split("=", 1)
            if key in {"WIDTH", "HEIGHT"} and value.isdigit():
                geometry[key] = int(value)
        if geometry.get("WIDTH", 0) <= 0 or geometry.get("HEIGHT", 0) <= 0:
            raise GuiDispatchError(f"Geometria invalida para a janela {window_id}.")
        return geometry

    def _read_clipboard(self) -> bytes | None:
        result = self._run(
            ["xclip", "-selection", "clipboard", "-out"],
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    def _write_clipboard(self, value: bytes) -> None:
        self._run(
            ["xclip", "-selection", "clipboard", "-in"],
            input_data=value,
        )

    @staticmethod
    def _validate_window_id(window_id: str) -> str:
        if not window_id.isdigit():
            raise GuiDispatchError("O ID da janela X11 precisa ser numerico.")
        return window_id

    @staticmethod
    def _require_tool(name: str) -> None:
        if shutil.which(name) is None:
            raise GuiDispatchError(f"Ferramenta obrigatoria nao encontrada: {name}.")

    @staticmethod
    def _run(
        command: list[str],
        *,
        input_data: bytes | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            result = subprocess.run(
                command,
                input=input_data,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise GuiDispatchError(f"Falha ao executar {command[0]}: {exc}.") from exc
        if check and result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            raise GuiDispatchError(
                f"Comando {command[0]} falhou com codigo {result.returncode}{suffix}."
            )
        return result
