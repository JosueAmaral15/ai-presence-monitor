# Task 045 - Tray Agent-chat Experience

## Objective

Replace the one-shot response form with a compact desktop chat for one exact
project/agent/session conversation at a time.

## Interaction design

- profile and exact-session selectors remain explicit;
- the transcript occupies the primary surface and uses clear human/agent
  alignment, timestamps and restrained delivery labels;
- the composer supports multiline text while the Send button remains a clear
  command;
- a bounded page is loaded initially, with an explicit older-messages action;
- periodic refresh appends new rows without stealing keyboard focus or moving
  the scroll position unless the user is already at the bottom.

No nested decorative cards or explanatory feature copy is added. Empty,
loading, unavailable and failed states appear inside the transcript region.

## Transport semantics

A human message is persisted as `queued` before native dispatch. Successful
queue start becomes `dispatch_started`, never `delivered`. A later exact
session hook may move it to `delivery_confirmed`. Failure becomes `failed` with
a sanitized code and no automatic retry.

Discord questions and answers are projected through correlation IDs. Discord
remains optional; the local database is the canonical transcript.

## Validation

- offscreen PySide smoke test for construction and profile/session switching;
- pure view-model tests for ordering, labels and pagination;
- two-profile isolation and restart persistence;
- message send success/failure and no duplicate Discord projection;
- manual Linux Mint tray inspection before release promotion.

The `tray --check-chat` smoke check constructs the real dialog, processes one
GUI cycle and verifies the transcript surface before exiting. Run it against an
isolated database for automated validation and against the installed runtime
for the Linux Mint release check.
