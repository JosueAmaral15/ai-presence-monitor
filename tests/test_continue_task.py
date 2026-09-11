from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from test_cli import make_config

from ai_presence_monitor.cli import _check_once
from ai_presence_monitor.codex_input import CodexInputError, CodexInputResult
from ai_presence_monitor.continue_task import (
    ContinueTaskError,
    countdown,
    execute_continue_task,
)
from ai_presence_monitor.gui_answer import GuiDispatchError, WindowTarget
from ai_presence_monitor.store import PresenceStore


class FakeDispatcher:
    def __init__(self, *, fail_dispatch: bool = False):
        self.fail_dispatch = fail_dispatch
        self.captured: list[tuple[str, str | None]] = []
        self.dispatched: list[tuple[WindowTarget, str, bool]] = []

    def capture_target(
        self,
        *,
        title_pattern: str,
        window_id: str | None = None,
    ) -> WindowTarget:
        self.captured.append((title_pattern, window_id))
        return WindowTarget(
            window_id=window_id or "900",
            title="Codex - project",
            pattern=title_pattern,
        )

    def dispatch_text(
        self,
        *,
        target: WindowTarget,
        text: str,
        allow_title_change: bool = False,
    ) -> None:
        if self.fail_dispatch:
            raise GuiDispatchError("falha na emissao")
        self.dispatched.append((target, text, allow_title_change))


class FakeQueueClient:
    def __init__(self, *, available: bool = True, fail: bool = False):
        self.available = available
        self.fail = fail
        self.sent: list[dict[str, str | None]] = []

    def is_available(self) -> bool:
        return self.available

    def send(
        self,
        *,
        thread_id: str,
        text: str,
        remote: str | None = None,
        remote_auth_token_env: str | None = None,
    ) -> CodexInputResult:
        if self.fail:
            raise CodexInputError("resultado incerto")
        self.sent.append(
            {
                "thread_id": thread_id,
                "text": text,
                "remote": remote,
                "remote_auth_token_env": remote_auth_token_env,
            }
        )
        return CodexInputResult(thread_id=thread_id, remote=remote)


def continue_config(root: Path):
    return replace(
        make_config(root),
        codex_gui_window_title="Codex",
        continue_message="continue",
        continue_delay_seconds=60,
        continue_sync_activity=True,
        continue_transport="gui",
        gui_fallback_enabled=True,
    )


def set_worker_clock(
    store: PresenceStore,
    worker_id: str,
    *,
    timestamp: float,
) -> None:
    with store.session() as conn:
        conn.execute(
            """
            UPDATE workers
            SET last_signal_at = ?, last_activity_at = ?,
                last_alert_level = 'yellow', last_alert_at = ?,
                updated_at = ?
            WHERE worker_id = ?
            """,
            (timestamp, timestamp, timestamp, timestamp, worker_id),
        )


