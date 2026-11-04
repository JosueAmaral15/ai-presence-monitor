from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from .release_lib import ReleaseError, sha256
except ImportError:
    from release_lib import (  # type: ignore[import-not-found,no-redef]
        ReleaseError,
        sha256,
    )

PACKAGE_NAME = "ai-presence-monitor"
DEBIAN_REVISION = "1"
REQUIRED_PATHS = {
    "usr/bin/ai-presence",
    "usr/bin/ai-presence-codex-hook",
    "usr/bin/ai-presence-codex-hooks",
    "usr/bin/ai-presence-interactive",
    "usr/bin/ai-presence-tray",
    "usr/lib/ai-presence-monitor/start-tray.sh",
    "usr/lib/python3/dist-packages/ai_presence_monitor/__init__.py",
    "usr/share/ai-presence-monitor/.env.example",
    "usr/share/doc/ai-presence-monitor/INSTALL-DEB.md",
    "usr/share/doc/ai-presence-monitor/build-info.json",
    "usr/share/doc/ai-presence-monitor/changelog.Debian.gz",
    "usr/share/doc/ai-presence-monitor/copyright",
    "usr/share/man/man1/ai-presence-codex-hook.1.gz",
    "usr/share/man/man1/ai-presence-codex-hooks.1.gz",
    "usr/share/man/man1/ai-presence-interactive.1.gz",
    "usr/share/man/man1/ai-presence-tray.1.gz",
    "usr/share/man/man1/ai-presence.1.gz",
    "usr/share/lintian/overrides/ai-presence-monitor",
}


def verify_debian_package(
    package: Path,
    *,
    expected_version: str | None = None,
    expected_commit: str | None = None,
    smoke: bool = True,
    allow_dirty: bool = False,
) -> dict[str, str]:
    package_path = package.expanduser().resolve()
    if not package_path.is_file() or package_path.suffix != ".deb":
        raise ReleaseError("Provide an existing .deb package.")
    fields = {
        name: _field(package_path, name)
        for name in ("Package", "Version", "Architecture", "Depends")
    }
    if fields["Package"] != PACKAGE_NAME:
        raise ReleaseError("Debian package name is invalid.")
    if fields["Architecture"] != "all":
        raise ReleaseError("Debian package architecture must be all.")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-[0-9]+", fields["Version"]):
        raise ReleaseError("Debian package version is invalid.")
    if (
        expected_version is not None
        and fields["Version"] != f"{expected_version}-{DEBIAN_REVISION}"
    ):
        raise ReleaseError("Debian package version does not match the release.")
    if "python3 (>= 3.10)" not in fields["Depends"] or "python3 (<< 3.13)" not in fields["Depends"]:
        raise ReleaseError("Debian package Python dependency range is invalid.")
    _verify_sidecar(package_path)

    with tempfile.TemporaryDirectory(prefix="ai-presence-deb-verify-") as temporary:
        root = Path(temporary) / "root"
        control_root = Path(temporary) / "control"
        root.mkdir()
        control_root.mkdir()
        _run(["dpkg-deb", "--extract", str(package_path), str(root)])
        _run(["dpkg-deb", "--control", str(package_path), str(control_root)])
        _verify_postrm(control_root / "postrm")
        present = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        missing = REQUIRED_PATHS - present
        if missing:
            raise ReleaseError(f"Debian package is missing files: {sorted(missing)}.")
        for relative in present:
            path = root / relative
            mode = path.stat().st_mode
            if mode & (stat.S_ISUID | stat.S_ISGID):
                raise ReleaseError("Debian package contains a privileged file mode.")
        for command in REQUIRED_PATHS & {path for path in present if path.startswith("usr/bin/")}:
            if not os.access(root / command, os.X_OK):
                raise ReleaseError(f"Debian command is not executable: {command}.")
        build_info = _load_build_info(
            root / "usr" / "share" / "doc" / PACKAGE_NAME / "build-info.json"
        )
        if build_info.get("debian_version") != fields["Version"]:
            raise ReleaseError("Debian build metadata version is invalid.")
        if expected_version is not None and build_info.get("version") != expected_version:
            raise ReleaseError("Debian build metadata upstream version is invalid.")
        if build_info.get("source_dirty") is not False and not allow_dirty:
            raise ReleaseError("Debian package must come from a clean source commit.")
        if expected_commit is not None and build_info.get("source_commit") != expected_commit:
            raise ReleaseError("Debian package source commit does not match the release.")
        if smoke:
            upstream_version = str(build_info.get("version", ""))
            _smoke(root, upstream_version)
    return fields


