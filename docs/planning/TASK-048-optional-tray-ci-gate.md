# Task 048 - Optional Tray CI Gate

## Incident

The `develop` workflow for commit `8384094` ran on all supported Linux/Python
combinations. Tests, aggregate coverage and Ruff passed, but mypy failed because
the CI intentionally installs `.[dev]` without the optional `tray` extra and
therefore cannot resolve `PySide6.*` imports.

After correcting that boundary, Python 3.10 and 3.11 passed. Python 3.12 then
exposed a separate packaging assumption: a no-isolation build requires the
declared setuptools backend to exist in the development environment, while a
fresh 3.12 venv no longer supplies it incidentally.

## Decision

Keep PySide6 optional. Configure mypy to tolerate missing implementations only
for `PySide6.*`, whose imports are delayed until the tray starts and whose
absence already produces a dedicated runtime error. Do not weaken missing-import
validation globally and do not make every headless CI job download Qt.
Declare the existing `setuptools>=68` build backend in the development extra so
the no-isolation build is reproducible on every supported Python version.

## Validation

1. Run the complete local quality gate.
2. Verify a clean environment containing only `.[dev]` can run mypy.
3. Push the task branch, promote it to `develop` and require successful GitHub
   Actions jobs for Python 3.10, 3.11 and 3.12.
4. Recheck the installed runtime with strict doctor and confirm the prompt-rule
   observer and tray session remain active with no restarts.

## Promotion

Fast-forward `main` only after the remote matrix and the already completed real
chat and prompt-observer integrations are all green. The optional Windows job
remains disabled under the current Linux-only product policy.

## Outcome

The final commit passed the hosted matrix on Python 3.10, 3.11 and 3.12 on the
task branch, then again after fast-forward promotion to `develop` and `main`.
The optional Windows job remained skipped as designed.
