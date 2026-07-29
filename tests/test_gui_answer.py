from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_presence_monitor.gui_answer import GuiDispatchError, X11GuiAnswerDispatcher
from ai_presence_monitor.store import PresenceStore


def completed(
    command: list[str],
    *,
    stdout: bytes = b"",
    stderr: bytes = b"",
    returncode: int = 0,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


class X11GuiAnswerDispatcherTests(unittest.TestCase):
    def test_capture_requires_one_matching_visible_window(self) -> None:
        dispatcher = X11GuiAnswerDispatcher(x_ratio=0.5, y_ratio=0.9)

        def run(command: list[str], **_: object):
            if command[1] == "search":
                return completed(command, stdout=b"10\n11\n")
            title = b"Codex - project\n" if command[-1] == "10" else b"Terminal\n"
            return completed(command, stdout=title)

        with patch("ai_presence_monitor.gui_answer.shutil.which", return_value="/bin/tool"), patch(
            "ai_presence_monitor.gui_answer.subprocess.run",
            side_effect=run,
        ):
            target = dispatcher.capture_target(title_pattern="Codex")
            self.assertEqual(target.window_id, "10")

        with patch("ai_presence_monitor.gui_answer.shutil.which", return_value="/bin/tool"), patch(
            "ai_presence_monitor.gui_answer.subprocess.run",
            return_value=completed(["xdotool"], stdout=b"10\n11\n"),
        ):
            with self.assertRaisesRegex(GuiDispatchError, "Nenhuma janela"):
                dispatcher.capture_target(title_pattern="Codex")

    def test_dispatch_pastes_unicode_and_restores_clipboard_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PresenceStore(Path(tmp) / "presence.db")
            question = store.create_question(
                worker_id="worker",
                prompt="Pergunta",
                timeout_seconds=60,
                target_window_id="10",
                target_window_title="Codex - project",
                target_window_pattern="Codex",
                now=1000,
            )
            store.mark_question_published(
                question.question_id,
                channel_id="200",
                external_message_id="100",
                now=1000,
            )
            answered = store.record_question_answer(
                external_message_id="100",
                channel_id="200",
                reply_message_id="101",
                answered_by="300",
                answer="Continue com a opcao ação; $(touch /tmp/nao)",
                now=1010,
            )
            assert answered is not None

            calls: list[tuple[list[str], bytes | None]] = []

            def run(
                command: list[str],
                *,
                input: bytes | None = None,
                **_: object,
            ):
                calls.append((command, input))
                if command[:2] == ["xdotool", "search"]:
                    return completed(command, stdout=b"10\n")
                if command[:2] == ["xdotool", "getwindowname"]:
                    return completed(command, stdout=b"Codex - project\n")
                if command[:2] == ["xdotool", "getwindowgeometry"]:
                    return completed(command, stdout=b"WIDTH=1000\nHEIGHT=800\n")
                if command[:3] == ["xclip", "-selection", "clipboard"] and "-out" in command:
                    return completed(command, stdout=b"clipboard anterior")
                return completed(command)

            dispatcher = X11GuiAnswerDispatcher(x_ratio=0.5, y_ratio=0.9)
            with patch(
                "ai_presence_monitor.gui_answer.shutil.which",
                return_value="/bin/tool",
            ), patch(
                "ai_presence_monitor.gui_answer.subprocess.run",
                side_effect=run,
            ), patch("ai_presence_monitor.gui_answer.time.sleep"):
                dispatcher.dispatch(answered)

            clipboard_writes = [
                value for command, value in calls if command[0] == "xclip" and "-in" in command
            ]
            self.assertEqual(
                clipboard_writes,
                [
                    answered.answer.encode("utf-8"),
                    b"clipboard anterior",
                ],
            )
            commands = [command for command, _ in calls]
            self.assertIn(["xdotool", "key", "--clearmodifiers", "ctrl+v"], commands)
            self.assertIn(["xdotool", "key", "--clearmodifiers", "Return"], commands)
            self.assertIn(
                [
                    "xdotool",
                    "mousemove",
                    "--sync",
                    "--window",
                    "10",
                    "500",
                    "720",
                ],
                commands,
            )

    def test_invalid_ratio_missing_tool_and_command_failure_fail_closed(self) -> None:
        with self.assertRaisesRegex(GuiDispatchError, "horizontal"):
            X11GuiAnswerDispatcher(x_ratio=2, y_ratio=0.9)

        dispatcher = X11GuiAnswerDispatcher(x_ratio=0.5, y_ratio=0.9)
        with patch("ai_presence_monitor.gui_answer.shutil.which", return_value=None):
            with self.assertRaisesRegex(GuiDispatchError, "xdotool"):
                dispatcher.capture_target(title_pattern="Codex")

        with patch(
            "ai_presence_monitor.gui_answer.subprocess.run",
            return_value=completed(["xdotool"], returncode=1, stderr=b"failed"),
        ):
            with self.assertRaisesRegex(GuiDispatchError, "codigo 1"):
                dispatcher._run(["xdotool", "getwindowname", "10"])


if __name__ == "__main__":
    unittest.main()
