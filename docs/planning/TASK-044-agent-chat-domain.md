# Task 044 - Persistent Agent-chat Domain and CLI

## Objective

Create a local, transport-neutral conversation model that can support the tray,
Discord correlation and explicit AI-worker publication without claiming that
Codex hooks contain assistant message text.

## Data contract

Upgrade SQLite from schema 1 to schema 2 with additive tables:

- `agent_conversations`: stable ID, worker profile, agent name, exact Codex
  session, optional title, creation/update timestamps and archive timestamp;
- `agent_messages`: append-only body plus role, direction, transport,
  correlation type/ID, delivery state, error code and timestamps.

The unique conversation identity is `(worker_id, agent_name, session_id)`.
Message bodies remain local plaintext under the existing private database file;
desktop notifications must not expose them. Correlation IDs are unique within
their source type so Discord projections are idempotent.

## Service boundary

Provide a small domain service that:

1. obtains or creates a conversation;
2. appends a message before any external transport begins;
3. updates only delivery metadata after transport;
4. lists conversations and messages using bounded pagination;
5. projects existing `RemoteQuestion` records without changing their current
   source-of-truth workflow.

## CLI boundary

Add read-only `conversations`/`messages` commands and `publish-agent-message`.
The publication command derives the worker from the current project and accepts
no arbitrary worker override. It requires an exact session and appends an
explicit agent-authored message; it does not infer text from hooks.

## Validation

- migration from an actual schema-1 shape preserves workers/questions;
- two workers using the same session never share conversations;
- duplicate correlation is idempotent;
- pagination is stable in chronological order;
- invalid roles, transports, states, empty bodies and oversized bodies fail;
- transport failure leaves an auditable failed message;
- database busy handling keeps the existing bounded SQLite behavior.

## Rollback

Schema 2 is additive. Runtime rollback to schema 1 is not allowed directly once
the database has migrated; transactional product upgrade must restore the
pre-upgrade database backup together with the old wheel.
