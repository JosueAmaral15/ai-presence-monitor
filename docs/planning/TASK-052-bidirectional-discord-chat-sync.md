# Task 052 - Bidirectional Discord Chat Synchronization

## Goal

Make the project-scoped agent chat and the configured Discord question channel
represent the same explicit human/agent exchange without weakening exact-session
correlation or accepting arbitrary channel messages as Codex input.

## Current gap

- `ask-user` questions and their authorized Discord replies are projected into
  the local transcript.
- messages composed in the tray are delivered to the exact Codex session but
  are not mirrored to Discord;
- `publish-agent-message` records an explicit agent response locally but does
  not publish it to Discord;
- one delivery state cannot accurately represent both the Codex transport and
  the Discord mirror.

## Implementation

1. Add optional, persisted Discord delivery metadata to each logical chat
   message: channel, external message ID, state and sanitized error code.
2. Add a Discord client operation for transcript messages that verifies the
   configured channel and disables mentions.
3. When Discord chat synchronization is enabled, mirror explicit agent
   publications and tray-composed human messages after local persistence.
4. Keep `ask-user` authoritative for Discord-to-agent input. The reply observer
   continues to require an allowed user, the configured channel, a live direct
   message reference and an unexpired question before dispatching to the exact
   session.
5. Show both primary delivery and Discord mirror state in the tray and expose
   the metadata in CLI/JSON exports.
6. Document configuration, failure semantics and the AI-worker contract.

## Safety rules

- Never copy secrets into the database, transcript, logs or Discord content.
- Persist before network I/O and never retry an uncertain Discord write
  automatically.
- A Discord mirror failure must not change a confirmed native-delivery state.
- A Discord message is not accepted as Codex input unless it is a correlated
  reply handled by the existing remote-question observer.
- Synchronization is scoped to the configured question channel and the current
  project/session conversation.

## Validation gates

1. Schema migration and restart persistence tests.
2. Client tests for content bounds, mention suppression and channel mismatch.
3. Unit tests for successful, rejected and uncertain mirrors without duplicate
   logical messages.
4. Existing remote-question correlation and exact-session tests.
5. Full lint, type, test, coverage and package checks.
6. Real Discord E2E only with an explicit unique-marker authorization; local
   automated tests do not claim external delivery.

## Rollback

Disable Discord chat synchronization. Existing messages and Discord delivery
metadata remain auditable; the local chat and correlated `ask-user` workflow
continue to operate.

## Validation record

Local validation passed 362 tests on Python 3.10, 3.11 and 3.12 with 86%
coverage. Compilation, Ruff, mypy, shell syntax, wheel/sdist build and diff
checks passed. The chat dialog constructed successfully in the real graphical
session with isolated HOME, configuration and database paths. GitHub Actions
run `41721734878` passed all three Linux jobs. A real Discord marker was not
sent without separate authorization, so promotion remains pending that E2E.
