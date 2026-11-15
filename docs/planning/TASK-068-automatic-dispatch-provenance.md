# Task 068 - Automatic Dispatch Provenance Investigation

## Question

Determine whether the Codex prompt received while the operator was away from
the computer was generated automatically, which feature generated it and
whether later lifecycle evidence proves that the target session processed it.

## Method

1. Read only timestamps and minimal message metadata from the exact Codex
   session JSONL.
2. Correlate those timestamps with the Prompt Rule observer journal.
3. Query canonical presence events without displaying their stored payloads.
4. Inspect the persisted control file through a sanitized projection that
   excludes prompt text and session identifiers.
5. Compare every profile with a dispatch in the relevant interval because the
   observer summary aggregates profiles.
6. Preserve the distinction between transport start and later processing
   confirmation.

## Evidence Timeline - 2026-11-15

- 11:22:45 and 11:23:15: one due Prompt Rule waited for usage availability.
- 11:23:44/49: the `clarify` profile dispatched its tenth and final repeated
  occurrence. This was a separate project and must not be attributed to the
  current Codex session.
- 11:28:19: the `ai-presence-monitor` rule was waiting for usage availability.
- 11:28:44/45: the observer saw `usage_available` and recorded
  `dispatch_started` for the `ai-presence-monitor` rule.
- 11:28:51: the exact Codex session recorded `task_started`.
- 11:28:54: the session recorded a user message containing
  `continue with what you were doing.` and the canonical database recorded
  `observation:codex:UserPromptSubmit`.
- 11:29:00: the agent produced its first response.
- 11:29:28 onward: canonical `PreToolUse` and `PostToolUse` events prove active
  processing in the same project worker.
- 11:51:39: the Codex session recorded `task_complete`.

The operator reported being away from 10:00 through 12:30. The dispatch,
delivery and processing chain inside that interval therefore did not depend on
human mouse or keyboard input.

## Rule Attribution

The current profile contained two Prompt Rules and no Availability Recovery
rule. The active rule had these sanitized properties:

- trigger: `red_inactivity`;
- delay and repeat interval: 271 minutes;
- usage availability required: yes;
- repetition enabled: yes;
- occurrence count after the dispatch: 2 of 8;
- next due time after confirmed activity: 15:59:54 local time;
- exact target: the current Codex session.

The observer simultaneously reported `quota_targets=0` and
`quota_recovery=none`. Therefore the automatic behavior was a Prompt Rule whose
second condition required available usage. It was not an unavailable-to-
available transition emitted by the independent Availability Recovery feature.

## Earlier Matching Message

The same session also received the identical text at 06:53:03. The observer
was already waiting for confirmation before that task loaded, which is
consistent with a previously queued automatic prompt. The current occurrence
count and identical message support that interpretation. The aggregate journal
does not retain enough per-rule provenance to attribute the original dispatch
timestamp with the same confidence as the 11:28 event, so this earlier case is
not used as the decisive E2E evidence.

## Product Gap

The journal summary reports aggregate counts and state names for every profile.
It does not identify which profile and rule produced each dispatch. The
persisted rule also retains only its latest attempt timestamp. A future audit
event should record, without prompt text or credentials:

- event identifier and timestamp;
- profile and rule identifiers;
- source feature (`prompt_rule` or `availability_recovery`);
- trigger and provider;
- target-session fingerprint rather than raw session content;
- transport result and later canonical confirmation state.

This would make provenance directly auditable instead of reconstructing it
from four independent data sources.
