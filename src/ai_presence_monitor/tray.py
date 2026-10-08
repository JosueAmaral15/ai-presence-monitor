from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import datetime
from typing import Any

from .codex_input import (
    CodexInputError,
    CodexInputResult,
    CodexQueueClient,
    send_native_message,
)
from .config import AppConfig, load_config
from .control import ControlError, ControlSettings, ControlStore
from .platform_integration import UnsupportedPlatformError, ensure_runtime_enabled
from .scheduled_prompt import (
    configure_scheduled_prompt,
    process_due_scheduled_prompt,
)
from .store import PresenceStore


class TrayUnavailableError(RuntimeError):
    pass


def dispatch_tray_message(
    *,
    settings: ControlSettings,
    message: str,
    destination: str,
    thread_id: str | None,
    client: CodexQueueClient | None = None,
) -> CodexInputResult:
    return send_native_message(
        settings=settings,
        message=message,
        destination=destination,
        thread_id=thread_id,
        client=client,
        detached=True,
    )


def run_tray(  # pragma: no cover - optional Qt presentation; smoke-tested.
    config: AppConfig,
    *,
    check_only: bool = False,
) -> int:
    ensure_runtime_enabled(
        experimental_windows_enabled=config.experimental_windows_enabled,
    )
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QLineEdit,
            QMenu,
            QMessageBox,
            QPlainTextEdit,
            QSpinBox,
            QSystemTrayIcon,
            QVBoxLayout,
        )
    except ImportError as exc:
        raise TrayUnavailableError(
            "PySide6 nao esta instalado. Instale ai-presence-monitor[tray]."
        ) from exc

    existing_app = QApplication.instance()
    owned_app = existing_app is None
    app: Any = QApplication(sys.argv[:1]) if owned_app else existing_app
    app.setApplicationName("AI Presence Monitor")
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        if owned_app:
            app.quit()
        raise TrayUnavailableError(
            "o ambiente grafico atual nao anunciou uma bandeja do sistema."
        )
    if check_only:
        print("Bandeja do sistema disponivel; nenhum icone persistente foi iniciado.")
        if owned_app:
            app.quit()
        return 0

    control_store = ControlStore.from_config(config)
    presence_store = PresenceStore(config.db_path)

    def load_settings() -> ControlSettings:
        return control_store.load()

    def session_combo(configured: str | None) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        configured_index = -1
        for session in presence_store.list_codex_sessions():
            task = session.task or "no task"
            label = f"{task} | {session.worker_id} | {session.session_id}"
            combo.addItem(label, session.session_id)
            if session.session_id == configured:
                configured_index = combo.count() - 1
        if configured and configured_index < 0:
            combo.insertItem(0, configured, configured)
            configured_index = 0
        if configured_index >= 0:
            combo.setCurrentIndex(configured_index)
        else:
            combo.setCurrentIndex(-1)
            combo.setEditText("")
        combo.setPlaceholderText("Codex session UUID or exact name")
        return combo

    def selected_session(combo: QComboBox) -> str | None:
        index = combo.currentIndex()
        if index >= 0 and combo.currentText() == combo.itemText(index):
            data = combo.itemData(index)
            if isinstance(data, str) and data.strip():
                return data.strip()
        return combo.currentText().strip() or None

    class PreferencesDialog(QDialog):
        def __init__(self, settings: ControlSettings):
            super().__init__()
            self._original = settings
            self.setWindowTitle("AI Presence Monitor")
            self.setMinimumWidth(480)
            layout = QVBoxLayout(self)
            title = QLabel("Automation controls")
            title.setStyleSheet("font-size: 16px; font-weight: 600;")
            layout.addWidget(title)

            self.automation = QCheckBox("Enable task automation")
            self.automation.setChecked(settings.task_automation_enabled)
            self.native = QCheckBox("Enable native Codex input")
            self.native.setChecked(settings.native_input_enabled)
            self.gui = QCheckBox("Allow mouse and keyboard fallback")
            self.gui.setChecked(settings.gui_fallback_enabled)
            self.remote = QCheckBox("Allow input on a client computer")
            self.remote.setChecked(settings.remote_input_enabled)
            self.sync = QCheckBox("Synchronize successful continue as activity")
            self.sync.setChecked(settings.sync_activity_enabled)
            for checkbox in (
                self.automation,
                self.native,
                self.gui,
                self.remote,
                self.sync,
            ):
                layout.addWidget(checkbox)

            form = QFormLayout()
            self.thread_field = session_combo(
                settings.scheduled_prompt_thread_id or settings.codex_thread_id
            )
            form.addRow("Codex session", self.thread_field)
            self.endpoint = QLineEdit(settings.codex_remote or "")
            self.endpoint.setPlaceholderText("wss://client.example/app-server")
            form.addRow("Client endpoint", self.endpoint)
            self.auth_env = QLineEdit(settings.remote_auth_token_env or "")
            self.auth_env.setPlaceholderText("CODEX_REMOTE_AUTH_TOKEN")
            form.addRow("Token variable", self.auth_env)
            layout.addLayout(form)

            scheduled_title = QLabel("Scheduled one-shot prompt")
            scheduled_title.setStyleSheet("font-size: 14px; font-weight: 600;")
            layout.addWidget(scheduled_title)
            self.scheduled_prompt = QCheckBox("Send one prompt after a delay")
            self.scheduled_prompt.setChecked(settings.scheduled_prompt_enabled)
            layout.addWidget(self.scheduled_prompt)
            scheduled_form = QFormLayout()
            self.scheduled_delay = QSpinBox()
            self.scheduled_delay.setRange(1, 10_080)
            self.scheduled_delay.setSuffix(" min")
            self.scheduled_delay.setValue(settings.scheduled_prompt_delay_minutes)
            scheduled_form.addRow("Delay", self.scheduled_delay)
            self.scheduled_text = QLineEdit(settings.scheduled_prompt_text)
            self.scheduled_text.setMaxLength(4_000)
            self.scheduled_text.setPlaceholderText("continue")
            scheduled_form.addRow("Prompt", self.scheduled_text)
            layout.addLayout(scheduled_form)
            self.scheduled_status = QLabel(_scheduled_status(settings))
            self.scheduled_status.setWordWrap(True)
            layout.addWidget(self.scheduled_status)

            def update_scheduled_fields(enabled: bool) -> None:
                self.scheduled_delay.setEnabled(enabled)
                self.scheduled_text.setEnabled(enabled)

            self.scheduled_prompt.toggled.connect(update_scheduled_fields)
            update_scheduled_fields(self.scheduled_prompt.isChecked())

            note = QLabel(
                "Token values stay in the operating-system environment and are "
                "never saved here."
            )
            note.setWordWrap(True)
            layout.addWidget(note)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def result_settings(self) -> ControlSettings:
            settings = replace(
                self._original,
                task_automation_enabled=self.automation.isChecked(),
                native_input_enabled=self.native.isChecked(),
                gui_fallback_enabled=self.gui.isChecked(),
                remote_input_enabled=self.remote.isChecked(),
                sync_activity_enabled=self.sync.isChecked(),
                codex_thread_id=selected_session(self.thread_field),
                codex_remote=self.endpoint.text().strip() or None,
                remote_auth_token_env=self.auth_env.text().strip() or None,
            )
            return configure_scheduled_prompt(
                settings,
                enabled=self.scheduled_prompt.isChecked(),
                delay_minutes=self.scheduled_delay.value(),
                text=self.scheduled_text.text(),
                thread_id=selected_session(self.thread_field),
            )

    class MessageDialog(QDialog):
        def __init__(self, settings: ControlSettings):
            super().__init__()
            self.setWindowTitle("Respond to message")
            self.setMinimumWidth(520)
            layout = QVBoxLayout(self)
            form = QFormLayout()
            self.destination = QComboBox()
            self.destination.addItem("This computer", "local")
            self.destination.addItem("Client computer", "remote")
            form.addRow("Destination", self.destination)
            self.thread_field = session_combo(settings.codex_thread_id)
            form.addRow("Codex session", self.thread_field)
            layout.addLayout(form)
            self.message = QPlainTextEdit()
            self.message.setPlaceholderText("Message to send to the Codex session")
            self.message.setMinimumHeight(140)
            layout.addWidget(self.message)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Send")
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def destination_name(self) -> str:
            return str(self.destination.currentData())

    def icon() -> QIcon:
        themed = QIcon.fromTheme("system-run")
        if not themed.isNull():
            return themed
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#16836b"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(17)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "AI")
        painter.end()
        return QIcon(pixmap)

    def _scheduled_status(settings: ControlSettings) -> str:
        if settings.scheduled_prompt_enabled and settings.scheduled_prompt_due_at:
            due = datetime.fromtimestamp(
                settings.scheduled_prompt_due_at
            ).astimezone()
            return f"Armed for {due:%Y-%m-%d %H:%M:%S %Z}; one attempt only."
        labels = {
            "dispatching": "Dispatch was claimed; automatic retry is disabled.",
            "dispatch_started": (
                "Dispatch process started; await later session evidence."
            ),
            "input_emitted": "Input was emitted; await later session evidence.",
            "failed_or_uncertain": (
                "Last attempt failed or was uncertain; automatic retry is disabled."
            ),
        }
        return labels.get(settings.scheduled_prompt_last_state, "No prompt is armed.")

    tray = QSystemTrayIcon(icon(), app)
    tray.setToolTip("AI Presence Monitor")
    menu = QMenu()
    automation_action = QAction("Enable task automation", menu)
    automation_action.setCheckable(True)
    automation_action.setChecked(load_settings().task_automation_enabled)
    respond_action = QAction("Respond to message...", menu)
    exit_action = QAction("Exit", menu)
    menu.addAction(automation_action)
    menu.addAction(respond_action)
    menu.addSeparator()
    menu.addAction(exit_action)
    tray.setContextMenu(menu)

    def show_error(title: str, error: Exception) -> None:
        QMessageBox.critical(None, title, str(error))

    def toggle_automation(enabled: bool) -> None:
        try:
            settings = load_settings().with_control("task-automation", enabled)
            control_store.save(settings)
            tray.showMessage(
                "AI Presence Monitor",
                "Task automation enabled." if enabled else "Task automation disabled.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
        except (ControlError, OSError) as exc:
            automation_action.blockSignals(True)
            automation_action.setChecked(not enabled)
            automation_action.blockSignals(False)
            show_error("Unable to update controls", exc)

    def show_preferences() -> None:
        try:
            dialog = PreferencesDialog(load_settings())
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            settings = dialog.result_settings()
            control_store.save(settings)
            automation_action.blockSignals(True)
            automation_action.setChecked(settings.task_automation_enabled)
            automation_action.blockSignals(False)
            check_scheduled_prompt()
        except (ControlError, OSError) as exc:
            show_error("Unable to save preferences", exc)

    def respond() -> None:
        try:
            settings = load_settings()
            dialog = MessageDialog(settings)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            result = dispatch_tray_message(
                settings=settings,
                message=dialog.message.toPlainText(),
                destination=dialog.destination_name(),
                thread_id=selected_session(dialog.thread_field),
            )
            location = "client computer" if result.remote else "this computer"
            QMessageBox.information(
                None,
                "Dispatch started",
                f"Dispatch started for {location}. Await later session evidence.",
            )
        except (CodexInputError, ControlError) as exc:
            show_error("Message was not sent", exc)

    def activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            show_preferences()

    last_schedule_notice: list[str | None] = [None]

    def check_scheduled_prompt() -> None:
        try:
            result = process_due_scheduled_prompt(store=control_store)
        except (ControlError, OSError) as exc:
            notice_key = f"error:{type(exc).__name__}:{exc}"
            if last_schedule_notice[0] != notice_key:
                last_schedule_notice[0] = notice_key
                tray.showMessage(
                    "Scheduled prompt unavailable",
                    str(exc),
                    QSystemTrayIcon.MessageIcon.Critical,
                    5000,
                )
            return
        if result.state in {"disabled", "waiting"}:
            last_schedule_notice[0] = None
            return
        if last_schedule_notice[0] == result.state:
            return
        last_schedule_notice[0] = result.state
        if result.state == "failed_or_uncertain":
            tray.showMessage(
                "Scheduled prompt not confirmed",
                "The one-shot attempt failed or was uncertain and will not retry.",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )
            return
        tray.showMessage(
            "Scheduled prompt dispatched",
            "The one-shot transport started. Await later session evidence.",
            QSystemTrayIcon.MessageIcon.Information,
            4000,
        )

    automation_action.toggled.connect(toggle_automation)
    respond_action.triggered.connect(respond)
    exit_action.triggered.connect(app.quit)
    tray.activated.connect(activated)
    schedule_timer = QTimer(app)
    schedule_timer.setInterval(1000)
    schedule_timer.timeout.connect(check_scheduled_prompt)
    schedule_timer.start()
    tray.show()
    QTimer.singleShot(0, check_scheduled_prompt)
    return app.exec()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Presence Monitor system tray.")
    parser.add_argument("--env-file")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        result = run_tray(load_config(args.env_file), check_only=args.check)
    except (
        ControlError,
        TrayUnavailableError,
        UnsupportedPlatformError,
        ValueError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        result = 2
    raise SystemExit(result)


if __name__ == "__main__":
    main()
