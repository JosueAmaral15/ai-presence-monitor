# Task 055 - Licence and Ownership Audit

## Scope

This audit covers tracked source and declared direct dependencies before a
public package licence is selected. It is evidence for a decision, not legal
advice.

## Repository ownership evidence

As of 2026-11-04, `git shortlog -sne --all` reports one repository author:
Josue Amaral. No source header or tracked text file declares a third-party
copyright or embedded licence. Task 059 added a root Apache-2.0 `LICENSE`,
removed the private Python classifier and aligned generated Debian copyright
metadata with that licence.

## Declared dependencies

- Runtime Python standard library, plus `tzdata` only on Windows.
- Optional tray dependency: PySide6, whose installed metadata declares
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`.
- Build and quality tools are development dependencies and are not bundled in
  the wheel.

PySide6 is dynamically installed as an optional dependency; it is not copied
into this repository. A public distribution must retain its upstream notices
and must not imply that PySide6 is relicensed by this project.

## Asset resolution

`assets/alarm-four2.mp3` is a tracked binary introduced in the baseline commit.
No code references it and it is absent from the wheel, but its author, source
and licence were not recorded. It was removed from current source under the
owner's explicit authorization and replaced with `ai-presence-alarm.wav`.

The replacement is synthesized entirely by the tracked standard-library
script `scripts/generate_alarm_asset.py`. Its authorship, parameters,
Apache-2.0 licence and SHA-256 are recorded in
`docs/audits/TASK-059-alarm-asset-provenance.md`; an automated test requires
byte-for-byte reproduction. No third-party recording or sample is included.

## Recommendation

Apache-2.0 is now applied to project-owned source and generated assets. Python
and Debian metadata agree, optional dependency notices are recorded, and the
licence/provenance files are required release-bundle assets. Rebuild every
artifact from one clean candidate commit before any publication. External
package publication remains separately gated.
