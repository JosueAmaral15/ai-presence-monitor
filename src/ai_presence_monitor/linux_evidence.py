from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .diagnostics import (
    DiagnosticEvidence,
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
)


@dataclass(frozen=True)
class LinuxObservation:
    source: EvidenceSource
    kind: EvidenceKind
    state: str
    summary: str


_PROCESS_NAME = re.compile(r"^[A-Za-z0-9_.+:-]{1,64}$")
_SERVICE_UNIT = re.compile(r"^[A-Za-z0-9_.@:-]{1,128}\.service$")
_FAILED_RESULTS = frozenset(
    {
        "core-dump",
        "exit-code",
        "protocol",
        "resources",
        "signal",
        "start-limit-hit",
        "timeout",
        "watchdog",
    }
)


class LinuxProcessObserver:
    def __init__(
        self,
        pid: int,
        *,
        expected_name: str | None = None,
        proc_root: Path = Path("/proc"),
    ) -> None:
        if pid <= 0:
            raise ValueError("process PID must be greater than zero.")
        if expected_name is not None and not _PROCESS_NAME.fullmatch(expected_name):
            raise ValueError("expected process name must be a bounded Linux name.")
        self.pid = pid
        self.expected_name = expected_name
        self.proc_root = proc_root
        self._start_ticks: int | None = None

    def sample(self) -> LinuxObservation:
        process_dir = self.proc_root / str(self.pid)
        try:
            process_name = (process_dir / "comm").read_text(encoding="utf-8").strip()
            stat = (process_dir / "stat").read_text(encoding="utf-8")
        except FileNotFoundError:
            return self._observation("missing", "The configured Linux process is absent.")
        except OSError:
            return self._observation(
                "unreadable",
                "The configured Linux process state could not be read.",
            )

        if self.expected_name is not None and process_name != self.expected_name:
            return self._observation(
                "identity_mismatch",
                "The configured Linux PID does not match the expected process name.",
            )

        parsed = _parse_proc_stat(stat)
        if parsed is None:
            return self._observation(
                "unreadable",
                "The configured Linux process state could not be parsed.",
            )
        process_state, start_ticks = parsed
        if self._start_ticks is None:
            self._start_ticks = start_ticks
        elif self._start_ticks != start_ticks:
            return self._observation(
                "replaced",
                "The configured Linux PID now belongs to a different process instance.",
            )

        if process_state == "Z":
            return self._observation("zombie", "The configured Linux process is a zombie.")
        if process_state in {"X", "x"}:
            return self._observation("dead", "The configured Linux process is dead.")
        return self._observation("running", "The configured Linux process is present.")

    @staticmethod
    def _observation(state: str, summary: str) -> LinuxObservation:
        return LinuxObservation(
            source=EvidenceSource.PROCESS,
            kind=EvidenceKind.PROCESS_STATE,
            state=state,
            summary=summary,
        )


class LinuxPowerObserver:
    def __init__(
        self,
        *,
        suspend_gap_seconds: float = 5.0,
        boot_id_reader: Callable[[], str] | None = None,
        boottime_reader: Callable[[], float] | None = None,
        monotonic_reader: Callable[[], float] = time.monotonic,
    ) -> None:
        if suspend_gap_seconds <= 0:
            raise ValueError("suspend gap must be greater than zero.")
        self.suspend_gap_seconds = suspend_gap_seconds
        self._boot_id_reader = boot_id_reader or _read_boot_id
        self._boottime_reader = boottime_reader or _read_boottime
        self._monotonic_reader = monotonic_reader
        self._previous_boot_id: str | None = None
        self._previous_boottime: float | None = None
        self._previous_monotonic: float | None = None

    def sample(self) -> LinuxObservation:
        try:
            boot_id = self._boot_id_reader().strip()
            boottime = self._boottime_reader()
            monotonic = self._monotonic_reader()
        except (OSError, TypeError, ValueError):
            return self._observation(
                "unknown",
                "Linux power timing state could not be read.",
            )
        if not boot_id or boottime < 0 or monotonic < 0:
            return self._observation("unknown", "Linux power timing state is invalid.")

        previous_boot_id = self._previous_boot_id
        previous_boottime = self._previous_boottime
        previous_monotonic = self._previous_monotonic
        self._previous_boot_id = boot_id
        self._previous_boottime = boottime
        self._previous_monotonic = monotonic

        if previous_boot_id is None:
            return self._observation("awake", "Linux is running; no prior sample exists.")
        if previous_boot_id != boot_id:
            return self._observation("boot_changed", "The Linux boot identity changed.")
        assert previous_boottime is not None
        assert previous_monotonic is not None
        boottime_delta = boottime - previous_boottime
        monotonic_delta = monotonic - previous_monotonic
        if boottime_delta < 0 or monotonic_delta < 0:
            return self._observation("unknown", "Linux power timing moved backwards.")
        if boottime_delta - monotonic_delta >= self.suspend_gap_seconds:
            return self._observation(
                "resume_detected",
                "Linux resumed after a suspended interval.",
            )
        return self._observation("awake", "Linux remained awake between samples.")

    @staticmethod
    def _observation(state: str, summary: str) -> LinuxObservation:
        return LinuxObservation(
            source=EvidenceSource.POWER,
            kind=EvidenceKind.POWER_STATE,
            state=state,
            summary=summary,
        )


