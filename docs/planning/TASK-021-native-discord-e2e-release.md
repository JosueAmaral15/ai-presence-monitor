# Task 021 - Native Discord E2E and Linux Release

## Objective

Deploy the validated native Discord answer-routing candidate to the local Linux
runtime, recover the reply observer, prove one exactly targeted Discord-to-Codex
delivery, and promote the result through the documented Git release gates.

## Authorization

The user authorized the complete recommended sequence, automatic continuation
of this work session, one real native Discord E2E, and final use of `main` when
the gates pass. This plan interprets that authorization conservatively:

- target only the current Codex session on the local computer;
- use one generated, non-command `ACK_ONLY` marker;
- keep GUI fallback disabled;
- never retry an uncertain input automatically;
- work on a task branch, then merge to `develop`, then `main` only after the
  recorded evidence passes.

## Action Plan

### Phase 1 - Baseline and Recovery

- [x] Verify the clean `develop` baseline and create a task branch.
- [x] Read the operational and security protocols.
- [x] Register the AI-worker start event once.
- [x] Record the installed package and observer failure baseline.
- [x] Create private rollback copies of the live database and service file.
- [x] Build and install the exact task-branch candidate in the live venv.
- [x] Verify the installed CLI exposes native answer-routing options.
- [x] Recover the failed observer and complete a read-only Discord poll.

### Phase 2 - Controlled E2E

- [x] Resolve and record the exact current Codex session ID.
- [x] Generate a unique `ACK_ONLY` marker not previously used.
- [x] Stop the continuous observer to prevent competing consumers.
- [x] Invalidate the first pending question before dispatch after its marker was
      disclosed in the target conversation.
- [x] Publish one replacement Discord question using native/local delivery.
- [x] Receive one direct reply from the allowlisted user in Discord.
- [x] Run one observer delivery with no automatic retry or GUI fallback.
- [x] Confirm the replacement marker appears exactly once in the saved Codex
      session.
- [x] Confirm a later hook from that same session records
      `delivery_confirmed`.

### Phase 3 - Stabilization and Evidence

- [x] Restart the continuous observer.
- [x] Verify the unit remains active without a restart loop.
- [x] Record sanitized question, session, state, and service evidence.
- [x] Update `docs/TASKS.md`, changelog, and Task 020 validation status.
- [x] Run the complete local quality gate and review the diff for secrets.

### Phase 4 - Integration and Release

- [x] Commit the session on this task branch.
- [ ] Merge the validated task branch into `develop`.
- [ ] Push `develop` to its remote branch.
- [x] Record the temporary private Linux-only CI decision if remote CI remains
      unavailable.
- [ ] Merge validated `develop` into `main` and push `main`.
- [ ] Register the AI-worker finish event once.

## Pass Criteria

- The live CLI is the candidate version and exposes `--thread`,
  `--answer-transport`, and `--answer-destination` for `ask-user`.
- The observer accepts one correlated Discord reply and dispatches it once.
- The unique marker is visible once in the exact target session and was not
  entered directly into Codex by the human.
- The saved question reaches `delivery_confirmed` only after a hook from the
  exact stored session.
- No retry, GUI event, clipboard mutation, mouse event, or keyboard event is
  used.
- The observer returns to a stable active state.
- Local tests, coverage, lint, typing, build, and diff checks pass.

## Evidence In Progress

- Initial live package: `0.6.1`.
- E2E candidate installed in the live venv: `0.6.2`; the final `0.7.0` wheel
  was built and installed after the real integration passed.
- Initial observer state: `failed`; the last error was a temporary DNS
  resolution failure while reading Discord.
- Recovery preflight: one Discord poll completed with zero failures.
- Refreshed systemd unit started successfully and produced healthy polls before
  the controlled stop.
- Exact target session: `019f5691-c118-7370-a205-94cfde0a93d7`.
- The first question was invalidated as `expired` before dispatch because its
  marker was disclosed in the target conversation. It produced no accepted
  reply and no Codex input.
- Valid question ID: `9de8144f-3dd7-4226-92a6-e7d569755bcf`.
- Valid Discord message ID: `1548666857685385297`.
- Valid E2E marker:
  `[AI-PRESENCE-DISCORD-E2E:d8edc7f0-b348-495e-ab1f-458091cfacab] ACK_ONLY`.
- Transport/destination: `native` / `local`; GUI fallback disabled.
- Observer result: one reply accepted, one input delivered, zero delivery
  failures, zero guidance messages, and no retry.
- Stored result: `delivery_confirmed` for the exact target session; confirmation
  was recorded about ten seconds after `input_emitted`.
- The marker appeared once as the next Codex user input after the dispatching
  turn yielded. The human entered it only as a direct Discord reply.
- Local gate: 171 tests passed on Python 3.10, 3.11, and 3.12; coverage was 86%;
  Ruff, mypy, package build, and `git diff --check` passed.
- Final live package: `0.7.0`; the observer restarted from that wheel with zero
  initial systemd restarts.
- Stabilization: the final service remained `active/running` for more than ten
  minutes with `NRestarts=0` and no warning-or-higher journal entries.
- Final E2E state: passed for the valid replacement question.

## Failure Policy

Any timeout, transport rejection, missing marker, duplicate marker, wrong
session, or uncertain result stops the E2E. Do not run `dispatch-answer`, send a
second question, switch to GUI, or select another session without new explicit
authorization. Preserve the evidence and keep `main` unchanged.

## Rollback

Restore the previous installed package or retained venv and the private
database/service backups, then reset and restart the user service. Rollback
must not print or commit `.env` contents.
