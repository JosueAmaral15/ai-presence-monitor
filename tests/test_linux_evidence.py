from __future__ import annotations

import subprocess
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai_presence_monitor.cli import _observe_linux_state, build_parser
from ai_presence_monitor.diagnostics import (
    DiagnosticStore,
    EvidenceKind,
    EvidenceSource,
)
from ai_presence_monitor.linux_evidence import (
    LinuxObservation,
    LinuxPowerObserver,
    LinuxProcessObserver,
    observe_linux_network,
    observe_user_service,
    record_linux_observations,
)
from ai_presence_monitor.platform_integration import UnsupportedPlatformError
from ai_presence_monitor.store import PresenceStore


def write_process(
    proc_root: Path,
    *,
    pid: int = 123,
    name: str = "codex",
    state: str = "S",
    start_ticks: int = 100,
) -> None:
    process_dir = proc_root / str(pid)
    process_dir.mkdir(parents=True, exist_ok=True)
    (process_dir / "comm").write_text(f"{name}\n", encoding="utf-8")
    trailing_fields = " ".join(["0"] * 18 + [str(start_ticks)])
    (process_dir / "stat").write_text(
        f"{pid} ({name}) {state} {trailing_fields}\n",
        encoding="utf-8",
    )


def write_network(
    root: Path,
    *,
    route_lines: tuple[str, ...],
    links: dict[str, str],
) -> tuple[Path, Path]:
    proc_root = root / "proc"
    sys_root = root / "sys"
    route_path = proc_root / "net" / "route"
    route_path.parent.mkdir(parents=True)
    route_path.write_text(
        "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
        + "\n".join(route_lines),
        encoding="utf-8",
    )
    for name, state in links.items():
        interface = sys_root / "class" / "net" / name
        interface.mkdir(parents=True)
        (interface / "operstate").write_text(f"{state}\n", encoding="utf-8")
    return proc_root, sys_root


def observation(source: EvidenceSource, kind: EvidenceKind, state: str) -> LinuxObservation:
    return LinuxObservation(source, kind, state, f"Bounded {state} state.")


class LinuxProcessObserverTests(unittest.TestCase):
    def test_running_process_is_bound_to_start_ticks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root = Path(tmp) / "proc"
            write_process(proc_root)
            observer = LinuxProcessObserver(
                123,
                expected_name="codex",
                proc_root=proc_root,
            )

            self.assertEqual(observer.sample().state, "running")
            write_process(proc_root, start_ticks=200)
            self.assertEqual(observer.sample().state, "replaced")

    def test_process_states_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root = Path(tmp) / "proc"
            observer = LinuxProcessObserver(123, proc_root=proc_root)
            self.assertEqual(observer.sample().state, "missing")

            write_process(proc_root, state="Z")
            self.assertEqual(observer.sample().state, "zombie")

            (proc_root / "123" / "stat").write_text("invalid", encoding="utf-8")
            self.assertEqual(observer.sample().state, "unreadable")

    def test_expected_name_rejects_pid_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root = Path(tmp) / "proc"
            write_process(proc_root, name="python3")

            state = LinuxProcessObserver(
                123,
                expected_name="codex",
                proc_root=proc_root,
            ).sample()

            self.assertEqual(state.state, "identity_mismatch")
            self.assertNotIn("python3", state.summary)

    def test_process_arguments_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            LinuxProcessObserver(0)
        with self.assertRaisesRegex(ValueError, "bounded Linux name"):
            LinuxProcessObserver(1, expected_name="codex --unsafe")


class LinuxNetworkObserverTests(unittest.TestCase):
    def test_default_route_with_up_link_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root, sys_root = write_network(
                Path(tmp),
                route_lines=(
                    "eth0 00000000 0102A8C0 0003 0 0 100 00000000 0 0 0",
                ),
                links={"eth0": "up"},
            )

            result = observe_linux_network(proc_root=proc_root, sys_root=sys_root)

            self.assertEqual(result.state, "default_route_available")
            self.assertIn("unverified", result.summary)

    def test_one_down_default_route_does_not_hide_an_up_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root, sys_root = write_network(
                Path(tmp),
                route_lines=(
                    "eth0 00000000 0102A8C0 0003 0 0 100 00000000 0 0 0",
                    "wlan0 00000000 0102A8C0 0003 0 0 200 00000000 0 0 0",
                ),
                links={"eth0": "down", "wlan0": "up"},
            )

            result = observe_linux_network(proc_root=proc_root, sys_root=sys_root)

            self.assertEqual(result.state, "default_route_available")

    def test_link_and_route_absence_have_distinct_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root, sys_root = write_network(
                Path(tmp),
                route_lines=(),
                links={"eth0": "up"},
            )
            self.assertEqual(
                observe_linux_network(proc_root=proc_root, sys_root=sys_root).state,
                "link_up_no_default_route",
            )

            (sys_root / "class" / "net" / "eth0" / "operstate").write_text(
                "down\n",
                encoding="utf-8",
            )
            self.assertEqual(
                observe_linux_network(proc_root=proc_root, sys_root=sys_root).state,
                "no_usable_link",
            )

    def test_unreadable_local_state_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = observe_linux_network(
                proc_root=Path(tmp) / "missing-proc",
                sys_root=Path(tmp) / "missing-sys",
            )
            self.assertEqual(result.state, "unknown")


