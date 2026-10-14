# Task 036 - Linux tray launcher release and main promotion

## Goal

Ship the validated Linux Mint tray launcher as a first-class asset of version
0.10.4, then promote the exact validated commit through `develop` to `main`.

## Scope

- include `start-tray.sh` in the canonical Linux bundle;
- preserve its executable mode and verify valid Bash syntax;
- test positive and fail-closed verifier behavior;
- synchronize package, runtime and changelog version 0.10.4;
- run the full local quality, supported-Python and clean release gates;
- retain the Task 035 real graphical-session smoke as operational evidence;
- inspect hosted CI and document any external zero-step billing failure;
- fast-forward the same candidate to `develop` and `main`.

## Non-goals

- no installed-runtime upgrade without separate transactional authorization;
- no tag, GitHub release or public artifact publication;
- no Windows support change;
- no automation permission or Codex input during launcher startup.

## Gate

1. Focused verifier and launcher tests pass.
2. `scripts/quality-check.sh` passes on the candidate.
3. Python 3.10, 3.11 and 3.12 tests pass.
4. A clean bundle records the exact candidate commit and `source_dirty=false`.
5. Offline verification passes and includes the executable launcher.
6. Hosted CI status is recorded honestly; a billing zero-step failure supplies
   no evidence and may only be bypassed by a version-specific owner decision.
7. `develop`, `main` and their remote refs resolve to the validated commit.

## Rollback

Before promotion, delete only the unmerged task branch if the candidate fails.
After a fast-forward promotion, revert the offending commit; do not rewrite
shared history. Runtime installation remains unchanged unless a separately
authorized transactional upgrade is performed.

## Local evidence

- candidate commit: `1ff2c2136a45fea541a66b1b6d2e40f207a455f2`;
- quality gate: 331 tests, 86% coverage, Ruff, mypy, shell syntax, package
  build and diff checks passed;
- supported matrix: the same 331 tests passed on Python 3.10, 3.11 and 3.12;
- clean release bundle: version 0.10.4, `source_dirty=false`, isolated install
  and two-project smoke passed;
- bundled launcher: mode `0755`, content identical to source, SHA-256
  `eda7011542e6ed60fcc2b8d5bd53fd89e2faf285513534d1b32cc969c53a853e`;
- operational smoke: launcher reported the existing single tray instance;
  tray, monitor and Discord reply observer remained active;
- installed runtime: 0.10.3 with strict doctor status `ok`; it was not changed
  because no transactional runtime upgrade is required for source promotion.
