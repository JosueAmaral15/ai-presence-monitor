from __future__ import annotations

import ctypes
import re
import sys
import time
from ctypes import wintypes
from typing import Any, Protocol

from .gui_answer import GuiDispatchError, WindowTarget
from .store import RemoteQuestion

SW_RESTORE = 9
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class Win32GuiApi(Protocol):
    def list_visible_windows(self) -> list[tuple[int, str]]: ...

    def window_title(self, window_id: int) -> str | None: ...

    def window_rect(self, window_id: int) -> tuple[int, int, int, int] | None: ...

    def activate(self, window_id: int) -> bool: ...

    def click(self, x: int, y: int) -> None: ...

    def type_text_and_enter(self, text: str) -> None: ...


class _KeyboardInput(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class _MouseInput(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class _HardwareInput(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _InputUnion(ctypes.Union):
    _fields_ = (
        ("mi", _MouseInput),
        ("ki", _KeyboardInput),
        ("hi", _HardwareInput),
    )


class _Input(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = (("type", wintypes.DWORD), ("union", _InputUnion))


class CtypesWin32GuiApi:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise GuiDispatchError("A automacao Win32 requer Windows.")
        win_dll = getattr(ctypes, "WinDLL")
        self._user32: Any = win_dll("user32", use_last_error=True)
        self._configure_signatures()

    def list_visible_windows(self) -> list[tuple[int, str]]:
        windows: list[tuple[int, str]] = []
        callback_type = getattr(ctypes, "WINFUNCTYPE")(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        @callback_type
        def callback(hwnd: int, _: int) -> bool:
            if self._user32.IsWindowVisible(hwnd):
                title = self.window_title(hwnd)
                if title:
                    windows.append((int(hwnd), title))
            return True

        if not self._user32.EnumWindows(callback, 0):
            raise GuiDispatchError(
                f"Falha ao enumerar janelas: erro Win32 {_last_error()}."
            )
        return windows

    def window_title(self, window_id: int) -> str | None:
        if not self._user32.IsWindow(window_id) or not self._user32.IsWindowVisible(window_id):
            return None
        length = self._user32.GetWindowTextLengthW(window_id)
        if length <= 0:
            return None
        buffer = ctypes.create_unicode_buffer(length + 1)
        copied = self._user32.GetWindowTextW(window_id, buffer, len(buffer))
        return buffer.value if copied else None

    def window_rect(self, window_id: int) -> tuple[int, int, int, int] | None:
        rect = wintypes.RECT()
        if not self._user32.GetWindowRect(window_id, ctypes.byref(rect)):
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def activate(self, window_id: int) -> bool:
        self._user32.ShowWindow(window_id, SW_RESTORE)
        self._user32.SetForegroundWindow(window_id)
        for _ in range(20):
            if int(self._user32.GetForegroundWindow()) == window_id:
                return True
            time.sleep(0.01)
        return False

    def click(self, x: int, y: int) -> None:
        if not self._user32.SetCursorPos(x, y):
            raise GuiDispatchError(
                f"Falha ao posicionar o cursor: erro Win32 {_last_error()}."
            )
        self._user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self._user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def type_text_and_enter(self, text: str) -> None:
        units = text.encode("utf-16-le")
        inputs: list[_Input] = []
        for index in range(0, len(units), 2):
            scan = int.from_bytes(units[index : index + 2], "little")
            inputs.append(self._keyboard_input(0, scan, KEYEVENTF_UNICODE))
            inputs.append(
                self._keyboard_input(0, scan, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
            )
        inputs.append(self._keyboard_input(VK_RETURN, 0, 0))
        inputs.append(self._keyboard_input(VK_RETURN, 0, KEYEVENTF_KEYUP))
        if not inputs:
            return
        array_type = _Input * len(inputs)
        array = array_type(*inputs)
        sent = self._user32.SendInput(len(array), array, ctypes.sizeof(_Input))
        if sent != len(array):
            raise GuiDispatchError(
                f"Falha ao digitar texto: erro Win32 {_last_error()}."
            )

    @staticmethod
    def _keyboard_input(vk: int, scan: int, flags: int) -> _Input:
        return _Input(
            type=INPUT_KEYBOARD,
            union=_InputUnion(
                ki=_KeyboardInput(
                    wVk=vk,
                    wScan=scan,
                    dwFlags=flags,
                    time=0,
                    dwExtraInfo=0,
                )
            ),
        )

    def _configure_signatures(self) -> None:
        self._user32.IsWindow.argtypes = [wintypes.HWND]
        self._user32.IsWindow.restype = wintypes.BOOL
        self._user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self._user32.IsWindowVisible.restype = wintypes.BOOL
        self._user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self._user32.GetWindowTextLengthW.restype = ctypes.c_int
        self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetWindowTextW.restype = ctypes.c_int
        self._user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self._user32.GetWindowRect.restype = wintypes.BOOL
        self._user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self._user32.SetForegroundWindow.restype = wintypes.BOOL
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.ShowWindow.restype = wintypes.BOOL
        self._user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self._user32.SetCursorPos.restype = wintypes.BOOL
        self._user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int]
        self._user32.SendInput.restype = wintypes.UINT


class Win32GuiAnswerDispatcher:
    def __init__(
        self,
        *,
        x_ratio: float,
        y_ratio: float,
        api: Win32GuiApi | None = None,
    ) -> None:
        if not 0 <= x_ratio <= 1:
            raise GuiDispatchError("A proporcao horizontal precisa estar entre 0 e 1.")
        if not 0 <= y_ratio <= 1:
            raise GuiDispatchError("A proporcao vertical precisa estar entre 0 e 1.")
        self.x_ratio = x_ratio
        self.y_ratio = y_ratio
        self._api = api or CtypesWin32GuiApi()

    def capture_target(
        self,
        *,
        title_pattern: str,
        window_id: str | None = None,
    ) -> WindowTarget:
        try:
            compiled = re.compile(title_pattern)
        except re.error as exc:
            raise GuiDispatchError(f"Padrao de titulo invalido: {exc}.") from exc
        exact_id = self._validate_window_id(window_id) if window_id else None
        matches = [
            WindowTarget(str(candidate), title, title_pattern)
            for candidate, title in self._api.list_visible_windows()
            if (exact_id is None or candidate == exact_id) and compiled.search(title)
        ]
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
            raise GuiDispatchError("A pergunta nao possui uma janela vinculada.")
        self.dispatch_text(
            target=WindowTarget(
                question.target_window_id,
                question.target_window_title or "",
                question.target_window_pattern,
            ),
            text=question.answer,
        )

    def dispatch_text(
        self,
        *,
        target: WindowTarget,
        text: str,
        allow_title_change: bool = False,
    ) -> None:
        if not text:
            raise GuiDispatchError("O texto para entrega nao pode ficar vazio.")
        validated = self.capture_target(
            title_pattern=target.pattern,
            window_id=target.window_id,
        )
        if not allow_title_change and target.title and validated.title != target.title:
            raise GuiDispatchError(
                "O titulo da janela alvo mudou desde a captura inicial."
            )
        window_id = int(validated.window_id)
        rect = self._api.window_rect(window_id)
        if rect is None:
            raise GuiDispatchError(f"Geometria invalida para a janela {window_id}.")
        left, top, right, bottom = rect
        if right <= left or bottom <= top:
            raise GuiDispatchError(f"Geometria invalida para a janela {window_id}.")
        if not self._api.activate(window_id):
            raise GuiDispatchError(
                "O Windows nao permitiu ativar a janela alvo; nenhuma entrada foi enviada."
            )
        click_x = left + round((right - left) * self.x_ratio)
        click_y = top + round((bottom - top) * self.y_ratio)
        self._api.click(click_x, click_y)
        self._api.type_text_and_enter(text)

    @staticmethod
    def _validate_window_id(window_id: str) -> int:
        if not window_id.isdigit() or int(window_id) <= 0:
            raise GuiDispatchError("O ID da janela Win32 precisa ser um inteiro positivo.")
        return int(window_id)


def _last_error() -> int:
    getter = getattr(ctypes, "get_last_error", None)
    return int(getter()) if getter else 0