class LinuxPowerObserverTests(unittest.TestCase):
    def test_first_sample_is_awake_and_later_suspend_gap_is_detected(self) -> None:
        boot_ids = iter(("boot-a", "boot-a"))
        boottimes = iter((100.0, 120.0))
        monotonic = iter((50.0, 60.0))
        observer = LinuxPowerObserver(
            suspend_gap_seconds=5,
            boot_id_reader=lambda: next(boot_ids),
            boottime_reader=lambda: next(boottimes),
            monotonic_reader=lambda: next(monotonic),
        )

        self.assertEqual(observer.sample().state, "awake")
        self.assertEqual(observer.sample().state, "resume_detected")

    def test_boot_change_is_reported_without_raw_identifier(self) -> None:
        boot_ids = iter(("private-boot-a", "private-boot-b"))
        boottimes = iter((100.0, 101.0))
        monotonic = iter((50.0, 51.0))
        observer = LinuxPowerObserver(
            boot_id_reader=lambda: next(boot_ids),
            boottime_reader=lambda: next(boottimes),
            monotonic_reader=lambda: next(monotonic),
        )

        observer.sample()
        result = observer.sample()

        self.assertEqual(result.state, "boot_changed")
        self.assertNotIn("private-boot", result.summary)

    def test_power_read_failure_and_invalid_gap_are_safe(self) -> None:
        observer = LinuxPowerObserver(
            boot_id_reader=lambda: "",
            boottime_reader=lambda: 1,
            monotonic_reader=lambda: 1,
        )
        self.assertEqual(observer.sample().state, "unknown")
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            LinuxPowerObserver(suspend_gap_seconds=0)


class LinuxServiceObserverTests(unittest.TestCase):
    def test_systemd_query_uses_argument_vector_and_bounded_fields(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="LoadState=loaded\nActiveState=active\nResult=success\n",
                stderr="private diagnostic text",
            )

        result = observe_user_service(
            "ai-presence-monitor.service",
            timeout_seconds=2,
            runner=runner,
        )

        self.assertEqual(result.state, "active")
        self.assertEqual(calls[0][0][0:4], ["systemctl", "--user", "show", "ai-presence-monitor.service"])
        self.assertNotIn("shell", calls[0][1])
        self.assertNotIn("private diagnostic text", result.summary)

    def test_failed_missing_and_unavailable_services_are_distinct(self) -> None:
        def completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")

        failed = observe_user_service(
            "worker.service",
            runner=lambda *args, **kwargs: completed(
                "LoadState=loaded\nActiveState=failed\nResult=exit-code\n"
            ),
        )
        missing = observe_user_service(
            "worker.service",
            runner=lambda *args, **kwargs: completed(
                "LoadState=not-found\nActiveState=inactive\nResult=success\n",
                1,
            ),
        )
        unavailable = observe_user_service(
            "worker.service",
            runner=lambda *args, **kwargs: completed("private failure", 1),
        )

        self.assertEqual(failed.state, "failed")
        self.assertEqual(missing.state, "not_found")
        self.assertEqual(unavailable.state, "unknown")
        self.assertNotIn("private failure", unavailable.summary)

    def test_service_target_and_timeout_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "bounded .service"):
            observe_user_service("worker.service; shutdown")
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            observe_user_service("worker.service", timeout_seconds=0)


