from __future__ import annotations

import json
import unittest
from dataclasses import asdict
from typing import cast
from unittest.mock import patch

from ai_presence_monitor.cli import _probe_codex_app_server, build_parser
from ai_presence_monitor.codex_app_server import (
    CodexAppServerClient,
    CodexAppServerError,
    CodexAppServerProbeResult,
    JsonRpcTransport,
    RateLimitSnapshot,
    RateLimitWindowSnapshot,
    SanitizedCodexEvent,
    ThreadSnapshot,
    probe_codex_app_server,
    read_codex_rate_limits,
    sanitize_codex_message,
)


class FakeTransport:
    def __init__(self, responses: list[dict[str, object] | BaseException]) -> None:
        self.responses = list(responses)
        self.sent: list[dict[str, object]] = []
        self.closed = False

    def send(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    def receive(self, timeout_seconds: float) -> dict[str, object]:
        if not self.responses:
            raise TimeoutError
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


def initialized_client(
    responses: list[dict[str, object] | BaseException],
) -> tuple[CodexAppServerClient, FakeTransport]:
    transport = FakeTransport([{"id": 1, "result": {}}] + responses)
    client = CodexAppServerClient(cast(JsonRpcTransport, transport))
    client.initialize()
    return client, transport


class CodexAppServerClientTests(unittest.TestCase):
    def test_initialize_uses_bounded_capabilities_and_initialized_notification(self) -> None:
        client, transport = initialized_client([])

        self.assertIsNotNone(client)
        initialize = transport.sent[0]
        self.assertEqual(initialize["method"], "initialize")
        params = cast(dict[str, object], initialize["params"])
        capabilities = cast(dict[str, object], params["capabilities"])
        opted_out = cast(list[str], capabilities["optOutNotificationMethods"])
        self.assertIn("item/agentMessage/delta", opted_out)
        self.assertIn("item/commandExecution/outputDelta", opted_out)
        self.assertEqual(
            transport.sent[1],
            {"method": "initialized", "params": {}},
        )

    def test_forbidden_method_is_rejected_before_transport_send(self) -> None:
        client, transport = initialized_client([])
        sent_before = list(transport.sent)

        with self.assertRaisesRegex(CodexAppServerError, "not allowed"):
            client.request_read_only("turn/start", {"input": "continue"})

        self.assertEqual(transport.sent, sent_before)

    def test_unsafe_allowed_method_parameters_are_rejected_before_send(self) -> None:
        client, transport = initialized_client([])
        sent_before = list(transport.sent)

        unsafe_requests = (
            ("thread/read", {"threadId": "thread-1", "includeTurns": True}),
            (
                "thread/resume",
                {
                    "threadId": "thread-1",
                    "excludeTurns": True,
                    "history": [{"text": "private"}],
                },
            ),
            ("account/rateLimits/read", {"excludeResetCreditDetails": False}),
            ("thread/unsubscribe", {"threadId": "invalid\nthread"}),
        )

        for method, params in unsafe_requests:
            with self.subTest(method=method):
                with self.assertRaisesRegex(CodexAppServerError, "Unsafe parameters"):
                    client.request_read_only(method, params)

        self.assertEqual(transport.sent, sent_before)

    def test_reads_only_thread_metadata_and_sanitized_rate_limits(self) -> None:
        thread_id = "019f5691-c118-7370-a205-94cfde0a93d7"
        client, transport = initialized_client(
            [
                {
                    "id": 2,
                    "result": {
                        "thread": {
                            "id": thread_id,
                            "name": "private title",
                            "preview": "private transcript",
                            "turns": [{"items": [{"text": "private"}]}],
                            "status": {
                                "type": "active",
                                "activeFlags": [
                                    "waitingOnUserInput",
                                    "unknownFutureFlag",
                                ],
                            },
                        }
                    },
                },
                {
                    "id": 3,
                    "result": {
                        "accountId": "private-account",
                        "ordinaryUsageAllowed": False,
                        "rateLimits": {
                            "planType": "plus",
                            "rateLimitReachedType": "rate_limit_reached",
                            "primary": {
                                "usedPercent": 100,
                                "resetsAt": 200,
                                "windowDurationMins": 300,
                            },
                            "secondary": None,
                            "credits": {
                                "hasCredits": True,
                                "unlimited": False,
                                "balance": "private-balance",
                            },
                            "spendControlReached": False,
                        },
                    },
                },
            ]
        )

        thread = client.read_thread(thread_id)
        limits = client.read_rate_limits()

        self.assertEqual(thread.status, "active")
        self.assertEqual(thread.active_flags, ("waitingOnUserInput",))
        self.assertFalse(limits.ordinary_usage_allowed)
        self.assertEqual(limits.reached_type, "rate_limit_reached")
        self.assertEqual(limits.primary.used_percent if limits.primary else None, 100)
        serialized = json.dumps({"thread": asdict(thread), "limits": asdict(limits)})
        self.assertNotIn("private", serialized)
        self.assertEqual(
            cast(dict[str, object], transport.sent[2]["params"]),
            {"threadId": thread_id, "includeTurns": False},
        )
        self.assertEqual(
            cast(dict[str, object], transport.sent[3]["params"]),
            {"excludeResetCreditDetails": True},
        )

    def test_observation_sanitizes_events_and_always_unsubscribes(self) -> None:
        thread_id = "019f5691-c118-7370-a205-94cfde0a93d7"
        client, transport = initialized_client(
            [
                {
                    "method": "thread/status/changed",
                    "params": {
                        "threadId": thread_id,
                        "status": {
                            "type": "active",
                            "activeFlags": ["waitingOnApproval"],
                        },
                    },
                },
                {"id": 2, "result": {"thread": {"id": thread_id}}},
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": thread_id,
                        "turn": {
                            "id": "turn-1",
                            "status": "failed",
                            "items": [{"text": "private transcript"}],
                            "error": {
                                "message": "private failure",
                                "additionalDetails": "private details",
                                "codexErrorInfo": {
                                    "httpConnectionFailed": {"httpStatusCode": 503}
                                },
                            },
                        },
                    },
                },
                TimeoutError(),
                {"id": 3, "result": {}},
            ]
        )

        events = client.observe_thread(thread_id, 0.01)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].active_flags, ("waitingOnApproval",))
        self.assertEqual(events[1].error_type, "httpConnectionFailed")
        self.assertEqual(events[1].http_status_code, 503)
        self.assertNotIn("private", json.dumps([asdict(event) for event in events]))
        self.assertEqual(transport.sent[-1]["method"], "thread/unsubscribe")

    def test_sanitizer_keeps_only_aggregate_usage_and_compaction_marker(self) -> None:
        usage = sanitize_codex_message(
            {
                "method": "thread/tokenUsage/updated",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "tokenUsage": {
                        "total": {"totalTokens": 400, "inputTokens": 300},
                        "last": {"totalTokens": 40, "outputTokens": 20},
                        "modelContextWindow": 1000,
                    },
                    "message": "private",
                },
            }
        )
        compaction = sanitize_codex_message(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "item": {"type": "contextCompaction", "text": "private"},
                },
            }
        )
        ignored = sanitize_codex_message(
            {
                "method": "item/agentMessage/delta",
                "params": {"delta": "private"},
            }
        )

        self.assertEqual(usage.total_tokens if usage else None, 400)
        self.assertEqual(usage.last_tokens if usage else None, 40)
        self.assertEqual(compaction.method if compaction else None, "contextCompaction")
        self.assertIsNone(ignored)

    def test_probe_closes_transport(self) -> None:
        thread_id = "019f5691-c118-7370-a205-94cfde0a93d7"
        transport = FakeTransport(
            [
                {"id": 1, "result": {}},
                {
                    "id": 2,
                    "result": {"thread": {"id": thread_id, "status": {"type": "idle"}}},
                },
                {"id": 3, "result": {"rateLimits": {}}},
            ]
        )

        result = probe_codex_app_server(
            thread_id,
            transport_factory=lambda executable: cast(JsonRpcTransport, transport),
        )

        self.assertEqual(result.thread.status, "idle")
        self.assertTrue(transport.closed)

    def test_rate_limit_reader_does_not_require_or_read_a_thread(self) -> None:
        transport = FakeTransport(
            [
                {"id": 1, "result": {}},
                {
                    "id": 2,
                    "result": {
                        "ordinaryUsageAllowed": True,
                        "rateLimits": {"planType": "plus"},
                    },
                },
            ]
        )

        limits = read_codex_rate_limits(
            transport_factory=lambda executable: cast(JsonRpcTransport, transport),
        )

        self.assertTrue(limits.ordinary_usage_allowed)
        self.assertEqual(
            [message["method"] for message in transport.sent],
            ["initialize", "initialized", "account/rateLimits/read"],
        )
        self.assertTrue(transport.closed)

    def test_unknown_rate_limit_type_is_collapsed_to_bounded_fallback(self) -> None:
        transport = FakeTransport(
            [
                {"id": 1, "result": {}},
                {
                    "id": 2,
                    "result": {
                        "ordinaryUsageAllowed": True,
                        "rateLimits": {
                            "rateLimitReachedType": "future_private_limit"
                        },
                    },
                },
            ]
        )

        limits = read_codex_rate_limits(
            transport_factory=lambda executable: cast(JsonRpcTransport, transport),
        )

        self.assertEqual(limits.reached_type, "other")

    def test_json_rpc_error_does_not_expose_server_message(self) -> None:
        client, _ = initialized_client(
            [
                {
                    "id": 2,
                    "error": {"code": -32000, "message": "private server detail"},
                }
            ]
        )

        with self.assertRaises(CodexAppServerError) as raised:
            client.read_thread("thread-1")

        self.assertIn("-32000", str(raised.exception))
        self.assertNotIn("private", str(raised.exception))

    def test_active_thread_error_is_classified_without_raw_message(self) -> None:
        client, _ = initialized_client(
            [
                {
                    "id": 2,
                    "error": {
                        "code": -32600,
                        "message": (
                            "thread private-session is already active in a private place"
                        ),
                    },
                }
            ]
        )

        with self.assertRaises(CodexAppServerError) as raised:
            client.request_read_only(
                "thread/resume",
                {"threadId": "thread-1", "excludeTurns": True},
            )

        message = str(raised.exception)
        self.assertIn("reason=thread_already_active", message)
        self.assertNotIn("private", message)

    def test_cross_thread_subscription_event_is_discarded(self) -> None:
        event = sanitize_codex_message(
            {
                "method": "thread/status/changed",
                "params": {
                    "threadId": "thread-2",
                    "status": {"type": "active", "activeFlags": []},
                },
            },
            expected_thread_id="thread-1",
        )

        self.assertIsNone(event)


