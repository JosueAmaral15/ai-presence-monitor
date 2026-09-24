from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

try:
    from .release_lib import (
        NORMALIZED_PACKAGE_NAME,
        ReleaseError,
        parse_checksums,
        sha256,
        wheel_metadata,
    )
except ImportError:
    from release_lib import (  # type: ignore[import-not-found,no-redef]
        NORMALIZED_PACKAGE_NAME,
        ReleaseError,
        parse_checksums,
        sha256,
        wheel_metadata,
    )

REQUIRED_WHEEL_MODULES = {
    "ai_presence_monitor/product_health.py",
    "ai_presence_monitor/updater.py",
    "ai_presence_monitor/windows_task.py",
    "ai_presence_monitor/win32_gui.py",
}
STATIC_ASSETS = {
    ".env.example",
    "install-linux.sh",
    "verify_release.py",
    "release_lib.py",
    "release-manifest.json",
}


def verify_release(
    bundle_dir: Path,
    *,
    install_smoke: bool = True,
    allow_dirty: bool = False,
) -> dict[str, object]:
    bundle = bundle_dir.expanduser().resolve()
    manifest = _load_manifest(bundle / "release-manifest.json")
    version = _manifest_version(manifest)
    checksums = parse_checksums(bundle / "SHA256SUMS")
    artifact_names = _manifest_artifact_names(manifest)
    expected_checksums = artifact_names | {"release-manifest.json"}
    if set(checksums) != expected_checksums:
        raise ReleaseError("Checksum file does not match the release manifest artifacts.")
    for filename, expected in checksums.items():
        path = bundle / filename
        if not path.is_file() or sha256(path) != expected:
            raise ReleaseError(f"Artifact checksum failed: {filename}.")
    _verify_manifest_artifacts(bundle, manifest)

    wheels = list(bundle.glob(f"{NORMALIZED_PACKAGE_NAME}-{version}-*.whl"))
    sdists = list(bundle.glob(f"{NORMALIZED_PACKAGE_NAME}-{version}.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseError("Release bundle must contain exactly one wheel and one sdist.")
    _, wheel_version = wheel_metadata(wheels[0])
    if wheel_version != version:
        raise ReleaseError("Wheel version does not match the release manifest.")
    _verify_wheel_modules(wheels[0])
    missing_static = STATIC_ASSETS - {path.name for path in bundle.iterdir()}
    if missing_static:
        raise ReleaseError(f"Release bundle is missing assets: {sorted(missing_static)}.")
    if manifest.get("source_dirty") is not False and not allow_dirty:
        raise ReleaseError("Release manifest must come from a clean source commit.")
    if install_smoke:
        _installed_smoke(wheels[0], version)
    return manifest


def _installed_smoke(wheel: Path, version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="ai-presence-verify-") as temporary:
        root = Path(temporary)
        venv_dir = root / "venv"
        home = root / "home"
        config_dir = home / ".config" / "ai-presence-monitor"
        state_dir = home / ".local" / "state"
        database = state_dir / "ai-presence-monitor" / "presence.db"
        config_dir.mkdir(parents=True)
        state_dir.mkdir(parents=True)
        env_file = config_dir / ".env"
        env_file.write_text(
            "\n".join(
                (
                    "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=false",
                    f"PRESENCE_DB_PATH={database}",
                    "PRESENCE_DEFAULT_PROTOCOL=protocol2",
                    "PRESENCE_CODEX_WORKER_SCOPE=project",
                    "RED_NOTIFICATION_MODE=none",
                    "",
                )
            ),
            encoding="utf-8",
        )
        env_file.chmod(0o600)
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = venv_dir / "bin" / "python"
        command = venv_dir / "bin" / "ai-presence"
        environment = _isolated_environment(home, state_dir, env_file, venv_dir)
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheel),
            ],
            env=environment,
        )
        version_result = _run([str(command), "--version"], env=environment)
        if version_result.stdout.strip() != f"ai-presence {version}":
            raise ReleaseError("Installed command returned the wrong version.")
        _run([str(command), "init"], env=environment)
        schema = json.loads(
            _run([str(command), "schema-status", "--json"], env=environment).stdout
        )
        if not schema.get("healthy") or schema.get("migration_status") != "current":
            raise ReleaseError("Installed schema smoke failed.")
        doctor = json.loads(_run([str(command), "doctor", "--json"], env=environment).stdout)
        if doctor.get("status") == "error" or doctor.get("version") != version:
            raise ReleaseError("Installed doctor smoke failed.")
        _run([str(command), "upgrade", "--help"], env=environment)
        _run([str(command), "rollback-upgrade", "--help"], env=environment)
        _verify_project_isolation(command, root, database, environment)


