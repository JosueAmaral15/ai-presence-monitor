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
from .control import (
    DEFAULT_PROMPT_RULE_OCCURRENCES,
    MAX_PROMPT_RULES,
    ControlError,
    ControlSettings,
    ControlStore,
    PromptRule,
)
from .platform_integration import UnsupportedPlatformError, ensure_runtime_enabled
from .prompt_rules import (
    configure_prompt_rule,
    process_prompt_rules,
    replace_prompt_rules,
)
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
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMenu,
            QMessageBox,
            QPlainTextEdit,
            QScrollArea,
            QSpinBox,
            QSystemTrayIcon,
            QToolButton,
            QVBoxLayout,
            QWidget,
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

    def load_settings(profile_id: str | None = None) -> ControlSettings:
        return control_store.load(profile_id)

    def known_profile_ids() -> tuple[str, ...]:
        profile_ids = set(control_store.list_profile_ids())
        profile_ids.update(worker.worker_id for worker in presence_store.list_workers())
        profile_ids.update(
            session.worker_id for session in presence_store.list_codex_sessions()
        )
        return tuple(sorted(profile_ids))

    def profile_combo(configured: str | None = None) -> QComboBox:
        combo = QComboBox()
        combo.addItem("Global defaults", None)
        configured_index = 0
        workers = {
            worker.worker_id: worker for worker in presence_store.list_workers()
        }
        for profile_id in known_profile_ids():
            worker = workers.get(profile_id)
            task = worker.current_task if worker and worker.current_task else "no task"
            combo.addItem(f"{task} | {profile_id}", profile_id)
            if profile_id == configured:
                configured_index = combo.count() - 1
        combo.setCurrentIndex(configured_index)
        return combo

    def selected_profile(combo: QComboBox) -> str | None:
        data = combo.currentData()
        return data if isinstance(data, str) and data.strip() else None

    def populate_session_combo(
        combo: QComboBox,
        configured: str | None,
        profile_id: str | None,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.setEditable(profile_id is None)
        configured_index = -1
        sessions = presence_store.list_codex_sessions(worker_id=profile_id)
        if profile_id is None:
            sessions = presence_store.list_codex_sessions()
        for session in sessions:
            task = session.task or "no task"
            label = f"{task} | {session.worker_id} | {session.session_id}"
            combo.addItem(label, session.session_id)
            if session.session_id == configured:
                configured_index = combo.count() - 1
        if configured and configured_index < 0:
            label = configured if profile_id is None else f"saved session | {configured}"
            combo.insertItem(0, label, configured)
            configured_index = 0
        if configured_index >= 0:
            combo.setCurrentIndex(configured_index)
        else:
            combo.setCurrentIndex(-1)
            if combo.isEditable():
                combo.setEditText("")
        combo.setPlaceholderText("Codex session UUID or exact name")
        combo.blockSignals(False)

    def session_combo(
        configured: str | None,
        profile_id: str | None = None,
    ) -> QComboBox:
        combo = QComboBox()
        populate_session_combo(combo, configured, profile_id)
        return combo

    def selected_session(combo: QComboBox) -> str | None:
        index = combo.currentIndex()
        if index >= 0 and combo.currentText() == combo.itemText(index):
            data = combo.itemData(index)
            if isinstance(data, str) and data.strip():
                return data.strip()
        return combo.currentText().strip() or None

    class PromptRuleEditor(QWidget):
        def __init__(
            self,
            *,
            rule: PromptRule | None,
            profile_id: str | None,
            remove_callback: Any,
        ):
            super().__init__()
            self.original = rule
            layout = QGridLayout(self)
            layout.setContentsMargins(0, 8, 0, 8)

            self.enabled = QCheckBox("Enabled")
            self.enabled.setChecked(rule.enabled if rule else False)
            layout.addWidget(self.enabled, 0, 0)

            self.trigger = QComboBox()
            self.trigger.addItem("After arming", "after_delay")
            if profile_id is not None:
                self.trigger.addItem("After red inactivity", "red_inactivity")
            trigger = rule.trigger if rule else "after_delay"
            trigger_index = self.trigger.findData(trigger)
            self.trigger.setCurrentIndex(max(0, trigger_index))
            layout.addWidget(self.trigger, 0, 1)

            self.remove = QToolButton()
            self.remove.setText("-")
            self.remove.setToolTip("Remove prompt rule")
            self.remove.setFixedSize(28, 28)
            self.remove.clicked.connect(lambda: remove_callback(self))
            layout.addWidget(self.remove, 0, 2)

            self.session = session_combo(
                rule.thread_id if rule else None,
                profile_id,
            )
            layout.addWidget(QLabel("Session"), 1, 0)
            layout.addWidget(self.session, 1, 1, 1, 2)

            self.delay = QSpinBox()
            self.delay.setRange(1, 10_080)
            self.delay.setSuffix(" min")
            self.delay.setValue(rule.delay_minutes if rule else 210)
            layout.addWidget(QLabel("Delay"), 2, 0)
            layout.addWidget(self.delay, 2, 1, 1, 2)

            self.text = QLineEdit(rule.text if rule else "continue")
            self.text.setMaxLength(4_000)
            self.text.setPlaceholderText("continue")
            layout.addWidget(QLabel("Prompt"), 3, 0)
            layout.addWidget(self.text, 3, 1, 1, 2)

            self.repeat = QCheckBox("Repeat after confirmed session activity")
            self.repeat.setChecked(rule.repeat_enabled if rule else False)
            layout.addWidget(self.repeat, 4, 0, 1, 3)

            self.repeat_interval = QSpinBox()
            self.repeat_interval.setRange(1, 10_080)
            self.repeat_interval.setSuffix(" min")
            self.repeat_interval.setValue(
                rule.repeat_interval_minutes if rule else 210
            )
            layout.addWidget(QLabel("Repeat interval"), 5, 0)
            layout.addWidget(self.repeat_interval, 5, 1, 1, 2)

            self.max_occurrences = QSpinBox()
            self.max_occurrences.setRange(1, 100)
            self.max_occurrences.setValue(
                rule.max_occurrences
                if rule
                else DEFAULT_PROMPT_RULE_OCCURRENCES
            )
            layout.addWidget(QLabel("Maximum sends"), 6, 0)
            layout.addWidget(self.max_occurrences, 6, 1, 1, 2)

            self.status = QLabel(_prompt_rule_status(rule))
            self.status.setWordWrap(True)
            layout.addWidget(self.status, 7, 0, 1, 3)
            self.repeat.toggled.connect(self._update_repeat_fields)
            self.enabled.toggled.connect(self._update_enabled_fields)
            self._update_enabled_fields(self.enabled.isChecked())

        def _update_repeat_fields(self, _checked: bool) -> None:
            active = self.enabled.isChecked() and self.repeat.isChecked()
            self.repeat_interval.setEnabled(active)
            self.max_occurrences.setEnabled(active)

        def _update_enabled_fields(self, checked: bool) -> None:
            for widget in (
                self.trigger,
                self.session,
                self.delay,
                self.text,
                self.repeat,
            ):
                widget.setEnabled(checked)
            self._update_repeat_fields(self.repeat.isChecked())

        def result_rule(self) -> PromptRule:
            return configure_prompt_rule(
                self.original,
                enabled=self.enabled.isChecked(),
                thread_id=selected_session(self.session),
                trigger=str(self.trigger.currentData()),
                delay_minutes=self.delay.value(),
                text=self.text.text(),
                repeat_enabled=self.repeat.isChecked(),
                repeat_interval_minutes=self.repeat_interval.value(),
                max_occurrences=self.max_occurrences.value(),
            )

    class PreferencesDialog(QDialog):
        def __init__(self):
            super().__init__()
            recent_sessions = presence_store.list_codex_sessions(limit=1)
            initial_profile = (
                recent_sessions[0].worker_id if recent_sessions else None
            )
            self.profile = profile_combo(initial_profile)
            settings = load_settings(selected_profile(self.profile))
            self._original = settings
            self.setWindowTitle("AI Presence Monitor")
            self.setMinimumWidth(480)
            layout = QVBoxLayout(self)
            title = QLabel("Automation controls")
            title.setStyleSheet("font-size: 16px; font-weight: 600;")
            layout.addWidget(title)

            profile_form = QFormLayout()
            profile_form.addRow("Project or agent", self.profile)
            layout.addLayout(profile_form)

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
                settings.codex_thread_id,
                selected_profile(self.profile),
            )
            form.addRow("Default Codex session", self.thread_field)
            self.endpoint = QLineEdit(settings.codex_remote or "")
            self.endpoint.setPlaceholderText("wss://client.example/app-server")
            form.addRow("Client endpoint", self.endpoint)
            self.auth_env = QLineEdit(settings.remote_auth_token_env or "")
            self.auth_env.setPlaceholderText("CODEX_REMOTE_AUTH_TOKEN")
            form.addRow("Token variable", self.auth_env)
            layout.addLayout(form)

            scheduled_title = QLabel("Prompt rules")
            scheduled_title.setStyleSheet("font-size: 14px; font-weight: 600;")
            layout.addWidget(scheduled_title)
            self.rule_editors: list[PromptRuleEditor] = []
            self.rules_widget = QWidget()
            self.rules_layout = QVBoxLayout(self.rules_widget)
            self.rules_layout.setContentsMargins(0, 0, 0, 0)
            rules_scroll = QScrollArea()
            rules_scroll.setWidgetResizable(True)
            rules_scroll.setMaximumHeight(420)
            rules_scroll.setWidget(self.rules_widget)
            layout.addWidget(rules_scroll)
            add_row = QHBoxLayout()
            self.add_rule_button = QToolButton()
            self.add_rule_button.setText("+")
            self.add_rule_button.setToolTip("Add prompt rule")
            self.add_rule_button.setFixedSize(28, 28)
            self.add_rule_button.clicked.connect(lambda: self._add_rule())
            add_row.addWidget(self.add_rule_button)
            add_row.addStretch()
            layout.addLayout(add_row)

            self.profile.currentIndexChanged.connect(self._load_selected_profile)
            self._rebuild_rules(settings)

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

        def _load_selected_profile(self, _index: int = -1) -> None:
            profile_id = selected_profile(self.profile)
            settings = load_settings(profile_id)
            self._original = settings
            self.automation.setChecked(settings.task_automation_enabled)
            self.native.setChecked(settings.native_input_enabled)
            self.gui.setChecked(settings.gui_fallback_enabled)
            self.remote.setChecked(settings.remote_input_enabled)
            self.sync.setChecked(settings.sync_activity_enabled)
            populate_session_combo(
                self.thread_field,
                settings.codex_thread_id,
                profile_id,
            )
            self.endpoint.setText(settings.codex_remote or "")
            self.auth_env.setText(settings.remote_auth_token_env or "")
            self._rebuild_rules(settings)

        def _rules_for_settings(
            self,
            settings: ControlSettings,
        ) -> tuple[PromptRule, ...]:
            if settings.prompt_rules:
                return settings.prompt_rules
            if not (
                settings.scheduled_prompt_enabled
                or settings.scheduled_prompt_thread_id
                or settings.scheduled_prompt_last_state != "disabled"
            ):
                return ()
            require_red = settings.scheduled_prompt_require_red_inactivity
            return (
                PromptRule(
                    rule_id=settings.scheduled_prompt_id or "legacy-scheduled-prompt",
                    enabled=settings.scheduled_prompt_enabled,
                    thread_id=settings.scheduled_prompt_thread_id,
                    trigger="red_inactivity" if require_red else "after_delay",
                    delay_minutes=settings.scheduled_prompt_delay_minutes,
                    text=settings.scheduled_prompt_text,
                    next_due_at=(
                        None if require_red else settings.scheduled_prompt_due_at
                    ),
                    last_state=(
                        "waiting_for_event"
                        if settings.scheduled_prompt_enabled and require_red
                        else settings.scheduled_prompt_last_state
                    ),
                    last_attempt_at=settings.scheduled_prompt_last_attempt_at,
                ),
            )

        def _rebuild_rules(self, settings: ControlSettings) -> None:
            for editor in self.rule_editors:
                self.rules_layout.removeWidget(editor)
                editor.deleteLater()
            self.rule_editors.clear()
            for rule in self._rules_for_settings(settings):
                self._add_rule(rule)
            self.add_rule_button.setEnabled(len(self.rule_editors) < MAX_PROMPT_RULES)

        def _add_rule(self, rule: PromptRule | None = None) -> None:
            if len(self.rule_editors) >= MAX_PROMPT_RULES:
                return
            editor = PromptRuleEditor(
                rule=rule,
                profile_id=self.profile_id(),
                remove_callback=self._remove_rule,
            )
            self.rule_editors.append(editor)
            self.rules_layout.addWidget(editor)
            self.add_rule_button.setEnabled(len(self.rule_editors) < MAX_PROMPT_RULES)

        def _remove_rule(self, editor: PromptRuleEditor) -> None:
            if editor not in self.rule_editors:
                return
            self.rule_editors.remove(editor)
            self.rules_layout.removeWidget(editor)
            editor.deleteLater()
            self.add_rule_button.setEnabled(True)

        def profile_id(self) -> str | None:
            return selected_profile(self.profile)

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
            settings = configure_scheduled_prompt(
                settings,
                enabled=False,
                delay_minutes=settings.scheduled_prompt_delay_minutes,
                text=settings.scheduled_prompt_text,
                thread_id=None,
                require_red_inactivity=False,
            )
            return replace_prompt_rules(
                settings,
                [editor.result_rule() for editor in self.rule_editors],
            )

    class MessageDialog(QDialog):
        def __init__(self):
            super().__init__()
            recent_sessions = presence_store.list_codex_sessions(limit=1)
            initial_profile = (
                recent_sessions[0].worker_id if recent_sessions else None
            )
            self.profile = profile_combo(initial_profile)
            settings = load_settings(selected_profile(self.profile))
            self.settings = settings
            self.setWindowTitle("Respond to message")
            self.setMinimumWidth(520)
            layout = QVBoxLayout(self)
            form = QFormLayout()
            self.destination = QComboBox()
            self.destination.addItem("This computer", "local")
            self.destination.addItem("Client computer", "remote")
            form.addRow("Destination", self.destination)
            form.addRow("Project or agent", self.profile)
            self.thread_field = session_combo(
                settings.codex_thread_id,
                selected_profile(self.profile),
            )
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
            self.profile.currentIndexChanged.connect(self._load_selected_profile)

        def _load_selected_profile(self, _index: int = -1) -> None:
            profile_id = selected_profile(self.profile)
            self.settings = load_settings(profile_id)
            populate_session_combo(
                self.thread_field,
                self.settings.codex_thread_id,
                profile_id,
            )

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
            red_gate = (
                " It will then wait for red inactivity."
                if settings.scheduled_prompt_require_red_inactivity
                else ""
            )
            return (
                f"Armed for {due:%Y-%m-%d %H:%M:%S %Z}; one attempt only."
                f"{red_gate}"
            )
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

    def _prompt_rule_status(rule: PromptRule | None) -> str:
        if rule is None:
            return "New rule; save to persist it."
        if rule.awaiting_confirmation:
            return (
                f"Waiting for later activity from the exact session; "
                f"{rule.occurrence_count}/{rule.max_occurrences} sends used."
            )
        if rule.enabled and rule.next_due_at is not None:
            due = datetime.fromtimestamp(rule.next_due_at).astimezone()
            return (
                f"Armed for {due:%Y-%m-%d %H:%M:%S %Z}; "
                f"{rule.occurrence_count}/{rule.max_occurrences} sends used."
            )
        if rule.enabled and rule.trigger == "red_inactivity":
            return "Waiting for canonical red inactivity, then the configured delay."
        labels = {
            "dispatching": "Dispatch was claimed; automatic retry is disabled.",
            "dispatch_started": "Dispatch started; await later session evidence.",
            "input_emitted": "Input was emitted; await later session evidence.",
            "failed_or_uncertain": (
                "Last attempt failed or was uncertain; the rule is disabled."
            ),
        }
        return labels.get(rule.last_state, "Rule is disabled.")

    tray = QSystemTrayIcon(icon(), app)
    tray.setToolTip("AI Presence Monitor")
    menu = QMenu()
    automation_action = QAction("Enable task automation (global default)", menu)
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
            dialog = PreferencesDialog()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            settings = dialog.result_settings()
            control_store.save(settings, dialog.profile_id())
            if dialog.profile_id() is None:
                automation_action.blockSignals(True)
                automation_action.setChecked(settings.task_automation_enabled)
                automation_action.blockSignals(False)
            check_scheduled_prompt()
        except (ControlError, OSError) as exc:
            show_error("Unable to save preferences", exc)

    def respond() -> None:
        try:
            dialog = MessageDialog()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            result = dispatch_tray_message(
                settings=dialog.settings,
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

    last_schedule_notice: dict[str, str | None] = {}

    def check_scheduled_prompt() -> None:
        try:
            profile_ids = control_store.list_profile_ids()
        except (ControlError, OSError) as exc:
            notice_key = f"profiles:{type(exc).__name__}:{exc}"
            if last_schedule_notice.get("profiles") != notice_key:
                last_schedule_notice["profiles"] = notice_key
                tray.showMessage(
                    "Scheduled prompt unavailable",
                    str(exc),
                    QSystemTrayIcon.MessageIcon.Critical,
                    5000,
                )
            return
        last_schedule_notice["profiles"] = None
        for profile_id in (None, *profile_ids):
            notice_profile = profile_id or "global"
            result_state: str
            result_rule_id: str | None
            try:
                legacy_result = process_due_scheduled_prompt(
                    store=control_store,
                    profile_id=profile_id,
                    presence_store=presence_store,
                )
                if legacy_result.state in {
                    "dispatch_started",
                    "input_emitted",
                    "failed_or_uncertain",
                }:
                    result_state = legacy_result.state
                    result_rule_id = "legacy"
                else:
                    rule_result = process_prompt_rules(
                        store=control_store,
                        profile_id=profile_id,
                        presence_store=presence_store,
                    )
                    result_state = rule_result.state
                    result_rule_id = rule_result.rule_id
            except (ControlError, OSError) as exc:
                notice_key = f"error:{type(exc).__name__}:{exc}"
                if last_schedule_notice.get(notice_profile) != notice_key:
                    last_schedule_notice[notice_profile] = notice_key
                    tray.showMessage(
                        "Scheduled prompt unavailable",
                        f"{notice_profile}: {exc}",
                        QSystemTrayIcon.MessageIcon.Critical,
                        5000,
                    )
                continue
            if result_state in {
                "disabled",
                "automation_disabled",
                "waiting",
                "waiting_for_event",
                "waiting_for_confirmation",
            }:
                last_schedule_notice[notice_profile] = None
                continue
            notice_state = f"{result_rule_id}:{result_state}"
            if last_schedule_notice.get(notice_profile) == notice_state:
                continue
            last_schedule_notice[notice_profile] = notice_state
            if result_state == "failed_or_uncertain":
                tray.showMessage(
                    "Scheduled prompt not confirmed",
                    f"{notice_profile} / {result_rule_id}: the attempt failed "
                    "or was uncertain and the rule was disabled.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000,
                )
                continue
            tray.showMessage(
                "Scheduled prompt dispatched",
                f"{notice_profile} / {result_rule_id}: transport started. "
                "Await later session evidence.",
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
