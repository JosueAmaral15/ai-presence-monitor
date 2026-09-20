# Task 025 - Immediate Product Activation

## Objective

Activate the already installed private Linux 0.8.0 runtime for controlled use
by other AI-workers while preserving explicit boundaries for higher-risk input
and proving one post-installation native continuation.

## Scope

1. Publish the completed 0.8.0 operational-upgrade record.
2. Reconcile AI-worker policy with the persistent `task-automation` control.
3. Enable persistent ordinary native continuation and retain native input.
4. Configure tray autostart for the current Linux Mint Cinnamon session.
5. Perform one exact-session native E2E with a unique marker, zero delay and no
   retry.

This task does not authorize diagnostic recovery, Discord answer dispatch, GUI
fallback, remote input or another native dispatch. It preserves the existing
activity-synchronization control without changing it.

## Authorization Model

For ordinary native continuation, the user may grant persistent permission by
enabling `task-automation`. An AI-worker must still satisfy the normative
checks: the current step is complete, the next task is concrete, and no user
question, blocker or other execution is pending.

`recover-diagnostic-incident` remains different. Every real recovery requires
its own `--authorize-once`; persistent automation permission is insufficient.
The same one-invocation boundary remains for GUI automation and manual answer
dispatch.

## Tray Autostart

Linux Mint Cinnamon loads a user XDG autostart entry after login to the
graphical session. The entry invokes the dedicated 0.8.0 environment with an
absolute `.env` path and does not contain configuration values. File mode must
be `600`.

The tray is optional and independent from the systemd monitor and Discord
reply observer. Exiting it does not stop those services, and removing the XDG
entry is sufficient to disable future automatic tray starts.

## Native E2E Gate

The test must use the exact current Codex session and a marker in this form:

```text
[AI-PRESENCE-POST-UPGRADE-E2E:<uuid>] continue
```

Required evidence:

- `task-automation` and `native-input` are enabled;
- dry-run resolves the exact worker and session without mutation;
- one real zero-delay native dispatch returns a preliminary transport state;
- the exact marker appears in the target session and was not typed by the
  human;
- a later hook from the same session records subsequent activity;
- no retry, GUI fallback, remote input or synthetic activity synchronization
  occurs; the later Codex hook records normal session activity.

## Checklist

- [x] Operational-upgrade commits published to remote `develop` and `main`.
- [x] Persistent ordinary task automation enabled and verified.
- [x] AI-worker authorization rule reconciled and documented.
- [x] Linux Mint XDG tray autostart installed, mode `600`, validated and started.
- [ ] One post-upgrade exact-session native E2E completed.
- [ ] Task branch committed and promoted after all checks pass.
