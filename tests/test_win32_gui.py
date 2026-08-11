from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

import ai_presence_monitor.win32_gui as win32_gui
from ai_presence_monitor.gui_answer import GuiDispatchError
from ai_presence_monitor.win32_gui import CtypesWin32GuiApi, Win32GuiAnswerDispatcher


class FakeWin32GuiApi:
    def __init__(self) -> None:
        self.windows = [(10, "Codex - project"), (11, "Terminal")]
        self.rect = (100, 200, 1100, 1000)
        self.activation_allowed = True
        self.activated: list[int] = []
        self.clicks: list[tuple[int, int]] = []
        self.typed: list[str] = []

    def list_visible_windows(self) -> list[tuple[int, str]]:
        return self.windows

    def window_title(self, window_id: int) -> str | None:
        return dict(self.windows).get(window_id)

    def window_rect(self, window_id: int):
        return self.rect

    def activate(self, window_id: int) -> bool:
        self.activated.append(window_id)
        return self.activation_allowed

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def type_text_and_enter(self, text: str) -> None:
        self.typed.append(text)


class Win32GuiAnswerDispatcherTests(unittest.TestCase):
    def test_capture_requires_one_visible_matching_window(self) -> None:
        api = FakeWin32GuiApi()
        dispatcher = Win32GuiAnswerDispatcher(x_ratio=0.5, y_ratio=0.9, api=api)

        target = dispatcher.capture_target(title_pattern="Codex")
        self.assertEqual(target.window_id, "10")

        api.windows.append((12, "Codex - second"))
        with self.assertRaisesRegex(GuiDispatchError, "Mais de uma"):
            dispatcher.capture_target(title_pattern="Codex")
        with self.assertRaisesRegex(GuiDispatchError, "inteiro positivo"):
            dispatcher.capture_target(title_pattern="Codex", window_id="invalid")
        with self.assertRaisesRegex(GuiDispatchError, "Padrao de titulo"):
            dispatcher.capture_target(title_pattern="[")

    def test_dispatch_revalidates_and_types_unicode_without_clipboard(self) -> None:
        api = FakeWin32GuiApi()
        dispatcher = Win32GuiAnswerDispatcher(x_ratio=0.5, y_ratio=0.9, api=api)
        target = dispatcher.capture_target(title_pattern="Codex", window_id="10")

        dispatcher.dispatch_text(target=target, text="Continue: ação")

        self.assertEqual(api.activated, [10])
        self.assertEqual(api.clicks, [(600, 920)])
        self.assertEqual(api.typed, ["Continue: ação"])

    def test_title_change_and_foreground_failure_fail_closed(self) -> None:
        api = FakeWin32GuiApi()
        dispatcher = Win32GuiAnswerDispatcher(x_ratio=0.5, y_ratio=0.9, api=api)
        target = dispatcher.capture_target(title_pattern="Codex", window_id="10")

        api.windows[0] = (10, "Codex - changed")
        with self.assertRaisesRegex(GuiDispatchError, "titulo"):
            dispatcher.dispatch_text(target=target, text="continue")
        self.assertEqual(api.typed, [])

        api.activation_allowed = False
        with self.assertRaisesRegex(GuiDispatchError, "nao permitiu"):
            dispatcher.dispatch_text(
                target=target,
                text="continue",
                allow_title_change=True,
            )
        self.assertEqual(api.typed, [])

    def test_invalid_ratio_and_non_windows_api_are_rejected(self) -> None:
        api = FakeWin32GuiApi()
        with self.assertRaisesRegex(GuiDispatchError, "horizontal"):
            Win32GuiAnswerDispatcher(x_ratio=2, y_ratio=0.9, api=api)
        if sys.platform != "win32":
            with self.assertRaisesRegex(GuiDispatchError, "requer Windows"):
                CtypesWin32GuiApi()

    def test_native_api_enumerates_activates_clicks_and_types(self) -> None:
        user32 = MagicMock()
        user32.IsWindowVisible.return_value = True
        user32.IsWindow.return_value = True
        user32.GetWindowTextLengthW.return_value = 5
        user32.GetWindowTextW.side_effect = lambda hwnd, buffer, size: setattr(
            buffer,
            "value",
            "Codex",
        ) or 5
        user32.EnumWindows.side_effect = lambda callback, value: callback(10, value)

        def set_rect(hwnd, rect):
            rect._obj.left = 1
            rect._obj.top = 2
            rect._obj.right = 101
            rect._obj.bottom = 202
            return True

        user32.GetWindowRect.side_effect = set_rect
        user32.GetForegroundWindow.return_value = 10
        user32.SetCursorPos.return_value = True
        user32.SendInput.side_effect = lambda count, array, size: count

        with patch.object(win32_gui.sys, "platform", "win32"), patch.object(
            win32_gui.ctypes,
            "WinDLL",
            return_value=user32,
            create=True,
        ), patch.object(
            win32_gui.ctypes,
            "WINFUNCTYPE",
            win32_gui.ctypes.CFUNCTYPE,
            create=True,
        ):
            api = CtypesWin32GuiApi()
            self.assertEqual(api.list_visible_windows(), [(10, "Codex")])
            self.assertEqual(api.window_rect(10), (1, 2, 101, 202))
            self.assertTrue(api.activate(10))
            api.click(50, 100)
            api.type_text_and_enter("ação")

        user32.SetCursorPos.assert_called_once_with(50, 100)
        self.assertGreater(user32.SendInput.call_args.args[0], 2)


if __name__ == "__main__":
    unittest.main()
