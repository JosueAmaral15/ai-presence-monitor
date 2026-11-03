# Task 051 - Linux Release 0.11.3

## Objective

Ship the Linux alarm spawn stabilization as an unambiguous patch version. Do
not leave the installed pre-fix runtime and the corrected bundle under the same
0.11.2 identity.

## Gates

1. Keep the already validated chat, prompt-observer and schema-2 behavior.
2. Run the full quality gate and Python 3.10-3.12 matrix.
3. Require hosted Linux CI on the task branch, `develop` and `main`.
4. Build and verify the canonical 0.11.3 bundle from the exact final commit.
5. Upgrade the dedicated runtime transactionally from authentic 0.11.2,
   preserving database, controls, hooks and service state.
6. Confirm strict doctor, zero prompt-observer restarts, active tray, no alarm
   and matching remote branch commits.

## Publication Boundary

This task prepares and promotes the local product release. It does not create a
Git tag or publish a GitHub prerelease without a separate explicit decision.
