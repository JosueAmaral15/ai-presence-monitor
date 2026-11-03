# Task 050 - Linux Alarm Spawn Identity Race

## Incident

The final 0.11.2 release gate intermittently failed because a newly spawned
alarm was immediately reported as stale. On Linux, the child PID exists before
`exec`; a snapshot taken in that interval can still expose the parent Python
command line. Persisting that transient fingerprint makes the next snapshot of
the same process disagree after it becomes GNU `timeout`.

## Correction

Keep the process start token and command fingerprint identity checks. In the
Linux backend, wait for at most 200 milliseconds for the child command line to
match the exact controlled `timeout` argv before returning it to the controller.
Stop waiting if the process exits. The controller retains its existing bounded
snapshot/error handling.

## Validation

1. Add a deterministic unit test with a pre-exec snapshot followed by the
   expected `timeout` snapshot.
2. Repeat the two previously failing process tests to exercise real `/proc`.
3. Run the complete local quality and Python matrix release gate.
4. Require hosted CI on the task branch, `develop` and `main`.
5. Verify the final bundle manifest is bound to the promoted commit.