def _field(package: Path, name: str) -> str:
    return _run(["dpkg-deb", "--field", str(package), name]).stdout.strip()


def _verify_sidecar(package: Path) -> None:
    sidecar = package.with_suffix(package.suffix + ".sha256")
    try:
        line = sidecar.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise ReleaseError("Debian package SHA-256 sidecar is missing.") from exc
    expected = f"{sha256(package)}  {package.name}"
    if line != expected:
        raise ReleaseError("Debian package SHA-256 sidecar is invalid.")


def _verify_postrm(path: Path) -> None:
    try:
        content = path.read_text(encoding="utf-8")
        mode = path.stat().st_mode
    except OSError as exc:
        raise ReleaseError("Debian package post-removal script is missing.") from exc
    package_dir = "/usr/lib/python3/dist-packages/ai_presence_monitor"
    if not mode & stat.S_IXUSR or package_dir not in content:
        raise ReleaseError("Debian package post-removal script is invalid.")
    if "$HOME" in content or ".config" in content or "presence.db" in content:
        raise ReleaseError("Debian package post-removal script touches user state.")


def _load_build_info(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError("Debian package build metadata is unreadable.") from exc
    if not isinstance(payload, dict) or payload.get("product") != PACKAGE_NAME:
        raise ReleaseError("Debian package build metadata is invalid.")
    return payload


def _smoke(root: Path, version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="ai-presence-deb-home-") as temporary:
        home = Path(temporary)
        config = home / ".config" / PACKAGE_NAME
        state = home / ".local" / "state"
        config.mkdir(parents=True)
        state.mkdir(parents=True)
        database = state / PACKAGE_NAME / "presence.db"
        env_file = config / ".env"
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
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("PRESENCE_", "DISCORD_", "TELEGRAM_", "RED_", "PHONE_"))
        }
        environment.update(
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_STATE_HOME": str(state),
                "PRESENCE_ENV_FILE": str(env_file),
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": str(root / "usr" / "lib" / "python3" / "dist-packages"),
            }
        )
        command = root / "usr" / "bin" / "ai-presence"
        version_result = _run(["/usr/bin/python3", str(command), "--version"], env=environment)
        if version_result.stdout.strip() != f"ai-presence {version}":
            raise ReleaseError("Debian package command returned the wrong version.")
        _run(["/usr/bin/python3", str(command), "init"], env=environment)
        schema = json.loads(
            _run(
                ["/usr/bin/python3", str(command), "schema-status", "--json"],
                env=environment,
            ).stdout
        )
        if not schema.get("healthy") or schema.get("migration_status") != "current":
            raise ReleaseError("Debian package schema smoke failed.")


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
            cwd=Path("/tmp"),
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError(f"Debian package verification failed: {Path(command[0]).name}.") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify an AI Presence Monitor .deb package.")
    parser.add_argument("package", type=Path)
    parser.add_argument("--expected-version")
    parser.add_argument("--expected-commit")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)
    try:
        fields = verify_debian_package(
            args.package,
            expected_version=args.expected_version,
            expected_commit=args.expected_commit,
            smoke=not args.skip_smoke,
            allow_dirty=args.allow_dirty,
        )
    except (ReleaseError, ValueError, json.JSONDecodeError) as exc:
        print(f"Debian package verification failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"Debian package verified: package={fields['Package']} "
        f"version={fields['Version']} architecture={fields['Architecture']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
