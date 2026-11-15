# Task 069 - Persistent Automatic Dispatch Audit

## Problem

The background observer currently logs aggregate state names for all worker
profiles. A later investigation can correlate control state, service journals,
Codex session history and canonical hooks, but no durable record directly says
which profile, rule and automation feature initiated a transport attempt.

## Design

Add one append-only audit record per automatic transport attempt. The record is
claimed before native input and completed after the transport returns. A later
canonical hook from the exact worker and session changes only the confirmation
state.

The database stores:

- a random audit identifier;
- worker profile and rule identifier;
- source feature (`prompt_rule` or `availability_recovery`);
- normalized trigger and provider;
- a worker-scoped SHA-256 session fingerprint;
- occurrence number;
- transport and confirmation states;
- attempt, update and optional confirmation timestamps.

It never stores prompt text, raw session identifiers, account identity,
percentages, tokens, webhook values or exception messages.

## Action Plan

1. Add an additive schema 3 to schema 4 migration with a dedicated table and
   indexes for profile history and pending confirmation.
2. Add typed store methods to claim, complete, confirm and list audit records.
3. Claim an audit row immediately before each Prompt Rule or Availability
   Recovery transport and finalize it for success or uncertain failure.
4. Reconcile pending rows from later canonical session observations by exact
   worker-scoped session fingerprint.
5. Expose a read-only, sanitized CLI query with bounded results and optional
   explicit profile selection.
6. Add focused tests for migration, ordering, source separation, uncertainty,
   exact-session confirmation and prohibited content.
7. Update architecture, security, AI-worker and operator documentation.
8. Run formatting, focused tests, full tests, coverage, Ruff, mypy, shell
   checks, package build and diff validation.

## Acceptance Criteria

- Existing schema 3 databases migrate without losing operational data.
- Every real automatic transport is preceded by one durable claimed row.
- A transport exception produces one terminal `failed_or_uncertain` row and is
  never retried by the audit layer.
- `dispatch_started` remains preliminary until a later exact-session hook.
- Prompt Rule and Availability Recovery records are distinguishable.
- No prompt text or raw session identifier is written or printed.
- The CLI cannot mutate rules or fabricate confirmation.
- Existing authorization, claim-before-dispatch and fail-closed behavior remain
  unchanged.

## Validation Record

Completed on 2026-11-15:

- 403 tests passed with 87% aggregate coverage;
- Ruff, mypy, shell syntax and `git diff --check` passed;
- wheel and source distribution `0.15.0` built successfully;
- an isolated installation reported version `0.15.0`, initialized healthy
  schema 4 and returned a sanitized empty `dispatch-audit` response;
- the transactional dry-run reported `would_upgrade` from `0.14.0` to
  `0.15.0` using the preserved `0.14.0` rollback wheel.

The installed runtime and its real database were not mutated. A real upgrade
remains a separate, explicitly authorized operation because schema 4 is not
readable by runtime `0.14.0`.
