from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

PACKAGE_NAME = "ai-presence-monitor"
NORMALIZED_PACKAGE_NAME = "ai_presence_monitor"
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ReleaseError(RuntimeError):
    pass


def project_version(project_root: Path) -> str:
    pyproject = project_root / "pyproject.toml"
    init_file = project_root / "src" / "ai_presence_monitor" / "__init__.py"
    pyproject_version = _single_match(
        pyproject,
        r'^version\s*=\s*"([^"]+)"\s*$',
        "project version",
    )
    runtime_version = _single_match(
        init_file,
        r'^__version__\s*=\s*"([^"]+)"\s*$',
        "runtime version",
    )
    if pyproject_version != runtime_version:
        raise ReleaseError(
            "Package and runtime versions differ: "
            f"pyproject={pyproject_version} runtime={runtime_version}."
        )
    if not VERSION_PATTERN.fullmatch(pyproject_version):
        raise ReleaseError(f"Release version is invalid: {pyproject_version}.")
    return pyproject_version


def wheel_metadata(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise ReleaseError("Wheel must contain exactly one METADATA file.")
            metadata = archive.read(metadata_names[0]).decode("utf-8")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, KeyError) as exc:
        raise ReleaseError(f"Wheel metadata is unreadable: {path.name}.") from exc

    fields: dict[str, str] = {}
    for line in metadata.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in {"Name", "Version", "Requires-Python"}:
            fields[key] = value.strip()
    name = fields.get("Name", "")
    version = fields.get("Version", "")
    if name.lower().replace("_", "-") != PACKAGE_NAME:
        raise ReleaseError(f"Unexpected wheel package name: {name or '<missing>'}.")
    if not VERSION_PATTERN.fullmatch(version):
        raise ReleaseError(f"Unexpected wheel version: {version or '<missing>'}.")
    return name, version


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ReleaseError(f"Could not hash {path}.") from exc
    return digest.hexdigest()


def parse_checksums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReleaseError(f"Could not read checksum file: {path}.") from exc
    values: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise ReleaseError("Checksum file has an invalid line.")
        digest, filename = parts
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ReleaseError("Checksum file contains an invalid SHA-256 value.")
        if Path(filename).name != filename or filename in values:
            raise ReleaseError("Checksum file contains an invalid artifact name.")
        values[filename] = digest
    if not values:
        raise ReleaseError("Checksum file is empty.")
    return values


def _single_match(path: Path, pattern: str, label: str) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseError(f"Could not read {label} source: {path}.") from exc
    matches = re.findall(pattern, content, flags=re.MULTILINE)
    if len(matches) != 1:
        raise ReleaseError(f"Could not determine exactly one {label}.")
    return matches[0]
