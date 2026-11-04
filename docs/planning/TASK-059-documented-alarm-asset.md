# Task 059 - Documented Alarm Asset

## Goal

Replace the untraceable optional MP3 with an original, reproducible alarm sound
and align repository, Python and Debian licence metadata for public
distribution.

## Scope

1. Remove `assets/alarm-four2.mp3` from the current source tree.
2. Generate a mono PCM WAV using only an auditable Python standard-library
   script and fixed synthesis parameters.
3. Verify byte-for-byte reproduction and a recorded SHA-256 digest in tests.
4. Document authorship, generation parameters, licence and configuration.
5. Apply Apache-2.0 consistently to the repository, Python package and Debian
   package metadata.
6. Include the licence, generated sound, generator and provenance document in
   the canonical Linux bundle.
7. Run the full local quality and release gates before promotion.

## Safety Boundaries

- The asset remains opt-in and does not alter an existing `.env`.
- Building, installing or starting the monitor does not play the sound.
- No third-party recording or sample is embedded in the generated waveform.
- External package or marketplace publication remains a separate approval
  boundary.

## Acceptance Criteria

- the removed MP3 is absent from tracked source;
- the committed WAV is reproducible byte-for-byte from the tracked script;
- provenance and SHA-256 are documented and regression-tested;
- wheel, sdist, Debian metadata and Linux release bundle carry consistent
  Apache-2.0 information;
- quality, package build and release verification pass.
