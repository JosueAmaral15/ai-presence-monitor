from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone

from . import __version__
from .alarm import AlarmControlError, AlarmController
from .config import AppConfig
from .protocols import AlertThreshold, ProtocolSpec, format_duration
from .store import WorkerState


class NotificationError(RuntimeError):
    pass


class Notifier:
    def __init__(
        self,
        config: AppConfig,
        dry_run: bool = False,
        alarm_controller: AlarmController | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.alarm_controller = alarm_controller or AlarmController()

    def send_point(self, event_type: str, worker: WorkerState, message: str | None) -> None:
        event_titles = {
            "heartbeat": "Ponto de atividade",
            "start": "Inicio de tarefa",
            "finish": "Fim de tarefa",
            "touch": "Atividade registrada",
        }
        title = event_titles.get(event_type, event_type)
        content = (
            f"**{title}**\n"
            f"Computador: `{worker.computer}`\n"
            f"IA: `{worker.ia_name}`\n"
            f"Worker: `{worker.worker_id}`\n"
            f"Protocolo: `{worker.protocol}`"
        )
        if worker.current_task:
            content += f"\nTarefa: `{worker.current_task}`"
        if message:
            content += f"\nMensagem: {message}"

        self._send_discord(
            self.config.discord_point_webhook_url,
            {"content": content},
            label="discord:ponto",
        )
        self._send_telegram(content, label="telegram:ponto")

    def send_alert(
        self,
        *,
        worker: WorkerState,
        protocol: ProtocolSpec,
        threshold: AlertThreshold,
        age_seconds: float,
        clock_name: str,
        trigger_red_escalation: bool = True,
    ) -> None:
        title = f"{threshold.icon} Alerta {threshold.color_name.upper()} - {worker.ia_name}"
        description = (
            f"Computador: `{worker.computer}`\n"
            f"Worker: `{worker.worker_id}`\n"
            f"Protocolo: `{protocol.protocol_id}`\n"
            f"Relogio monitorado: `{clock_name}`\n"
            f"Tempo sem sinal/atividade: `{format_duration(age_seconds)}`"
        )
        if worker.current_task:
            description += f"\nTarefa: `{worker.current_task}`"
        if worker.last_message:
            description += f"\nUltima mensagem: {worker.last_message}"

        webhook_url = self.config.discord_alert_webhook_url
        if threshold.level == "red" and self.config.discord_red_webhook_url:
            webhook_url = self.config.discord_red_webhook_url

        self._send_discord(
            webhook_url,
            {
                "content": title,
                "embeds": [
                    {
                        "title": title,
                        "description": description,
                        "color": threshold.discord_color,
                        "timestamp": datetime.now(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                ],
            },
            label=f"discord:alerta:{threshold.level}",
        )
        self._send_telegram(
            f"{title}\n{description.replace('`', '')}",
            label=f"telegram:alerta:{threshold.level}",
        )

        if threshold.level == "red" and trigger_red_escalation:
            self._trigger_red_escalation(worker, protocol, threshold, age_seconds)

    def _trigger_red_escalation(
        self,
        worker: WorkerState,
        protocol: ProtocolSpec,
        threshold: AlertThreshold,
        age_seconds: float,
    ) -> None:
        mode = self.config.red_notification_mode
        payload = {
            "worker": asdict(worker),
            "protocol": protocol.protocol_id,
            "level": threshold.level,
            "age_seconds": age_seconds,
            "mode": mode,
        }

        if mode == "alarm":
            if not self.config.red_alert_command:
                self._dry_or_print(
                    "alarme",
                    "Alerta vermelho configurado como alarm, mas RED_ALERT_COMMAND nao foi definido.",
                )
                return
            self._start_alarm(self.config.red_alert_command)
            return

        if mode == "phone":
            if not self.config.phone_webhook_url:
                self._dry_or_print(
                    "telefone",
                    "Alerta vermelho configurado como phone, mas PHONE_WEBHOOK_URL nao foi definido.",
                )
                return
            self._post_json(self.config.phone_webhook_url, payload, label="telefone")
            return

        self._dry_or_print("vermelho", f"Modo de alerta vermelho sem acao externa: {mode!r}.")

    def _send_discord(self, url: str | None, payload: dict, label: str) -> None:
        if not url:
            self._dry_or_print(label, "Webhook do Discord nao configurado.")
            return
        self._post_json(url, payload, label=label)

    def _send_telegram(self, text: str, label: str) -> None:
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            self._dry_or_print(label, "Telegram nao configurado.")
            return
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        self._post_json(
            url,
            {"chat_id": self.config.telegram_chat_id, "text": text},
            label=label,
        )

    def _post_json(self, url: str, payload: dict, label: str) -> None:
        if self.dry_run:
            print(f"[dry-run:{label}] {json.dumps(payload, ensure_ascii=False)}")
            return

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"ai-presence-monitor/{__version__}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read()
        except urllib.error.URLError as exc:
            raise NotificationError(f"Falha ao enviar notificacao para {label}: {exc}") from exc

    def _start_alarm(self, command: str) -> None:
        if self.dry_run:
            print(f"[dry-run:comando] {command}")
            return
        try:
            result = self.alarm_controller.start(command)
        except AlarmControlError as exc:
            raise NotificationError(str(exc)) from exc
        if result.status == "already_running":
            self._dry_or_print(
                "alarme",
                f"Alarme ja esta ativo no PID {result.pid}.",
            )
            return
        self._dry_or_print(
            "alarme",
            f"Alarme iniciado no PID {result.pid}. Interrompa com: ai-presence stop-alarm",
        )

    def _dry_or_print(self, label: str, message: str) -> None:
        prefix = "dry-run" if self.dry_run else "info"
        print(f"[{prefix}:{label}] {message}")
