from dataclasses import dataclass


@dataclass(frozen=True)
class AlertThreshold:
    level: str
    after_seconds: int
    color_name: str
    discord_color: int
    icon: str


@dataclass(frozen=True)
class ProtocolSpec:
    protocol_id: str
    title: str
    expected_signal_seconds: int | None
    monitored_clock: str
    description: str
    thresholds: tuple[AlertThreshold, ...]


YELLOW = AlertThreshold(
    level="yellow",
    after_seconds=7 * 60,
    color_name="amarelo",
    discord_color=0xF1C40F,
    icon=":yellow_circle:",
)
ORANGE = AlertThreshold(
    level="orange",
    after_seconds=15 * 60,
    color_name="laranja",
    discord_color=0xE67E22,
    icon=":orange_circle:",
)
RED = AlertThreshold(
    level="red",
    after_seconds=30 * 60,
    color_name="vermelho",
    discord_color=0xE74C3C,
    icon=":red_circle:",
)

PROTOCOLS: dict[str, ProtocolSpec] = {
    "protocol1": ProtocolSpec(
        protocol_id="protocol1",
        title="Protocolo 1 - ponto a cada 5 minutos",
        expected_signal_seconds=5 * 60,
        monitored_clock="last_signal_at",
        description=(
            "A IA deve sinalizar publicamente a cada 5 minutos que segue "
            "trabalhando. O monitor alerta quando a ultima sinalizacao atrasa."
        ),
        thresholds=(YELLOW, ORANGE, RED),
    ),
    "protocol2": ProtocolSpec(
        protocol_id="protocol2",
        title="Protocolo 2 - inicio/fim com atividade silenciosa",
        expected_signal_seconds=None,
        monitored_clock="last_activity_at",
        description=(
            "A IA sinaliza publicamente quando inicia e termina. Chamadas "
            "silenciosas de touch podem registrar atividade interna sem postar "
            "no canal de ponto."
        ),
        thresholds=(
            AlertThreshold("yellow", 5 * 60, "amarelo", 0xF1C40F, ":yellow_circle:"),
            AlertThreshold("orange", 10 * 60, "laranja", 0xE67E22, ":orange_circle:"),
            AlertThreshold("red", 15 * 60, "vermelho", 0xE74C3C, ":red_circle:"),
        ),
    ),
}

ALERT_SEVERITY = {"yellow": 1, "orange": 2, "red": 3}


def get_protocol(protocol_id: str) -> ProtocolSpec:
    try:
        return PROTOCOLS[protocol_id]
    except KeyError as exc:
        valid = ", ".join(sorted(PROTOCOLS))
        raise ValueError(f"Protocolo desconhecido: {protocol_id!r}. Use: {valid}.") from exc


def choose_threshold(protocol: ProtocolSpec, age_seconds: float) -> AlertThreshold | None:
    selected = None
    for threshold in protocol.thresholds:
        if age_seconds >= threshold.after_seconds:
            selected = threshold
    return selected


def should_escalate(previous_level: str | None, next_level: str) -> bool:
    if previous_level is None:
        return True
    return ALERT_SEVERITY[next_level] > ALERT_SEVERITY.get(previous_level, 0)


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "sem registro"
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{sec:02d}s"
    if minutes:
        return f"{minutes}m{sec:02d}s"
    return f"{sec}s"
