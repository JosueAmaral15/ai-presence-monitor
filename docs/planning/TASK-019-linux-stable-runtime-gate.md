# Task 019 - Linux Stable Runtime Gate

## Objective

Publish a Linux-supported release without deleting the existing Windows
adapters. Windows remains available only for controlled development through an
explicit experimental opt-in.

## Confirmed Scope

- Linux is enabled and supported by default.
- Windows implementation files, tests, and architecture remain in the project.
- Windows operational execution is disabled by default.
- `PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true` explicitly enables the existing
  Windows runtime for controlled validation.
- macOS and unknown platforms remain unsupported.
- No database migration or secret change is required.

## Design

1. Add one platform policy beside the existing Abstract Factory.
2. Read the experimental Windows boolean through `AppConfig`.
3. Enforce the policy at executable entrypoints before operational side
   effects.
4. Keep read-only diagnostics and recovery available while Windows is disabled:
   status, protocol listing, question listing, alarm stop, worker finish,
   control disable, hook uninstall, and background-service uninstall.
5. Do not let `--dry-run` bypass the platform gate because some legacy dry-run
   commands still update local state; experimental Windows validation requires
   the explicit opt-in.
6. Make a disabled Codex hook fail open without recording artificial activity.
7. Require explicit opt-in before the factory returns Windows adapters.

The guard does not remove or stub `WindowsPlatformFactory`, Win32 input, the
Windows alarm backend, or Task Scheduler support. It changes only their default
availability.

## Release And CI Policy

- Push and pull-request quality jobs target Ubuntu with Python 3.10, 3.11, and
  3.12.
- Windows jobs remain in the workflow as manual, experimental, and
  non-blocking validation.
- A Linux release requires the complete local quality gate, package build,
  isolated installation, runtime guard tests, Linux service smoke checks, and
  the already completed native `codex queue` E2E.
- The current GitHub billing lock still prevents remote jobs from starting and
  must be reported separately from repository failures.
- `main` promotion is evaluated only after the implementation is integrated in
  `develop` and all required Linux evidence is recorded.

## Phases

1. Document the policy, risks, and rollback.
2. Add configuration and the central runtime guard.
3. Apply the guard to CLI, tray, interactive menu, Codex hook, and hook
   installer entrypoints.
4. Pass the opt-in flag to platform-backed alarm, GUI, and service factories.
5. Split required Linux CI from manual experimental Windows CI.
6. Add unit tests for default denial, explicit opt-in, safe recovery, dry-run,
   and fail-open hooks.
7. Update the environment example and user documentation.
8. Run quality, package, isolated-install, and Linux runtime smoke gates.
9. Commit on the task branch and merge validated work into `develop`.

## Acceptance Criteria

- [x] Linux behavior remains enabled without new configuration.
- [x] Windows operational commands fail before side effects by default.
- [x] Explicit experimental opt-in restores the preserved Windows adapters.
- [x] Diagnostics and rollback remain usable while Windows is disabled.
- [x] Disabled Windows hooks return successfully without recording activity.
- [x] Windows source and tests are not deleted.
- [x] Required CI no longer depends on Windows runners.
- [x] Documentation does not claim stable Windows support.
- [x] Full local quality and packaging gates pass.
- [x] Rollback is documented and requires only one configuration change or one
      Git revert.

## Validation Evidence

Completed locally on Linux on 2026-09-12:

- 162 tests passed under Python 3.10, 3.11, and 3.12;
- coverage passed at 87%;
- Ruff, mypy, compilation, and `git diff --check` passed;
- version 0.6.2 sdist and wheel built successfully;
- the wheel installed in an isolated virtual environment and initialized its
  database on Linux;
- dry-run systemd generation selected the Linux factory;
- the installed runtime rejected Windows by default and accepted the explicit
  experimental opt-in;
- the wheel contains `win32_gui.py`, `windows_process.py`, and
  `windows_task.py`;
- tray construction smoke passed and both existing user services were active;
- the workflow parsed successfully as YAML.

The GitHub account billing lock still prevents a remote Linux CI run. This is
an external publication decision for `main`, not a Windows runtime blocker.

## Risks

- A guard applied too late could allow partial side effects before rejection.
- Blocking cleanup commands could strand an old Windows service or alarm.
- Documentation could imply that experimental Windows code is production-ready.
- A permissive default would silently restore the release blocker.

## Rollback

To temporarily restore the existing Windows behavior for controlled testing,
set:

```env
PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true
```

To revert the policy implementation, revert the task commit. No SQLite or
`control.json` rollback is necessary.
