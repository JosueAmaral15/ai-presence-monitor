# Task 049 - Release Candidate Closeout

## Objective

Close the 0.11.2 Linux candidate with consistent branch, hosted-CI, runtime and
local-artifact evidence. Do not treat branch promotion as authorization to tag
or publish a new GitHub prerelease.

## Steps

1. Confirm the final task commit passes the hosted Linux matrix.
2. Fast-forward `develop` and require the same matrix to pass.
3. Fast-forward `main` and require the same matrix to pass.
4. Confirm both remote branches resolve to the same commit.
5. Regenerate the canonical local bundle from the final clean commit and run
   the isolated release verifier.
6. Recheck the installed 0.11.2 runtime, services, prompt observer, tray and
   alarm state without changing saved prompt rules.

## Publication Boundary

No new tag or GitHub release is created by this task. Those actions change
external release state and require a separate explicit publication decision.
