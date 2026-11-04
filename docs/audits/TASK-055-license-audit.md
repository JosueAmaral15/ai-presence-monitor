# Task 055 - Licence and Ownership Audit

## Scope

This audit covers tracked source and declared direct dependencies before a
public package licence is selected. It is evidence for a decision, not legal
advice.

## Repository ownership evidence

As of 2026-11-04, `git shortlog -sne --all` reports one repository author:
Josue Amaral. No source header or tracked text file declares a third-party
copyright or embedded licence. The repository nevertheless has no root
`LICENSE`, Python metadata says `Private :: Do Not Upload`, and the generated
Debian copyright file says `Proprietary`.

## Declared dependencies

- Runtime Python standard library, plus `tzdata` only on Windows.
- Optional tray dependency: PySide6, whose installed metadata declares
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`.
- Build and quality tools are development dependencies and are not bundled in
  the wheel.

PySide6 is dynamically installed as an optional dependency; it is not copied
into this repository. A public distribution must retain its upstream notices
and must not imply that PySide6 is relicensed by this project.

## Unresolved asset

`assets/alarm-four2.mp3` is a tracked binary introduced in the baseline commit.
No code references it and it is absent from the wheel, but its author, source
and licence are not recorded. A repository-wide Apache-2.0 grant cannot safely
claim this asset without provenance.

Resolve one of these options before changing the project licence:

1. record evidence that the copyright holder grants a compatible licence;
2. remove the unused asset from public source history going forward; or
3. replace it with a newly generated or commissioned sound whose rights and
   source are documented.

## Recommendation

After resolving the MP3, use Apache-2.0 for project-owned source, replace the
private Python classifier, update Debian copyright metadata, add dependency
notices and rebuild every artifact from one clean tagged commit. Until then,
keep package publication and licence mutation blocked.

