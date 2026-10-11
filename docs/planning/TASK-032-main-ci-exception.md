# Task 032 - Main Promotion with a Local CI Exception

## Decision

The owner explicitly authorized a manual `develop` to `main` promotion on
2026-10-09. The authorization covers a documented, version-specific exception
for the GitHub-hosted Quality gate. It does not authorize a tag, GitHub release,
asset upload, payment retry or future release exception.

## Reason

GitHub Actions run
[`37913742672`](https://github.com/JosueAmaral15/ai-presence-monitor/actions/runs/37913742672)
created three Linux jobs for Python 3.10, 3.11 and 3.12, but each job executed
zero steps. Every check annotation states that the account is locked due to a
billing issue. The failure is external to the workflow and supplies no test
evidence.

The owner cannot clear the account-level billing lock in this session. Waiting
would leave the installed and validated observer fix absent from `main` even
though `develop` contains the exact source already running on this Linux host.

## Scope

- Applies only to promoting version 0.10.2 from the current `develop` history.
- Linux remains the only supported production platform.
- Windows code remains preserved, disabled and unsupported.
- Hosted CI remains pending and must not be described as passing.
- No tag, release or release asset is created under this authorization.
- No `.env`, database, control file, logs or private transaction manifest may
  be committed or bundled.

## Substitute Gates

Promotion requires all of the following on the exact candidate commit:

1. Clean Git source and no divergence from remote `develop`.
2. Complete local quality gate: unit tests, at least 80% aggregate coverage,
   Ruff, mypy, compileall, shell syntax and package build.
3. Release gate with Python 3.10, 3.11 and 3.12, clean bundle construction and
   offline verification.
4. Installed runtime 0.10.2 with current, integral SQLite schema.
5. Strict doctor success for controls, hooks, Codex queue, main monitor, reply
   observer and tray autostart.
6. Reply observer active with no restart loop and no pending correlated answer.
7. A fresh read of the hosted run proving zero executed steps and the same
   account-level billing annotation.
8. Fast-forward-only promotion. Any divergence, uncertain input dispatch or
   failed gate stops the operation.

## Existing Evidence

- Source implementation commit:
  `3725479aa57b961206386c351d8affb5ad156cb9`.
- The implementation previously passed 321 tests, 86% aggregate coverage and
  the supported Python 3.10-3.12 matrix.
- Transactional upgrade from 0.10.0 to 0.10.1 completed with a private mode
  `0600` manifest and the exact rollback wheel preserved.
- Wheel SHA-256:
  `07c224591c1a34ab9f26ff925687f27c04346c5cf5242f478ffc2d2ba12f12c8`.
- Live recovery completed with nine successful Discord polls, zero pending
  questions, one stable observer PID and `NRestarts=0`.
- Post-recovery strict doctor reported every check `ok`.

Existing evidence is context only. The substitute gates must be rerun after
this exception plan is committed and before promotion.

## Pre-promotion Failure and Required Correction

The first substitute gate stopped the promotion because strict doctor found
the reply observer failed again. Discord had closed an HTTP connection without
a response. Python raised `http.client.RemoteDisconnected`, which escaped the
0.10.1 retryable network classification. Four systemd restarts then exhausted
the unit start limit.

The operational database remained integral with zero pending questions, and
Discord DNS and the public API gateway were reachable during diagnosis. No
answer was accepted or dispatched. Promotion remains blocked until version
0.10.2 classifies connection-level read failures as transient, passes every
substitute gate, is installed transactionally and sustains live polling.

## Substitute Gate Evidence

- Correction source commit: `54aee46136a9a96eb4efb44fad7093d07a1eb008`.
- The complete quality gate passed 321 tests, 86% aggregate coverage, Ruff,
  mypy, compileall, shell syntax and package build.
- The same 321 tests passed on Python 3.10, 3.11 and 3.12.
- The clean bundle and offline verifier identify version 0.10.2, the exact
  source commit above and `source_dirty=false`.
- Candidate wheel SHA-256:
  `7a340fb8c45c91202bdbb0e7d5bcda3067f643f77adfd4509dcafa155dadbbf7`.
- Candidate sdist SHA-256:
  `00356dc2b83071a3e8ba70b9714d044fed412cabb240e6d42a1536d6855c821a`.
- The transactional dry-run reported `would_upgrade` from 0.10.1 to 0.10.2.
- A real isolated poll read 13 Discord messages and accepted, guided and
  dispatched zero messages using a temporary database.
- The authorized transaction completed in private manifest
  `upgrade-0.10.1-to-0.10.2-20261009-142523-11c558e5/manifest.json`. Its mode is
  `0600`, target hash matches the wheel above and rollback hash matches the
  validated 0.10.1 wheel.
- The installed runtime reports 0.10.2. Schema 1 is current and integral, and
  the operational database contains zero pending questions.
- The observer completed 14 consecutive real polls over more than one minute,
  remained on one PID and reported `NRestarts=0`. No message was accepted,
  guided or dispatched.
- One strict-doctor invocation observed a transient `codex queue` probe
  timeout after the long local gate. The direct probe then completed in 0.11
  seconds, and the immediate strict-doctor rerun reported every check `ok`.
- Hosted run
  [`37913841059`](https://github.com/JosueAmaral15/ai-presence-monitor/actions/runs/37913841059)
  is the latest Quality run for `develop` before promotion. Its three Linux
  jobs each executed zero steps and each annotation reports the account-level
  billing lock.

## Residual Risk

Local tests cannot prove GitHub runner image behavior, hosted permissions,
workflow token behavior or GitHub service integration. The promoted commit may
therefore continue to display a failed Quality check. This is accepted only
because the hosted jobs never started and the repository currently has no
branch protection or ruleset requiring that check.

## Promotion Result

The authorized promotion completed on 2026-10-11 without a tag or release:

- task branch `codex/task-032-main-ci-exception` was published at
  `3201a773e722734099b3d05515c569e8ff3083ca`;
- `develop` advanced by fast-forward from
  `76d86dbbf2bd06e1edcc85d947d82ea926157666` to the same candidate;
- `main` advanced by fast-forward from
  `db7e8f7661f26bf66941370d75ab76042ab5f956` to the same candidate;
- Git accepted both pushes and a subsequent remote fetch confirmed the
  expected ancestry;
- post-promotion Quality run
  [`38146996990`](https://github.com/JosueAmaral15/ai-presence-monitor/actions/runs/38146996990)
  targets the first closure-record commit. Its three Linux jobs again executed
  zero steps, and each job reports the same account-level billing lock;
- the final release gate for the clean candidate passed 321 tests with 86%
  aggregate coverage, passed the same 321 tests on Python 3.10, 3.11 and
  3.12, and verified a clean 0.10.2 bundle;
- the installed runtime remained at 0.10.2, strict doctor returned only `ok`
  checks, and the reply observer remained active with `NRestarts=0` and no
  pending question.

The documentation-only closure record is promoted through the same
fast-forward path after `git diff --check` and the local quality gate. Hosted
Quality remains an external non-pass until GitHub actually starts its jobs.

## Follow-up

When the account lock is cleared:

1. dispatch or rerun Quality for the exact promoted `main` commit;
2. require all Linux matrix jobs to execute real steps and pass;
3. record the run URL and close Task 031;
4. retain this file as an audit record rather than rewriting the exception as
   a hosted success.
