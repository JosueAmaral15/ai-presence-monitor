# Task 020 - Native Discord Answer Routing

## Objective

Return an authorized Discord answer to the exact Codex session that created the
question without using the user's mouse or keyboard. Preserve GUI delivery as
an explicit fallback and keep all delivery evidence conservative.

## Current Limitation

The Discord observer correlates the human reply with a stored question, but
automatic delivery currently depends on the captured GUI window. A hook can
then confirm any recent GUI delivery for the same worker, even when several
Codex sessions share that worker identity.

This makes focus and window state part of the delivery path and does not bind
the reply to an immutable Codex session.

## Design Decisions

- Capture and persist the exact target session when the question is created.
- Select one transport per question: `native`, `gui`, or `store`.
- Prefer `native`; never silently downgrade to GUI after a native failure.
- Resolve a native target from an explicit `--thread`, the current Codex
  environment, a configured control target, or one fresh and unambiguous hook
  session from the same worker, in that order.
- Fail closed when a requested native target is missing or ambiguous.
- Use the existing `CodexQueueClient`; never invoke a shell.
- Store only the remote endpoint and token variable name, never the token.
- Treat `dispatch_started` and `input_emitted` as preliminary states.
- Confirm a native delivery only from a later hook with the same worker and
  exact session ID.
- Do not retry automatically after timeout, detached dispatch, observer
  restart, or any other uncertain result.

## Session Action Plan

### Phase 1 - Baseline and Contract

- [x] Verify a clean baseline and create a dedicated task branch.
- [x] Read the AI-worker, security, and user-tool protocols.
- [x] Inspect the current Discord, SQLite, Codex input, hook, and CLI paths.
- [x] Record this action plan before changing application source.

### Phase 2 - Persistent Target and Migration

- [x] Extend each remote question with transport, exact session, destination,
      remote endpoint, and remote token variable name.
- [x] Add a backward-compatible SQLite migration for existing databases.
- [x] Preserve existing GUI target fields for explicit fallback questions.

### Phase 3 - Native Delivery

- [x] Add a dispatcher contract for native and GUI strategies plus a
      store-only path with no dispatcher side effect.
- [x] Resolve and freeze the destination when `ask-user` creates the question.
- [x] Dispatch a valid Discord answer through `codex queue` when transport is
      native.
- [x] Keep manual retry explicit and transport-aware.
- [x] Expose transport and target information in CLI output without secrets.

### Phase 4 - Correlated Confirmation

- [x] Extract the hook session ID as structured data.
- [x] Require the stored target session for native delivery confirmation.
- [x] Preserve worker-only confirmation for legacy GUI records.
- [x] Prevent an unrelated session hook from confirming native input.

### Phase 5 - Configuration and Documentation

- [x] Add safe defaults and examples to `.env.example`.
- [x] Update the Discord guide, AI-worker protocol, architecture, security
      checklist, documentation index, changelog, and task register.
- [x] Document local and remote native destinations, explicit GUI fallback,
      state semantics, failure handling, and rollback.

### Phase 6 - Verification and Integration

- [x] Add migration, target-resolution, dispatcher, duplicate-prevention,
      session-confirmation, and CLI tests.
- [x] Run focused tests while implementing.
- [x] Run the complete quality gate, build, and isolated installation checks.
- [x] Review the diff for secrets, unrelated changes, and documentation drift.
- [ ] Commit the completed session on the task branch.
- [ ] Merge into `develop` only when the implementation is functional and all
      local gates pass.
- [ ] Keep `main` unchanged until release gates permit promotion.

## Acceptance Criteria

- A Discord reply is routed to the session stored with its question.
- No focused window, mouse movement, clipboard mutation, or keyboard event is
  required for native delivery.
- Missing or ambiguous native targets fail before the question is published.
- Native failure never triggers GUI fallback or automatic retry.
- A hook from another session cannot produce `delivery_confirmed`.
- Existing databases migrate without losing remote questions.
- Store-only and explicit GUI modes remain available.
- CLI and documentation do not expose tokens or claim processing from a
  preliminary transport state.

## Real E2E Gate

A real E2E is deliberately outside the automated test run. It requires a new,
explicit authorization for one Discord question and one exact Codex session.
The answer must contain a unique marker that the human agrees not to type or
paste manually. Success requires one visible delivery in the saved target, a
later hook from that same session, and no retry.

## Validation Result

- Focused routing and interactive suites passed during implementation.
- The complete suite passed with 171 tests on Python 3.12.
- Coverage was 86%, above the 80% project gate.
- The same 171 tests passed on Python 3.10, 3.11, and 3.12.
- Compilation, Ruff, mypy, package build, and `git diff --check` passed.
- The wheel installed in an isolated Python 3.12 environment.
- Installed `ask-user --help` exposed transport, session, and destination.
- An installed dry-run selected native local delivery without network, SQLite,
  GUI input, or a real Codex queue invocation.
- No real Discord question or Codex input was sent in this session. That E2E
  remains a publication gate requiring separate, exact authorization.

## Rollback

Set the answer transport to `store` to continue recording Discord replies
without delivering them. Existing GUI delivery can be selected explicitly
after reviewing the target window. The migration adds nullable columns and
does not remove legacy data.
