# Task 038 - Disable current prompt rules

## Goal

Allow an AI worker to stop every prompt rule belonging to its own derived
profile without granting arbitrary profile mutation or changing the profile's
general automation permission.

## Contract

The new command is:

```bash
ai-presence disable-current-prompt-rules
```

It derives identity from the configured worker base, current directory,
configured scope and session environment when required. It accepts no worker,
profile, project, scope, computer, AI or session argument.

For every rule in the derived profile, it:

- sets `enabled=false` and `last_state=disabled`;
- clears arm, due, attempt, dispatch and confirmation runtime state;
- resets occurrence count;
- preserves ID, exact session, trigger, delay, prompt, repetition interval and
  occurrence limit.

It does not change `task_automation_enabled`, global defaults, another profile,
the presence database or any Codex session. Dry-run computes and reports the
number of enabled rules but writes nothing. AI workers cannot re-enable rules;
that remains a human tray action.

## Validation plan

1. Unit-test state clearing and configuration preservation.
2. Prove a derived project profile changes while a second profile does not.
3. Prove task automation remains enabled and dry-run does not persist.
4. Prove parser rejection of `--profile` and support while runtime is disabled.
5. Run quality, coverage, Python 3.10-3.12 and clean release gates.
6. Execute the installed candidate command against isolated environment and
   control files, never the operator's real controls.

## Promotion boundary

Validated source may advance to `develop`. Installing 0.10.5 or promoting it to
`main` requires the normal release decision and a separately authorized
transactional runtime upgrade; this task does not infer either operation.
