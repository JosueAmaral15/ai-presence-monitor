from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

try:
    from .release_lib import ReleaseError, project_version, sha256, wheel_metadata
except ImportError:
    from release_lib import (  # type: ignore[import-not-found,no-redef]
        ReleaseError,
        project_version,
        sha256,
        wheel_metadata,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_NAME = "ai-presence-monitor"
DEFAULT_MAINTAINER = "Josue Amaral <josueamaral15@gmail.com>"
DEBIAN_REVISION = "1"
COMMANDS = {
    "ai-presence": "ai_presence_monitor.cli",
    "ai-presence-codex-hook": "ai_presence_monitor.codex_hook",
    "ai-presence-codex-hooks": "ai_presence_monitor.codex_hook_installer",
    "ai-presence-interactive": "ai_presence_monitor.interactive",
    "ai-presence-tray": "ai_presence_monitor.tray",
}


def build_debian_package(
    wheel: Path,
    output_dir: Path,
    *,
    source_commit: str,
    source_dirty: bool,
    source_date_epoch: int,
    maintainer: str = DEFAULT_MAINTAINER,
    allow_dirty: bool = False,
) -> tuple[Path, Path]:
    wheel_path = wheel.expanduser().resolve()
    output = output_dir.expanduser().resolve()
    version = project_version(PROJECT_ROOT)
    debian_version = f"{version}-{DEBIAN_REVISION}"
    _, wheel_version = wheel_metadata(wheel_path)
    if wheel_version != version:
        raise ReleaseError(
            f"Debian package wheel version mismatch: expected={version} actual={wheel_version}."
        )
    _validate_maintainer(maintainer)
    if source_dirty and not allow_dirty:
        raise ReleaseError("Debian package requires a clean source commit.")
    if not source_commit or any(character.isspace() for character in source_commit):
        raise ReleaseError("Debian package source commit is invalid.")
    if source_date_epoch < 0:
        raise ReleaseError("Debian package source timestamp is invalid.")

    package_path = output / f"{PACKAGE_NAME}_{debian_version}_all.deb"
    sidecar_path = package_path.with_suffix(package_path.suffix + ".sha256")
    if package_path.exists() or sidecar_path.exists():
        raise ReleaseError(f"Debian package output already exists: {package_path}.")
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ai-presence-deb-") as temporary:
        root = Path(temporary) / "root"
        purelib = root / "usr" / "lib" / "python3" / "dist-packages"
        binary_dir = root / "usr" / "bin"
        product_dir = root / "usr" / "lib" / PACKAGE_NAME
        shared_dir = root / "usr" / "share" / PACKAGE_NAME
        doc_dir = root / "usr" / "share" / "doc" / PACKAGE_NAME
        man_dir = root / "usr" / "share" / "man" / "man1"
        lintian_dir = root / "usr" / "share" / "lintian" / "overrides"
        for directory in (
            purelib,
            binary_dir,
            product_dir,
            shared_dir,
            doc_dir,
            man_dir,
            lintian_dir,
        ):
            directory.mkdir(parents=True, mode=0o755)

        _extract_wheel(wheel_path, purelib)
        for command, module in COMMANDS.items():
            _write_file(binary_dir / command, _wrapper_text(module), mode=0o755)
            _write_gzip(
                man_dir / f"{command}.1.gz",
                _manual_text(command),
                mtime=0,
            )
        shutil.copy2(PROJECT_ROOT / "start-tray.sh", product_dir / "start-tray.sh")
        (product_dir / "start-tray.sh").chmod(0o755)
        shutil.copy2(PROJECT_ROOT / ".env.example", shared_dir / ".env.example")
        for name in ("README.md", "README.pt-BR.md"):
            shutil.copy2(PROJECT_ROOT / name, doc_dir / name)
        install_doc = PROJECT_ROOT / "docs" / "INSTALL-DEB.md"
        if not install_doc.is_file():
            raise ReleaseError("Debian installation documentation is missing.")
        shutil.copy2(install_doc, doc_dir / "INSTALL-DEB.md")
        _write_file(doc_dir / "copyright", _copyright_text(), mode=0o644)
        _write_file(
            lintian_dir / PACKAGE_NAME,
            "# Standalone upstream package; not an upload to the Debian archive.\n"
            f"{PACKAGE_NAME}: initial-upload-closes-no-bugs\n",
            mode=0o644,
        )
        _write_gzip(
            doc_dir / "changelog.Debian.gz",
            _changelog_text(debian_version, maintainer),
            mtime=0,
        )
        _write_file(
            doc_dir / "build-info.json",
            json.dumps(
                {
                    "product": PACKAGE_NAME,
                    "source_commit": source_commit,
                    "source_dirty": source_dirty,
                    "version": version,
                    "debian_version": debian_version,
                    "wheel_sha256": sha256(wheel_path),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            mode=0o644,
        )
        control_dir = root / "DEBIAN"
        control_dir.mkdir(mode=0o755)
        _write_file(
            control_dir / "control",
            _control_text(debian_version, maintainer),
            mode=0o644,
        )
        _write_file(control_dir / "postrm", _postrm_text(), mode=0o755)
        _write_file(control_dir / "md5sums", _md5sums(root), mode=0o644)
        _normalize_tree(root)
        _run(
            [
                "dpkg-deb",
                "--root-owner-group",
                "--build",
                str(root),
                str(package_path),
            ],
            env={**os.environ, "SOURCE_DATE_EPOCH": str(source_date_epoch)},
        )

    sidecar_path.write_text(
        f"{sha256(package_path)}  {package_path.name}\n",
        encoding="ascii",
    )
    return package_path, sidecar_path


def _control_text(version: str, maintainer: str) -> str:
    _validate_maintainer(maintainer)
    return "\n".join(
        (
            f"Package: {PACKAGE_NAME}",
            f"Version: {version}",
            "Section: utils",
            "Priority: optional",
            "Architecture: all",
            f"Maintainer: {maintainer}",
            "Homepage: https://github.com/JosueAmaral15/ai-presence-monitor",
            "Depends: python3 (>= 3.10), python3 (<< 3.13)",
            "Description: local AI-worker presence and continuation monitor",
            " AI Presence Monitor records scoped worker activity, evaluates bounded",
            " inactivity protocols and integrates explicit Discord and Codex flows.",
            " Configuration, services, hooks and automation remain operator-managed.",
            "",
        )
    )


def _wrapper_text(module: str) -> str:
    if not module.startswith("ai_presence_monitor."):
        raise ReleaseError("Debian command module is invalid.")
    return (
        "#!/usr/bin/python3\n"
        f"from {module} import main\n\n"
        "if __name__ == \"__main__\":\n"
        "    raise SystemExit(main())\n"
    )


def _postrm_text() -> str:
    return """#!/bin/sh
set -e

case "$1" in
    remove|purge)
        package_dir=/usr/lib/python3/dist-packages/ai_presence_monitor
        if [ -d "$package_dir" ]; then
            find "$package_dir" -type d -name __pycache__ -prune -exec rm -rf -- {} +
            rmdir --ignore-fail-on-non-empty -- "$package_dir"
        fi
        ;;
esac

exit 0
"""


def _manual_text(command: str) -> str:
    if command not in COMMANDS:
        raise ReleaseError("Debian manual command is invalid.")
    description = {
        "ai-presence": "operate the AI Presence Monitor",
        "ai-presence-codex-hook": "record one Codex hook event",
        "ai-presence-codex-hooks": "manage Codex presence hooks",
        "ai-presence-interactive": "run the interactive configuration assistant",
        "ai-presence-tray": "run the optional graphical system tray",
    }[command]
    return (
        f".TH {command.upper()} 1 \"04 November 2026\" \"AI Presence Monitor\"\n"
        ".SH NAME\n"
        f"{command} \\- {description}\n"
        ".SH SYNOPSIS\n"
        f".B {command}\n"
        ".RI [ options ]\n"
        ".SH DESCRIPTION\n"
        "AI Presence Monitor provides project-scoped worker presence, bounded "
        "inactivity protocols and explicit Discord and Codex integrations.\n"
        ".SH OPTIONS\n"
        "Run the command with \\fB--help\\fR for the complete current interface.\n"
        ".SH FILES\n"
        "Configuration is user-owned under \\fI~/.config/ai-presence-monitor\\fR.\n"
        ".SH SEE ALSO\n"
        "Documentation is installed under \\fI/usr/share/doc/ai-presence-monitor\\fR.\n"
    )


def _extract_wheel(wheel: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            for info in archive.infolist():
                relative = _safe_wheel_member(info.filename)
                if relative is None:
                    continue
                if relative.parts[0].endswith(".dist-info"):
                    continue
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise ReleaseError("Debian package wheel must not contain symlinks.")
                target = destination.joinpath(*relative.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
                target.chmod(0o644)
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ReleaseError("Debian package wheel is unreadable.") from exc


def _safe_wheel_member(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name)
    if not name or name.endswith("/"):
        if path.is_absolute() or ".." in path.parts:
            raise ReleaseError("Debian package wheel contains an unsafe path.")
        return None
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ReleaseError("Debian package wheel contains an unsafe path.")
    return path


def _validate_maintainer(maintainer: str) -> None:
    if (
        not maintainer.strip()
        or maintainer != maintainer.strip()
        or "\n" in maintainer
        or "\r" in maintainer
        or len(maintainer) > 200
    ):
        raise ReleaseError("Debian package maintainer is invalid.")


def _copyright_text() -> str:
    return """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: ai-presence-monitor
Source: https://github.com/JosueAmaral15/ai-presence-monitor

Files: *
Copyright: 2026 Josue Amaral
License: Apache-2.0
 On Debian systems, the complete text of the Apache License, Version 2.0 is
 available at /usr/share/common-licenses/Apache-2.0.
"""


def _changelog_text(version: str, maintainer: str) -> str:
    return (
        f"{PACKAGE_NAME} ({version}) stable; urgency=medium\n\n"
        "  * Add the verified Debian, Ubuntu and Linux Mint package.\n\n"
        f" -- {maintainer}  Wed, 04 Nov 2026 09:00:00 -0300\n"
    )


def _md5sums(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.parent == root / "DEBIAN":
            continue
        digest = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root).as_posix()}\n")
    return "".join(lines)


def _write_file(path: Path, content: str, *, mode: int) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def _write_gzip(path: Path, content: str, *, mtime: int) -> None:
    with path.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=mtime) as archive:
            archive.write(content.encode("utf-8"))
    path.chmod(0o644)


def _normalize_tree(root: Path) -> None:
    root.chmod(0o755)
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            path.chmod(0o755)
        elif (
            path.parent != root / "usr" / "bin"
            and path.name != "start-tray.sh"
            and path != root / "DEBIAN" / "postrm"
        ):
            path.chmod(0o644)


def _run(command: list[str], *, env: dict[str, str]) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError(f"Debian package command failed: {command[0]}.") from exc


def _git(*arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError("Could not inspect the Git source state.") from exc
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the AI Presence Monitor .deb package.")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maintainer", default=DEFAULT_MAINTAINER)
    args = parser.parse_args(argv)
    try:
        package, sidecar = build_debian_package(
            args.wheel,
            args.output_dir,
            source_commit=_git("rev-parse", "HEAD"),
            source_dirty=bool(_git("status", "--porcelain")),
            source_date_epoch=int(_git("show", "-s", "--format=%ct", "HEAD")),
            maintainer=args.maintainer,
        )
    except (ReleaseError, ValueError) as exc:
        print(f"Debian package build failed: {exc}", file=sys.stderr)
        return 2
    print(f"Debian package: {package}")
    print(f"SHA-256 sidecar: {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
