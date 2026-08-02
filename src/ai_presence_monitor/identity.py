from __future__ import annotations

import hashlib
import re
from pathlib import Path

WORKER_SCOPES = ("global", "project", "session", "project-session")
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def normalize_scope(scope: str) -> str:
    normalized = scope.strip().lower()
    if normalized not in WORKER_SCOPES:
        choices = ", ".join(WORKER_SCOPES)
        raise ValueError(f"Escopo de worker invalido: {scope!r}. Use: {choices}.")
    return normalized


def _safe_component(value: str, fallback: str) -> str:
    normalized = _SAFE_COMPONENT.sub("-", value.strip()).strip("-._")
    return normalized[:80] or fallback


def project_component(project_path: str | Path | None) -> str:
    if project_path is None:
        return "unknown"
    path = Path(project_path).expanduser().resolve()
    name = _safe_component(path.name, "project")
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8]
    return f"{name}-{digest}"


def session_component(session_id: str | None) -> str:
    return _safe_component(session_id or "", "unknown")


def scoped_worker_id(
    base_worker_id: str,
    scope: str,
    *,
    project_path: str | Path | None = None,
    session_id: str | None = None,
) -> str:
    normalized_scope = normalize_scope(scope)
    if normalized_scope == "global":
        return base_worker_id

    parts = [base_worker_id]
    if normalized_scope in {"project", "project-session"}:
        parts.append(f"project={project_component(project_path)}")
    if normalized_scope in {"session", "project-session"}:
        parts.append(f"session={session_component(session_id)}")
    return ":".join(parts)
