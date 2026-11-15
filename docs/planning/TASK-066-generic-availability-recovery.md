# Task 066 - Generic Availability Recovery and Delayed Session Validation

## Problem

The Token Recovery UI exposes Codex's five-hour and weekly windows as two
separate user features. Those windows are provider-specific evidence, while
the operator's intent is one policy: send a configured message when the agent
can work again. The current model therefore leaks adapter details into the
product contract and cannot naturally accommodate other providers.

A separate risk affects both recovery and Prompt Rules. A rule can become due
after 271 minutes, five hours or one week, but its stored destination may no
longer identify a session that the provider can read. Starting native transport
without a fresh target check can leave the result uncertain.

## Design

- **GRASP Information Expert**: each provider adapter interprets its own
  capacity and session metadata.
- **GRASP Low Coupling / Protected Variations**: the observer depends on
  provider protocols and normalized states, not Codex rate-limit fields.
- **GoF Strategy**: provider adapters implement capacity observation and exact
  session validation.
- **GoF Abstract Factory**: a provider factory creates a compatible capacity
  interpreter and exact-session validator family; native transport remains a
  separate policy-owned operation after validation.
- **GoF Observer**: the durable automation observer reacts to a normalized
  unavailable-to-available transition.

The first concrete family remains Codex. Gemini and Claude are extension
points, not simulated integrations: they stay unavailable until a documented,
authenticated capacity source and exact-session input transport exist.

## Action Plan

1. Replace the two user-facing Codex window controls with one persisted
   **Availability recovery** rule containing provider, exact session and text.
2. Load existing five-hour/weekly controls compatibly and migrate unambiguous
   legacy settings without causing a dispatch or losing a pending exhausted
   state.
3. Introduce provider protocols and an abstract factory; move Codex-specific
   rate-limit interpretation behind the Codex adapter.
4. Normalize Codex availability from the account-level permission first and
   use known windows only as a fail-closed fallback.
5. Validate the exact provider session immediately before delayed native
   dispatch. A missing, mismatched or unreadable session must produce a
   durable waiting/blocked state without emitting input.
6. Apply that target validation to Availability Recovery and Prompt Rules
   while preserving their independent triggers and state machines.
7. Add deterministic tests for legacy migration, one unified transition,
   provider isolation, 271-minute delay, tray restart and stale/missing exact
   sessions.
8. Update architecture, security, operator and AI-worker documentation.
9. Run focused tests, full quality gates, package build and installed-runtime
   dry-run before requesting any real delayed dispatch.

## Acceptance Criteria

- [x] The tray presents one Availability Recovery checkbox and one message.
- [x] Provider-specific quota windows are not part of the operator workflow.
- [x] Existing controls load without duplicate or premature dispatch.
- [x] Initial availability never dispatches.
- [x] An unavailable-to-available transition dispatches at most once in
  deterministic tests.
- [x] The exact session is validated immediately before delayed dispatch.
- [x] Prompt Rules remain independent and retain all existing semantics.
- [x] Gemini and Claude extension points fail closed until adapters exist.
- [x] Focused and full quality gates pass.
- [x] Runtime `0.14.0` is installed transactionally and the tray is restarted.
- [ ] A real exact-session E2E remains separately authorized and evidenced.

## Local Validation - 2026-11-15

- 398 tests and 16 subtests passed with 87% aggregate coverage;
- Ruff, mypy across 53 source files, shell syntax and `git diff --check`
  passed;
- wheel and sdist builds included the new provider module;
- the offscreen tray check constructed Controls, Prompt rules and the single
  Availability recovery tab;
- an isolated wheel install reported `ai-presence 0.14.0`, loaded the Codex
  provider factory and passed the same tray check;
- the installed transactional upgrader accepted candidate `0.14.0` and the
  preserved `0.13.1` rollback wheel in `--dry-run`, reporting `would_upgrade`;
- a deterministic 271-minute rule emitted no input while its target was
  unreadable, remained armed, and dispatched only after validation succeeded;
- a live metadata-only read matched the current exact Codex session. Its child
  status was `notLoaded`, which is expected for an independently owned GUI
  session and is not long-delay E2E evidence.

## Installed Runtime - 2026-11-15

One explicitly authorized transaction completed from `0.13.1` to `0.14.0`.
Schema 3, SQLite integrity and strict doctor passed. All three managed services
were restarted and remained `active/running` without new restarts. The
graphical tray was reloaded as one active transient-unit process, and its
offscreen preference check constructed Controls, Prompt rules and Availability
recovery. No automated prompt was sent during this maintenance operation.

## External Validation Boundary

Automated tests can prove state transitions and fail-closed session behavior.
They cannot prove that a graphical Codex session remains remotely addressable
after 271 minutes, five hours or one week. That requires a real delayed E2E
with a unique marker, later canonical hooks and no manual entry of the marker.
