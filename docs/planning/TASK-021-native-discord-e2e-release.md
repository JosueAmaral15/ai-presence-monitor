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
- [x] Publish exactly one Discord question using native/local delivery.
- [ ] Receive one direct reply from the allowlisted user in Discord.
- [ ] Run one observer poll with no automatic retry or GUI fallback.
- [ ] Confirm the marker appears exactly once in the saved Codex session.
- [ ] Confirm a later hook from that same session records
      `delivery_confirmed`.

### Phase 3 - Stabilization and Evidence

- [ ] Restart the continuous observer.
- [ ] Verify the unit remains active without a restart loop.
- [ ] Record sanitized question, session, state, and service evidence.
- [ ] Update `docs/TASKS.md`, changelog, and Task 020 validation status.
- [x] Run the complete local quality gate and review the diff for secrets.

### Phase 4 - Integration and Release

- [ ] Commit the session on this task branch.
- [ ] Merge the validated task branch into `develop`.
- [ ] Push `develop` to its remote branch.
- [ ] Record the temporary private Linux-only CI decision if remote CI remains
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
- Candidate installed in the live venv: `0.6.2`.
- Initial observer state: `failed`; the last error was a temporary DNS
  resolution failure while reading Discord.
- Recovery preflight: one Discord poll completed with zero failures.
- Refreshed systemd unit started successfully and produced healthy polls before
  the controlled stop.
- Exact target session: `019f5691-c118-7370-a205-94cfde0a93d7`.
- Question ID: `1b629b56-2cd8-47f1-9ddb-95b52591a202`.
- Discord message ID: `1548663978215870545`.
- E2E marker:
  `[AI-PRESENCE-DISCORD-E2E:a5f80722-e483-4de2-a804-0e3bfa32af3d] ACK_ONLY`.
- Transport/destination: `native` / `local`; GUI fallback disabled.
- Local gate: 171 tests passed, coverage 86%, Ruff and mypy passed, package
  build passed, and `git diff --check` passed.
- Current E2E state: pending direct Discord reply; no input has been emitted.

## Failure Policy

Any timeout, transport rejection, missing marker, duplicate marker, wrong
session, or uncertain result stops the E2E. Do not run `dispatch-answer`, send a
second question, switch to GUI, or select another session without new explicit
authorization. Preserve the evidence and keep `main` unchanged.

## Rollback

Restore the previous installed package or retained venv and the private
database/service backups, then reset and restart the user service. Rollback
must not print or commit `.env` contents.