def _verify_project_isolation(
    command: Path,
    root: Path,
    database: Path,
    environment: dict[str, str],
) -> None:
    projects = (root / "project-one", root / "project-two")
    for project in projects:
        project.mkdir()
        _run(
            [
                str(command),
                "start",
                "--project",
                str(project),
                "--protocol",
                "protocol2",
                "--task",
                "release verification",
                "--message",
                "isolated release verification",
            ],
            env=environment,
        )
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT worker_id FROM workers WHERE current_task = ? ORDER BY worker_id",
            ("release verification",),
        ).fetchall()
    if len(rows) != 2 or rows[0][0] == rows[1][0]:
        raise ReleaseError("Project isolation smoke did not create two distinct workers.")
    for project in projects:
        _run(
            [
                str(command),
                "finish",
                "--project",
                str(project),
                "--protocol",
                "protocol2",
                "--task",
                "release verification",
                "--message",
                "isolated release verification finished",
            ],
            env=environment,
        )


def _isolated_environment(
    home: Path,
    state_dir: Path,
    env_file: Path,
    venv_dir: Path,
) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PRESENCE_", "DISCORD_", "TELEGRAM_", "RED_", "PHONE_"))
    }
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_STATE_HOME": str(state_dir),
            "PRESENCE_ENV_FILE": str(env_file),
            "PATH": os.pathsep.join((str(venv_dir / "bin"), environment.get("PATH", ""))),
            "PYTHONNOUSERSITE": "1",
        }
    )
    return environment


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError("Release manifest is unreadable.") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ReleaseError("Release manifest schema is unsupported.")
    if payload.get("product") != "ai-presence-monitor":
        raise ReleaseError("Release manifest product is invalid.")
    if payload.get("supported_platform") != "linux":
        raise ReleaseError("Release manifest platform is invalid.")
    if payload.get("supported_python") != ["3.10", "3.11", "3.12"]:
        raise ReleaseError("Release manifest Python support is invalid.")
    return payload


def _manifest_version(manifest: dict[str, object]) -> str:
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ReleaseError("Release manifest version is invalid.")
    return version


def _manifest_artifact_names(manifest: dict[str, object]) -> set[str]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ReleaseError("Release manifest artifacts are invalid.")
    names = set()
    for name, value in artifacts.items():
        if not isinstance(name, str) or Path(name).name != name or not isinstance(value, dict):
            raise ReleaseError("Release manifest contains an invalid artifact.")
        digest = value.get("sha256")
        size = value.get("size")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ReleaseError("Release manifest contains an invalid artifact hash.")
        if not isinstance(size, int) or size <= 0:
            raise ReleaseError("Release manifest contains an invalid artifact size.")
        names.add(name)
    return names


def _verify_manifest_artifacts(bundle: Path, manifest: dict[str, object]) -> None:
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, dict)
    for name, value in artifacts.items():
        assert isinstance(name, str)
        assert isinstance(value, dict)
        path = bundle / name
        if not path.is_file():
            raise ReleaseError(f"Manifest artifact is missing: {name}.")
        if sha256(path) != value["sha256"] or path.stat().st_size != value["size"]:
            raise ReleaseError(f"Manifest artifact metadata failed: {name}.")


def _verify_wheel_modules(wheel: Path) -> None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseError("Wheel contents are unreadable.") from exc
    missing = REQUIRED_WHEEL_MODULES - names
    if missing:
        raise ReleaseError(f"Wheel is missing required modules: {sorted(missing)}.")


def _run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=Path("/tmp"),
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError(f"Release verification command failed: {Path(command[0]).name}.") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a private Linux release bundle.")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--skip-install-smoke", action="store_true")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Accept a development bundle whose manifest records source_dirty=true.",
    )
    args = parser.parse_args(argv)
    try:
        manifest = verify_release(
            args.bundle,
            install_smoke=not args.skip_install_smoke,
            allow_dirty=args.allow_dirty,
        )
    except (ReleaseError, ValueError) as exc:
        print(f"release verification failed: {exc}", file=sys.stderr)
        return 2
    print(
        "release verified: "
        f"version={manifest['version']} commit={manifest['source_commit']} "
        f"bundle={args.bundle.expanduser().resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