def observe_linux_network(
    *,
    proc_root: Path = Path("/proc"),
    sys_root: Path = Path("/sys"),
) -> LinuxObservation:
    route_known, default_interfaces = _read_default_route_interfaces(
        proc_root / "net" / "route"
    )
    link_states = _read_link_states(sys_root / "class" / "net")

    if default_interfaces:
        route_link_states = [link_states.get(name) for name in default_interfaces]
        if route_link_states and all(state == "down" for state in route_link_states):
            return _network_observation(
                "default_route_link_down",
                "A local default route exists but its reported link is down.",
            )
        return _network_observation(
            "default_route_available",
            "Linux reports a local default route; Internet access is unverified.",
        )
    if any(state == "up" for state in link_states.values()):
        state = "link_up_no_default_route" if route_known else "link_up_route_unknown"
        summary = (
            "A non-loopback link is up without a local default route."
            if route_known
            else "A non-loopback link is up but the route table is unreadable."
        )
        return _network_observation(state, summary)
    if route_known and link_states:
        return _network_observation(
            "no_usable_link",
            "Linux reports no up non-loopback link or local default route.",
        )
    return _network_observation(
        "unknown",
        "Linux local route and link state could not be established.",
    )


def observe_user_service(
    unit: str,
    *,
    timeout_seconds: float = 5.0,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> LinuxObservation:
    if not _SERVICE_UNIT.fullmatch(unit):
        raise ValueError("systemd unit must be a bounded .service name.")
    if timeout_seconds <= 0:
        raise ValueError("systemd timeout must be greater than zero.")
    command = [
        "systemctl",
        "--user",
        "show",
        unit,
        "--property=LoadState",
        "--property=ActiveState",
        "--property=Result",
        "--no-pager",
    ]
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _service_observation(
            unit,
            "unknown",
            "could not be queried",
        )

    fields = _parse_systemd_fields(result.stdout)
    load_state = fields.get("LoadState")
    active_state = fields.get("ActiveState")
    service_result = fields.get("Result")
    if load_state == "not-found":
        return _service_observation(unit, "not_found", "is not installed")
    if result.returncode != 0 or not fields:
        return _service_observation(unit, "unknown", "could not be queried")
    if active_state == "failed" or service_result in _FAILED_RESULTS:
        return _service_observation(unit, "failed", "is failed")
    if active_state == "active":
        return _service_observation(unit, "active", "is active")
    if active_state in {"activating", "reloading"}:
        return _service_observation(unit, "activating", "is activating")
    if active_state == "deactivating":
        return _service_observation(unit, "deactivating", "is deactivating")
    if active_state == "inactive":
        return _service_observation(unit, "inactive", "is inactive")
    return _service_observation(unit, "unknown", "reported an unknown state")


def record_linux_observations(
    *,
    db_path: Path,
    worker_id: str,
    session_id: str | None,
    observations: tuple[LinuxObservation, ...],
    observed_at: float,
    ttl_seconds: int,
) -> tuple[DiagnosticEvidence, ...]:
    if ttl_seconds <= 0:
        raise ValueError("Linux evidence TTL must be greater than zero.")
    store = DiagnosticStore(db_path)
    return tuple(
        store.record_evidence(
            worker_id=worker_id,
            session_id=session_id,
            source=observation.source,
            kind=observation.kind,
            state=observation.state,
            summary=observation.summary,
            observed_at=observed_at,
            expires_at=observed_at + ttl_seconds,
        )
        for observation in observations
    )


def _parse_proc_stat(value: str) -> tuple[str, int] | None:
    closing_parenthesis = value.rfind(")")
    if closing_parenthesis < 0:
        return None
    fields = value[closing_parenthesis + 1 :].split()
    if len(fields) < 20 or len(fields[0]) != 1:
        return None
    try:
        start_ticks = int(fields[19])
    except ValueError:
        return None
    return fields[0], start_ticks


def _read_default_route_interfaces(route_path: Path) -> tuple[bool, set[str]]:
    try:
        lines = route_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False, set()
    interfaces: set[str] = set()
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 8 or fields[1] != "00000000":
            continue
        try:
            route_is_up = bool(int(fields[3], 16) & 0x1)
        except ValueError:
            continue
        if route_is_up and fields[0] != "lo":
            interfaces.add(fields[0])
    return True, interfaces


def _read_link_states(network_root: Path) -> dict[str, str]:
    try:
        interfaces = tuple(network_root.iterdir())
    except OSError:
        return {}
    states: dict[str, str] = {}
    for interface in interfaces:
        if interface.name == "lo":
            continue
        try:
            state = (interface / "operstate").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if state in {"up", "down"}:
            states[interface.name] = state
        else:
            states[interface.name] = "unknown"
    return states


def _parse_systemd_fields(value: str) -> dict[str, str]:
    allowed = {"LoadState", "ActiveState", "Result"}
    fields: dict[str, str] = {}
    for line in value.splitlines():
        key, separator, item = line.partition("=")
        if separator and key in allowed and "\x00" not in item and "\n" not in item:
            fields[key] = item.strip()
    return fields


def _network_observation(state: str, summary: str) -> LinuxObservation:
    return LinuxObservation(
        source=EvidenceSource.NETWORK,
        kind=EvidenceKind.NETWORK_STATE,
        state=state,
        summary=summary,
    )


def _service_observation(unit: str, state: str, description: str) -> LinuxObservation:
    return LinuxObservation(
        source=EvidenceSource.SERVICE,
        kind=EvidenceKind.SERVICE_STATE,
        state=state,
        summary=f"User service {unit} {description}.",
    )


def _read_boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8")


def _read_boottime() -> float:
    return time.clock_gettime(time.CLOCK_BOOTTIME)
