# Task 043 - Persistent Agent Chat and Usage Recovery

## Goal

Deliver two related but independently verifiable capabilities:

1. a conversation-oriented tray experience for human/agent questions and
   answers, synchronized with supported transports;
2. a durable observer that can resume an explicitly authorized exact Codex
   session after a long usage-limit window ends.

The recovery mechanism is part of this task. The complete chat is a staged
product change because the current Codex hooks prove activity but do not expose
arbitrary assistant message bodies.

## Phase 1 - Audit and recovery observer

The audit found that prompt-rule state transitions are implemented and covered:
unchanged saves retain the due time, configuration changes rearm the rule,
one-shot dispatch claims the rule before transport, and exact fresh usage
evidence is required. The operational gap was outside that state machine:

- the tray was the only recurring prompt-rule scheduler;
- `observe-codex-limits --watch` stopped after the worker became inactive;
- a five-hour or weekly wait therefore had no durable producer/consumer pair.

The dedicated `observe-prompt-rules` process closes that gap. It remains idle
without polling Codex until it finds an enabled, due, usage-gated rule for a
known profile and exact session. One sanitized account observation is then
recorded for each target and the same prompt-rule state machine is evaluated.
Blocked, unknown and missing availability never dispatch. Fresh
`usage_available` permits one claim and one native queue dispatch.

The delay remains user-defined up to 10,080 minutes. The observer does not
assume that a plan always has both five-hour and weekly windows; the Codex
aggregate availability decision is authoritative.

## Phase 2 - Conversation data model

Add append-only SQLite entities for conversations and messages. A conversation
key contains the worker profile, agent identity and exact Codex session. Each
message records direction, author role, transport, correlation ID, timestamps
and delivery state. Keep the existing `remote_questions` table authoritative
for its current workflow and project it into the transcript during migration;
do not duplicate a Discord answer as a second logical message.

Content is local by default. Desktop notifications contain metadata only.
Export and deletion require explicit human actions and documented retention
rules.

## Phase 3 - Tray chat

Replace the one-shot **Respond to message** dialog with:

- project/agent conversation list;
- exact-session selector and clear transport indicator;
- scrollable, paginated transcript with human/agent alignment and delivery
  status;
- multiline composer and send action;
- pending, unavailable, empty and failed states;
- incremental refresh that does not steal focus or move the scroll position.

Sending to Codex must retain the existing queue safeguards. A visible bubble is
not delivery proof until a later hook confirms activity. Discord remains an
optional correlated transport rather than the canonical store.

## Phase 4 - Agent publication boundary

Provide a CLI command for an AI-worker to append an explicit reply to its own
conversation. This gives the tray a complete history for messages intentionally
published through the tool. Arbitrary Codex output capture is a separate
integration: hooks cannot be treated as message content, and app-server event
capture must pass privacy, ordering, session-isolation and compatibility tests
before it is enabled.

## Validation gates

1. Unit tests for due target selection, inactive workers, blocked/available
   transitions and one-shot dispatch.
2. Existing prompt-rule regression suite and service rendering tests.
3. Full quality gate, supported Python matrix and isolated wheel installation.
4. Installed service test with a temporary control/database pair.
5. Real exact-session E2E with a unique marker the human did not type. Deliberate
   token exhaustion is not required; sanitized fixtures prove the transition,
   while a live read-only observation proves App Server compatibility.
6. Chat phases add schema migration, two-profile isolation, restart,
   pagination, Discord correlation and exact-session E2E gates.

## Rollback

Disable and remove `ai-presence-prompt-rule-observer.service`. Existing prompt
rules and controls remain persisted. Rules without the usage checkbox continue
to be evaluated by the tray. No database migration is introduced by Phase 1.
