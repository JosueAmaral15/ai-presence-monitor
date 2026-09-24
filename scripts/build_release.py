from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from .release_lib import (
        NORMALIZED_PACKAGE_NAME,
        ReleaseError,
        project_version,
        sha256,
        wheel_metadata,
    )
except ImportError:
    from release_lib import (  # type: ignore[import-not-found,no-redef]
        NORMALIZED_PACKAGE_NAME,
        ReleaseError,
        project_version,
        sha256,
        wheel_metadata,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RELEASE_ASSETS = (
    PROJECT_ROOT / ".env.example",
    PROJECT_ROOT / "scripts" / "install-linux.sh",
    PROJECT_ROOT / "scripts" / "verify_release.py",
    PROJECT_ROOT / "scripts" / "release_lib.py",
)


def build_release(
    output_dir: Path,
    *,
    allow_dirty: bool = False,
    python_executable: str = sys.executable,
) -> Path:
    version = project_version(PROJECT_ROOT)
    output = output_dir.expanduser().resolve()
    if output.exists():
        raise ReleaseError(f"Release output already exists: {output}.")
    commit = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    if dirty and not allow_dirty:
        raise ReleaseError("Release build requires a clean Git worktree.")
    source_date_epoch = _git("show", "-s", "--format=%ct", "HEAD")

    with tempfile.TemporaryDirectory(prefix="ai-presence-release-") as temporary:
        staging_root = Path(temporary)
        build_dir = staging_root / "build"
        bundle_dir = staging_root / f"ai-presence-monitor-{version}-linux"
        build_dir.mkdir()
        bundle_dir.mkdir()
        environment = dict(os.environ)
        environment["SOURCE_DATE_EPOCH"] = source_date_epoch
        environment.pop("PYTHONPATH", None)
        _run(
            [
                python_executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(build_dir),
                str(PROJECT_ROOT),
            ],
            env=environment,
        )

        wheel = _single_artifact(build_dir, f"{NORMALIZED_PACKAGE_NAME}-{version}-*.whl")
        sdist = _single_artifact(build_dir, f"{NORMALIZED_PACKAGE_NAME}-{version}.tar.gz")
        _, wheel_version = wheel_metadata(wheel)
        if wheel_version != version:
            raise ReleaseError(
                f"Built wheel version mismatch: expected={version} actual={wheel_version}."
            )

        artifacts: list[Path] = []
        for source in (wheel, sdist, *RELEASE_ASSETS):
            if not source.is_file():
                raise ReleaseError(f"Required release asset is missing: {source}.")
            target = bundle_dir / source.name
            shutil.copy2(source, target)
            artifacts.append(target)

        manifest = {
            "schema_version": 1,
            "product": "ai-presence-monitor",
            "version": version,
            "supported_platform": "linux",
            "supported_python": ["3.10", "3.11", "3.12"],
            "source_commit": commit,
            "source_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": {
                artifact.name: {
                    "sha256": sha256(artifact),
                    "size": artifact.stat().st_size,
                }
                for artifact in sorted(artifacts)
            },
        }
        manifest_path = bundle_dir / "release-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksum_targets = sorted((*artifacts, manifest_path))
        checksum_path = bundle_dir / "SHA256SUMS"
        checksum_path.write_text(
            "".join(f"{sha256(path)}  {path.name}\n" for path in checksum_targets),
            encoding="utf-8",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle_dir, output)
    return output


def _git(*arguments: str) -> str:
    result = _run(["git", *arguments], cwd=PROJECT_ROOT)
    return result.stdout.strip()


def _run(
    command: list[str],
    *,
    cwd: Path = PROJECT_ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError(f"Release command failed: {command[0]}.") from exc


def _single_artifact(root: Path, pattern: str) -> Path:
    matches = list(root.glob(pattern))
    if len(matches) != 1:
        raise ReleaseError(f"Expected exactly one build artifact matching {pattern}.")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a private Linux release bundle.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow a development bundle and record source_dirty=true.",
    )
    args = parser.parse_args(argv)
    try:
        output = build_release(args.output, allow_dirty=args.allow_dirty)
    except ReleaseError as exc:
        print(f"release build failed: {exc}", file=sys.stderr)
        return 2
    print(f"release bundle: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