class CodexAppServerCliTests(unittest.TestCase):
    def test_parser_accepts_bounded_probe_options(self) -> None:
        args = build_parser().parse_args(
            [
                "probe-codex-app-server",
                "--thread",
                "thread-1",
                "--subscribe-seconds",
                "2.5",
                "--request-timeout",
                "3",
                "--codex-executable",
                "/opt/codex",
                "--json",
            ]
        )

        self.assertEqual(args.thread, "thread-1")
        self.assertEqual(args.subscribe_seconds, 2.5)
        self.assertEqual(args.request_timeout, 3.0)
        self.assertEqual(args.codex_executable, "/opt/codex")
        self.assertTrue(args.json)

    @patch("ai_presence_monitor.cli.probe_codex_app_server")
    def test_cli_prints_only_sanitized_json(self, probe: object) -> None:
        result = CodexAppServerProbeResult(
            thread=ThreadSnapshot("thread-1", "idle", ()),
            rate_limits=RateLimitSnapshot(
                ordinary_usage_allowed=True,
                reached_type=None,
                plan_type="plus",
                primary=RateLimitWindowSnapshot(10, 20, 300),
                secondary=None,
                has_credits=True,
                unlimited_credits=False,
                spend_control_reached=False,
            ),
            subscription_seconds=0,
            events=(SanitizedCodexEvent(method="turn/started", turn_id="turn-1"),),
        )
        cast(object, probe).return_value = result  # type: ignore[attr-defined]
        args = build_parser().parse_args(
            ["probe-codex-app-server", "--thread", "thread-1", "--json"]
        )

        with patch("builtins.print") as print_mock:
            return_code = _probe_codex_app_server(args)

        self.assertEqual(return_code, 0)
        output = print_mock.call_args.args[0]
        parsed = json.loads(output)
        self.assertEqual(parsed["thread"]["status"], "idle")
        self.assertNotIn("message", output)


if __name__ == "__main__":
    unittest.main()
