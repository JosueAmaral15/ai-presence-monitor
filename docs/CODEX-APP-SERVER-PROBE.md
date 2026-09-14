# Codex App Server Probe

## Purpose

`probe-codex-app-server` is a bounded diagnostic command for checking which
Codex state can be observed from a separate local App Server process. It does
not send a prompt, start or steer a turn, use `codex queue`, control the GUI,
write diagnostic evidence, update presence clocks, or notify Discord.

The command exists to support Task 022 implementation decisions. It is not a
continuous production observer.

## Safe Metadata Probe

Use the exact persisted Codex thread UUID:

```bash
ai-presence probe-codex-app-server \
  --thread '019f0000-0000-7000-8000-000000000000' \
  --json
```

This starts a dedicated `codex app-server --stdio` child and performs only:

1. `initialize` and `initialized`;
2. `thread/read` with `includeTurns=false`;
3. `account/rateLimits/read` with reset-credit details excluded;
4. clean child-process termination.

Output is restricted to the requested thread ID, thread status and documented
active flags, usage permission, allowlisted limit classifications, aggregate
limit windows, credit booleans and spend-control state. Account IDs, balances,
thread names, previews, turns, items, prompts, messages, commands and raw errors
are discarded.

## Subscription Feasibility Probe

An explicit positive duration additionally attempts an observational
`thread/resume` with `excludeTurns=true`, waits for sanitized events, and calls
`thread/unsubscribe`:

```bash
ai-presence probe-codex-app-server \
  --thread '019f0000-0000-7000-8000-000000000000' \
  --subscribe-seconds 10 \
  --json
```

This mode is for controlled development only. `thread/resume` loads or rejoins
a thread in that App Server process even though the probe never starts a turn.
Do not schedule it as a background observer.

## Verified Result on Codex CLI 0.154.0

The 2026-09-13/14 local feasibility test established:

| Capability | Result |
| --- | --- |
| Initialize a separate stdio App Server | Passed |
| Read exact persisted thread metadata without turns | Passed |
| Read structured account rate-limit state | Passed |
| See the GUI-owned thread as loaded in the child | Not available; status was `notLoaded` |
| Resume the active GUI-owned thread in the child | Rejected with `-32600`, sanitized as `thread_already_active` |
| Receive GUI-owned live events in the child | Not testable because subscription was rejected |

This means a separate stdio process is suitable for polling persisted metadata
and rate-limit state, but it is not an exact-session live event observer for a
thread already owned by the current Codex GUI/CLI process.

Live event observation remains viable only when the monitored session and the
observer share the same App Server connection boundary, for example through a
managed daemon or another supported multiplexed endpoint. The current Codex
session was not hosted by the managed daemon, and no daemon control socket was
running during the test.

## Events the Sanitizer Recognizes

The prototype can retain only these bounded event facts when a compatible
shared subscription becomes available:

- thread status and `waitingOnApproval` / `waitingOnUserInput` flags;
- turn start/completion status and allowlisted `codexErrorInfo` type;
- upstream HTTP status code for documented transport errors;
- aggregate total/last token counts and model context-window size;
- context-compaction start/completion markers;
- the method name of documented approval or user-input requests.

All other notifications are dropped. High-volume message, reasoning, command,
patch, plan, transcript and audio deltas are opted out during initialization.
Events from a different thread ID are also dropped.

## Instructions for AI Workers

1. Use this command only for diagnosis or an explicitly assigned Task 022 test.
2. Require the exact thread UUID; never infer a target from a window title.
3. Prefer the default zero-second mode.
4. Do not use `--subscribe-seconds` automatically or retry a failed resume.
5. Treat `notLoaded` as the child process state, not proof that Codex is closed.
6. Treat `thread_already_active` as an ownership boundary, not inactivity.
7. Never claim live observation unless a sanitized event from the exact thread
   was received through a shared connection during the test.
8. Do not translate a failed probe into `continue`, recovery, Discord, or alarm
   actions.

## Production Account-limit Evidence

Task 022 Phase 3 implements the bounded polling half of the architecture. Start
the exact project worker first, then perform one read:

```bash
ai-presence observe-codex-limits \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA
```

For an explicitly assigned continuous observer:

```bash
ai-presence observe-codex-limits \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA \
  --watch
```

The command calls only `account/rateLimits/read`, persists a sanitized and
expiring fact, and never updates presence clocks. The default is one-shot.
`--watch` revalidates the exact worker before every poll and stops when the
worker becomes idle. A dry run performs the safe read but does not create or
write the SQLite database.

This observer does not diagnose the final cause, open an incident, send a
notification, play an alarm, dispatch input or recover a session. In
particular, unavailable credits do not override `ordinary_usage_allowed=true`.

## Remaining Architecture Boundary

Codex evidence collection remains split into two sources:

- implemented safe account-limit polling plus existing same-session hooks;
- a live App Server event adapter that remains disabled until sessions are
  intentionally hosted through a shared managed endpoint and validated E2E.

The official protocol defines `thread/read` as a non-subscribing stored-thread
read and `thread/resume` as the operation that loads or rejoins a thread and
subscribes the connection. See the [Codex App Server documentation](https://learn.chatgpt.com/docs/app-server.md)
and its [events section](https://learn.chatgpt.com/docs/app-server#events).