class LinuxEvidencePersistenceTests(unittest.TestCase):
    def test_evidence_expires_without_changing_worker_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store = PresenceStore(db_path)
            store.record_event(
                worker_id="worker-1",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            before = store.get_worker("worker-1")

            records = record_linux_observations(
                db_path=db_path,
                worker_id="worker-1",
                session_id="session-1",
                observations=(
                    observation(
                        EvidenceSource.NETWORK,
                        EvidenceKind.NETWORK_STATE,
                        "default_route_available",
                    ),
                ),
                observed_at=100,
                ttl_seconds=90,
            )

            self.assertEqual(records[0].expires_at, 190)
            self.assertEqual(store.get_worker("worker-1"), before)
            self.assertEqual(
                DiagnosticStore(db_path).list_evidence(worker_id="worker-1")[0],
                records[0],
            )


class LinuxEvidenceCliTests(unittest.TestCase):
    def test_parser_accepts_all_linux_observer_targets(self) -> None:
        args = build_parser().parse_args(
            [
                "observe-linux-state",
                "--project",
                "/tmp/project",
                "--session",
                "session-1",
                "--process-pid",
                "123",
                "--expected-process-name",
                "codex",
                "--service",
                "worker.service",
                "--watch",
                "--interval",
                "10",
                "--evidence-ttl",
                "30",
            ]
        )

        self.assertEqual(args.process_pid, 123)
        self.assertEqual(args.expected_process_name, "codex")
        self.assertEqual(args.services, ["worker.service"])
        self.assertTrue(args.watch)

    @patch("ai_presence_monitor.cli.LinuxPowerObserver")
    @patch("ai_presence_monitor.cli.observe_linux_network")
    def test_one_shot_records_evidence_without_extending_presence(
        self,
        network: object,
        power_factory: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "presence.db"
            store = PresenceStore(db_path)
            store.record_event(
                worker_id="worker-1",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            before = store.get_worker("worker-1")
            network.return_value = observation(  # type: ignore[attr-defined]
                EvidenceSource.NETWORK,
                EvidenceKind.NETWORK_STATE,
                "default_route_available",
            )
            power_factory.return_value.sample.return_value = observation(  # type: ignore[attr-defined]
                EvidenceSource.POWER,
                EvidenceKind.POWER_STATE,
                "awake",
            )
            args = make_cli_args()
            config = make_cli_config(db_path)

            with patch(
                "ai_presence_monitor.cli._identity",
                return_value=("worker-1", "computer", "codex", "protocol2"),
            ):
                with redirect_stdout(StringIO()):
                    result = _observe_linux_state(args, config)  # type: ignore[arg-type]

            self.assertEqual(result, 0)
            self.assertEqual(store.get_worker("worker-1"), before)
            evidence = DiagnosticStore(db_path).list_evidence(worker_id="worker-1")
            self.assertEqual(len(evidence), 2)

    @patch("ai_presence_monitor.cli.observe_linux_network")
    def test_dry_run_samples_once_without_database(self, network: object) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "missing" / "presence.db"
            network.return_value = observation(  # type: ignore[attr-defined]
                EvidenceSource.NETWORK,
                EvidenceKind.NETWORK_STATE,
                "default_route_available",
            )
            args = make_cli_args(dry_run=True, skip_power=True)

            with patch(
                "ai_presence_monitor.cli._identity",
                return_value=("worker-1", "computer", "codex", "protocol2"),
            ):
                with redirect_stdout(StringIO()) as output:
                    result = _observe_linux_state(  # type: ignore[arg-type]
                        args,
                        make_cli_config(db_path),
                    )

            self.assertEqual(result, 0)
            self.assertEqual(network.call_count, 1)  # type: ignore[attr-defined]
            self.assertIn("[dry-run:linux-evidence]", output.getvalue())
            self.assertFalse(db_path.exists())

    @patch("ai_presence_monitor.cli.time.sleep")
    @patch("ai_presence_monitor.cli.record_linux_observations")
    @patch("ai_presence_monitor.cli.observe_linux_network")
    @patch("ai_presence_monitor.cli.PresenceStore")
    def test_watch_stops_when_worker_becomes_idle(
        self,
        presence_store: object,
        network: object,
        record: object,
        sleep: object,
    ) -> None:
        presence_store.return_value.get_worker.side_effect = [  # type: ignore[attr-defined]
            SimpleNamespace(status="active"),
            SimpleNamespace(status="active"),
            SimpleNamespace(status="idle"),
        ]
        network.return_value = observation(  # type: ignore[attr-defined]
            EvidenceSource.NETWORK,
            EvidenceKind.NETWORK_STATE,
            "default_route_available",
        )
        record.return_value = (SimpleNamespace(evidence_id="evidence-1"),)  # type: ignore[attr-defined]
        args = make_cli_args(watch=True, skip_power=True)

        with patch(
            "ai_presence_monitor.cli._identity",
            return_value=("worker-1", "computer", "codex", "protocol2"),
        ):
            with redirect_stdout(StringIO()) as output:
                result = _observe_linux_state(  # type: ignore[arg-type]
                    args,
                    make_cli_config(Path("/tmp/not-used.db")),
                )

        self.assertEqual(result, 0)
        self.assertEqual(network.call_count, 1)  # type: ignore[attr-defined]
        self.assertEqual(record.call_count, 1)  # type: ignore[attr-defined]
        self.assertEqual(sleep.call_count, 1)  # type: ignore[attr-defined]
        self.assertIn("observer encerrado", output.getvalue())

    @patch("ai_presence_monitor.cli.record_linux_observations")
    @patch("ai_presence_monitor.cli.observe_linux_network")
    @patch("ai_presence_monitor.cli.PresenceStore")
    def test_worker_is_rechecked_after_collection(
        self,
        presence_store: object,
        network: object,
        record: object,
    ) -> None:
        presence_store.return_value.get_worker.side_effect = [  # type: ignore[attr-defined]
            SimpleNamespace(status="active"),
            SimpleNamespace(status="idle"),
        ]
        network.return_value = observation(  # type: ignore[attr-defined]
            EvidenceSource.NETWORK,
            EvidenceKind.NETWORK_STATE,
            "default_route_available",
        )
        args = make_cli_args(skip_power=True)

        with patch(
            "ai_presence_monitor.cli._identity",
            return_value=("worker-1", "computer", "codex", "protocol2"),
        ):
            with self.assertRaisesRegex(ValueError, "became inactive"):
                _observe_linux_state(  # type: ignore[arg-type]
                    args,
                    make_cli_config(Path("/tmp/not-used.db")),
                )

        self.assertFalse(record.called)  # type: ignore[attr-defined]

    @patch("ai_presence_monitor.cli.observe_linux_network")
    def test_missing_worker_fails_before_collection(self, network: object) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = make_cli_args(skip_power=True)
            with patch(
                "ai_presence_monitor.cli._identity",
                return_value=("missing-worker", "computer", "codex", "protocol2"),
            ):
                with self.assertRaisesRegex(ValueError, "Run start"):
                    _observe_linux_state(  # type: ignore[arg-type]
                        args,
                        make_cli_config(Path(tmp) / "presence.db"),
                    )

            self.assertFalse(network.called)  # type: ignore[attr-defined]

    def test_cli_validates_all_positive_timing_values(self) -> None:
        cases = (
            ("interval", 0, "interval"),
            ("evidence_ttl", 0, "TTL"),
            ("suspend_gap", 0, "suspend gap"),
            ("service_timeout", 0, "service timeout"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                args = make_cli_args(dry_run=True, **{field: value})
                with self.assertRaisesRegex(ValueError, message):
                    _observe_linux_state(  # type: ignore[arg-type]
                        args,
                        make_cli_config(Path("/tmp/not-used.db")),
                    )

    def test_cli_rejects_unsupported_or_empty_collection(self) -> None:
        args = make_cli_args(skip_network=True, skip_power=True)
        with patch("ai_presence_monitor.cli.sys.platform", "win32"):
            with self.assertRaises(UnsupportedPlatformError):
                _observe_linux_state(args, make_cli_config(Path("/tmp/unused.db")))  # type: ignore[arg-type]

        with patch("ai_presence_monitor.cli.sys.platform", "linux"):
            with self.assertRaisesRegex(ValueError, "At least one"):
                _observe_linux_state(args, make_cli_config(Path("/tmp/unused.db")))  # type: ignore[arg-type]


def make_cli_args(**overrides: object) -> Namespace:
    values: dict[str, object] = {
        "interval": None,
        "evidence_ttl": None,
        "suspend_gap": None,
        "service_timeout": None,
        "dry_run": False,
        "session": "session-1",
        "watch": False,
        "process_pid": None,
        "expected_process_name": None,
        "services": None,
        "no_services": False,
        "skip_network": False,
        "skip_power": False,
        "worker": None,
        "computer": None,
        "ai": None,
        "protocol": None,
        "scope": None,
        "project": Path("/tmp/project"),
    }
    values.update(overrides)
    return Namespace(**values)


def make_cli_config(db_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        db_path=db_path,
        computer_name="computer",
        codex_worker_id=None,
        codex_worker_scope="project",
        default_protocol="protocol2",
        linux_observer_interval_seconds=30,
        linux_evidence_ttl_seconds=90,
        linux_suspend_gap_seconds=5,
        linux_service_timeout_seconds=5,
        linux_user_services=(),
    )


if __name__ == "__main__":
    unittest.main()