class ContinueTaskTests(unittest.TestCase):
    def test_native_transport_uses_exact_thread_without_gui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(
                make_config(root),
                continue_transport="native",
                codex_thread_id="thread-1",
                remote_input_enabled=True,
                codex_remote="wss://client.example/app-server",
                codex_remote_auth_token_env="REMOTE_TOKEN",
            )
            store = PresenceStore(config.db_path)
            worker = store.record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            queue = FakeQueueClient()

            result = execute_continue_task(
                config=config,
                worker_id=worker.worker_id,
                store=store,
                queue_client=queue,  # type: ignore[arg-type]
                wait=lambda _: None,
            )

            self.assertEqual(result.transport, "native")
            self.assertEqual(result.destination, "local")
            self.assertEqual(result.thread_id, "thread-1")
            self.assertEqual(queue.sent[0]["text"], "continue")
            self.assertIsNone(queue.sent[0]["remote"])
            self.assertIsNone(result.target)

            remote_result = execute_continue_task(
                config=config,
                worker_id=worker.worker_id,
                input_destination="client",
                sync_activity=False,
                store=store,
                queue_client=queue,  # type: ignore[arg-type]
                wait=lambda _: None,
            )
            self.assertEqual(remote_result.destination, "client")
            self.assertEqual(
                queue.sent[1]["remote"],
                "wss://client.example/app-server",
            )

    def test_native_thread_is_inferred_only_from_same_worker_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(make_config(root), continue_transport="native")
            store = PresenceStore(config.db_path)
            session = "019f5691-c118-7370-a205-94cfde0a93d7"
            other = "11111111-1111-1111-1111-111111111111"
            for worker_id, session_id in (("other", other), ("worker", session)):
                store.record_observation(
                    worker_id=worker_id,
                    computer="computer",
                    ia_name="codex",
                    protocol="protocol2",
                    source="codex:UserPromptSubmit",
                    message=f"codex hook UserPromptSubmit | session={session_id}",
                )
            queue = FakeQueueClient()

            result = execute_continue_task(
                config=config,
                worker_id="worker",
                store=store,
                queue_client=queue,  # type: ignore[arg-type]
                sync_activity=False,
                wait=lambda _: None,
            )

            self.assertEqual(result.thread_id, session)
            self.assertEqual(queue.sent[0]["thread_id"], session)
            self.assertEqual(
                [item.session_id for item in store.list_codex_sessions()],
                [session, other],
            )
            self.assertEqual(
                [
                    item.session_id
                    for item in store.list_codex_sessions(worker_id="worker")
                ],
                [session],
            )
            self.assertEqual(store.list_codex_sessions(limit=0), [])

    def test_native_failure_does_not_fall_back_to_gui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = replace(
                continue_config(Path(tmp)),
                continue_transport="auto",
                codex_thread_id="thread",
                native_input_enabled=True,
            )
            dispatcher = FakeDispatcher()
            with self.assertRaisesRegex(ContinueTaskError, "incerto"):
                execute_continue_task(
                    config=config,
                    worker_id="worker",
                    queue_client=FakeQueueClient(fail=True),  # type: ignore[arg-type]
                    dispatcher=dispatcher,  # type: ignore[arg-type]
                    sync_activity=False,
                    wait=lambda _: None,
                )
            self.assertEqual(dispatcher.captured, [])

    def test_dry_run_does_not_use_gui_store_or_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = continue_config(Path(tmp))

            result = execute_continue_task(
                config=config,
                worker_id="worker",
                dry_run=True,
                wait=lambda _: self.fail("dry-run nao deve aguardar"),
            )

            self.assertFalse(result.input_emitted)
            self.assertFalse(result.activity_synced)
            self.assertEqual(result.sync_reason, "dry_run")
            self.assertFalse(config.db_path.exists())

    def test_protocol2_emission_resets_only_activity_clock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = continue_config(root)
            store = PresenceStore(config.db_path)
            worker = store.record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
                task="task",
            )
            set_worker_clock(store, worker.worker_id, timestamp=1000)
            dispatcher = FakeDispatcher()
            waits: list[int] = []

            result = execute_continue_task(
                config=config,
                worker_id=worker.worker_id,
                store=store,
                dispatcher=dispatcher,  # type: ignore[arg-type]
                wait=waits.append,
                now=2000,
            )

            self.assertTrue(result.input_emitted)
            self.assertTrue(result.activity_synced)
            self.assertEqual(result.sync_reason, "synced")
            self.assertEqual(waits, [60])
            self.assertEqual(dispatcher.dispatched[0][1], "continue")
            updated = store.get_worker(worker.worker_id)
            assert updated is not None
            self.assertEqual(updated.last_signal_at, 1000)
            self.assertEqual(updated.last_activity_at, 2000)
            self.assertIsNone(updated.last_alert_level)
            with store.session() as conn:
                event = conn.execute(
                    "SELECT event_type FROM events ORDER BY id DESC LIMIT 1"
                ).fetchone()
            self.assertEqual(
                event["event_type"],
                "observation:automation:continue",
            )

    def test_protocol2_alert_clock_restarts_but_is_not_suppressed_forever(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = continue_config(root)
            store = PresenceStore(config.db_path)
            worker = store.record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            set_worker_clock(store, worker.worker_id, timestamp=1000)
            execute_continue_task(
                config=config,
                worker_id=worker.worker_id,
                store=store,
                dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
                wait=lambda _: None,
                now=2000,
            )

            self.assertEqual(
                _check_once(config, dry_run=True, now=2000 + 4 * 60),
                0,
            )
            self.assertEqual(
                _check_once(config, dry_run=True, now=2000 + 6 * 60),
                1,
            )

    def test_protocol1_continue_does_not_replace_public_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = continue_config(root)
            store = PresenceStore(config.db_path)
            worker = store.record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol1",
                event_type="start",
            )
            set_worker_clock(store, worker.worker_id, timestamp=1000)

            execute_continue_task(
                config=config,
                worker_id=worker.worker_id,
                store=store,
                dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
                wait=lambda _: None,
                now=2000,
            )

            updated = store.get_worker(worker.worker_id)
            assert updated is not None
            self.assertEqual(updated.last_signal_at, 1000)
            self.assertEqual(updated.last_activity_at, 2000)

    def test_gui_failure_does_not_update_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = continue_config(root)
            store = PresenceStore(config.db_path)
            worker = store.record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            set_worker_clock(store, worker.worker_id, timestamp=1000)

            with self.assertRaisesRegex(ContinueTaskError, "falha na emissao"):
                execute_continue_task(
                    config=config,
                    worker_id=worker.worker_id,
                    store=store,
                    dispatcher=FakeDispatcher(
                        fail_dispatch=True
                    ),  # type: ignore[arg-type]
                    wait=lambda _: None,
                    now=2000,
                )

            unchanged = store.get_worker(worker.worker_id)
            assert unchanged is not None
            self.assertEqual(unchanged.last_activity_at, 1000)
            self.assertEqual(unchanged.last_alert_level, "yellow")

    def test_missing_and_idle_workers_are_not_started(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = continue_config(root)
            store = PresenceStore(config.db_path)

            missing = execute_continue_task(
                config=config,
                worker_id="missing",
                store=store,
                dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
                wait=lambda _: None,
                now=2000,
            )
            self.assertEqual(missing.sync_reason, "worker_missing")
            self.assertIsNone(store.get_worker("missing"))

            worker = store.record_event(
                worker_id="idle-worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="finish",
            )
            idle = execute_continue_task(
                config=config,
                worker_id=worker.worker_id,
                store=store,
                dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
                wait=lambda _: None,
                now=2000,
            )
            self.assertEqual(idle.sync_reason, "worker_idle")
            self.assertEqual(store.get_worker(worker.worker_id).status, "idle")  # type: ignore[union-attr]

    def test_sync_can_be_disabled_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = continue_config(root)
            store = PresenceStore(config.db_path)
            worker = store.record_event(
                worker_id="worker",
                computer="computer",
                ia_name="codex",
                protocol="protocol2",
                event_type="start",
            )
            set_worker_clock(store, worker.worker_id, timestamp=1000)

            result = execute_continue_task(
                config=config,
                worker_id=worker.worker_id,
                sync_activity=False,
                store=store,
                dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
                wait=lambda _: None,
                now=2000,
            )

            self.assertEqual(result.sync_reason, "disabled")
            unchanged = store.get_worker(worker.worker_id)
            assert unchanged is not None
            self.assertEqual(unchanged.last_activity_at, 1000)

    def test_invalid_message_delay_and_title_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = continue_config(Path(tmp))
            with self.assertRaisesRegex(ContinueTaskError, "mensagem"):
                execute_continue_task(
                    config=config,
                    worker_id="worker",
                    message=" ",
                    dry_run=True,
                )
            with self.assertRaisesRegex(ContinueTaskError, "negativo"):
                execute_continue_task(
                    config=config,
                    worker_id="worker",
                    delay_seconds=-1,
                    dry_run=True,
                )
            with self.assertRaisesRegex(ContinueTaskError, "window-title"):
                execute_continue_task(
                    config=replace(config, codex_gui_window_title=None),
                    worker_id="worker",
                    dry_run=True,
                )
            with self.assertRaisesRegex(ContinueTaskError, "window-id"):
                execute_continue_task(
                    config=config,
                    worker_id="worker",
                    allow_title_change=True,
                    dry_run=True,
                )

    def test_dynamic_title_requires_explicit_window_and_is_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = FakeDispatcher()

            execute_continue_task(
                config=continue_config(Path(tmp)),
                worker_id="missing-worker",
                window_id="900",
                allow_title_change=True,
                sync_activity=False,
                dispatcher=dispatcher,  # type: ignore[arg-type]
                wait=lambda _: None,
            )

            self.assertTrue(dispatcher.dispatched[0][2])

    def test_countdown_reports_each_second(self) -> None:
        messages: list[str] = []
        sleeps: list[float] = []

        countdown(3, sleep=sleeps.append, output=messages.append)

        self.assertEqual(sleeps, [1, 1, 1])
        self.assertEqual(len(messages), 3)
        self.assertIn("3s", messages[0])
        self.assertIn("1s", messages[-1])


if __name__ == "__main__":
    unittest.main()
