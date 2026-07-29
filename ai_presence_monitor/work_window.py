from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .config import AppConfig


@dataclass(frozen=True)
class WorkWindowStatus:
    enabled: bool
    within_window: bool
    alerts_allowed: bool
    local_now: datetime
    reason: str


def parse_clock(value: str) -> time:
    try:
        hour_text, minute_text = value.strip().split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise ValueError(f"Horario invalido: {value!r}. Use HH:MM.") from exc

    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"Horario invalido: {value!r}. Use HH:MM entre 00:00 e 23:59.")
    return time(hour=hour, minute=minute)


def is_time_in_window(current: time, start: time, end: time) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def get_work_window_status(config: AppConfig, now_timestamp: float | None = None) -> WorkWindowStatus:
    tz = ZoneInfo(config.work_window_timezone)
    local_now = (
        datetime.now(tz)
        if now_timestamp is None
        else datetime.fromtimestamp(now_timestamp, tz=tz)
    )

    if not config.work_window_enabled:
        return WorkWindowStatus(
            enabled=False,
            within_window=True,
            alerts_allowed=True,
            local_now=local_now,
            reason="janela de expediente desativada",
        )

    behavior = config.outside_work_window_behavior
    if behavior not in {"suppress_alerts", "allow_alerts"}:
        raise ValueError(
            "PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR deve ser "
            "suppress_alerts ou allow_alerts."
        )

    start = parse_clock(config.work_window_start)
    end = parse_clock(config.work_window_end)
    within = is_time_in_window(local_now.time().replace(second=0, microsecond=0), start, end)
    alerts_allowed = within or behavior == "allow_alerts"
    reason = (
        "dentro do expediente"
        if within
        else f"fora do expediente {config.work_window_start}-{config.work_window_end}"
    )

    return WorkWindowStatus(
        enabled=True,
        within_window=within,
        alerts_allowed=alerts_allowed,
        local_now=local_now,
        reason=reason,
    )
