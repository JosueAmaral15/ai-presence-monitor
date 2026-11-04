from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


class CodexRepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositoryCategory:
    name: str
    file_count: int
    byte_count: int
    top_level_entries: tuple[str, ...]
    schema_review_candidate: bool


@dataclass(frozen=True)
class CodexRepositoryInventory:
    repository_name: str
    categories: tuple[RepositoryCategory, ...]
    symlink_count: int
    unreadable_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "repository_name": self.repository_name,
            "categories": [asdict(category) for category in self.categories],
            "symlink_count": self.symlink_count,
            "unreadable_count": self.unreadable_count,
        }


_CONVERSATION_CANDIDATES = frozenset(
    {
        "sessions",
        "archived_sessions",
        "history.jsonl",
        "session_index.jsonl",
    }
)
_SECRET_OR_CONFIGURATION = frozenset(
    {
        "auth.json",
        "config.toml",
        "hooks.json",
        "mcp-oauth-locks",
        "rules",
    }
)
_RUNTIME_STATE = frozenset(
    {
        "app-server-control",
        "app-server-daemon",
        "ipc",
        "thread-writer-locks",
        "tmp",
        ".tmp",
    }
)
_INSTALLATION_CONTENT = frozenset(
    {
        "packages",
        "plugins",
        "skills",
        "vendor_imports",
    }
)
_PRIVATE_AUXILIARY_DATA = frozenset(
    {
        ".chatgpt-projects",
        "attachments",
        "browser",
        "computer-use",
        "dictation-history",
        "generated_images",
        "memories",
        "shell_snapshots",
        "transcription-history.jsonl",
        "visualizations",
    }
)


def inspect_codex_repository(root: Path) -> CodexRepositoryInventory:
    repository = root.expanduser()
    if not repository.exists():
        raise CodexRepositoryError("Codex repository does not exist.")
    if not repository.is_dir():
        raise CodexRepositoryError("Codex repository is not a directory.")

    aggregates: dict[str, tuple[int, int, set[str]]] = {}
    symlink_count = 0
    unreadable_count = 0
    try:
        paths = repository.rglob("*")
        for path in paths:
            try:
                relative = path.relative_to(repository)
                top_level = relative.parts[0]
                if path.is_symlink():
                    symlink_count += 1
                    continue
                if not path.is_file():
                    continue
                category = classify_codex_repository_path(relative)
                try:
                    size = path.stat().st_size
                except OSError:
                    unreadable_count += 1
                    continue
                count, byte_count, entries = aggregates.get(
                    category,
                    (0, 0, set()),
                )
                entries.add(top_level)
                aggregates[category] = (count + 1, byte_count + size, entries)
            except (OSError, ValueError):
                unreadable_count += 1
    except OSError as exc:
        raise CodexRepositoryError("Could not inventory the Codex repository.") from exc

    categories = tuple(
        RepositoryCategory(
            name=name,
            file_count=count,
            byte_count=byte_count,
            top_level_entries=tuple(sorted(entries)),
            schema_review_candidate=name == "conversation_candidate",
        )
        for name, (count, byte_count, entries) in sorted(aggregates.items())
    )
    return CodexRepositoryInventory(
        repository_name=repository.name,
        categories=categories,
        symlink_count=symlink_count,
        unreadable_count=unreadable_count,
    )


def classify_codex_repository_path(relative_path: Path) -> str:
    if relative_path.is_absolute() or not relative_path.parts:
        raise CodexRepositoryError("Repository path must be relative.")
    top_level = relative_path.parts[0]
    name = relative_path.name
    if top_level in _CONVERSATION_CANDIDATES:
        if name.endswith(".jsonl"):
            return "conversation_candidate"
        return "unknown"
    if top_level in _SECRET_OR_CONFIGURATION:
        return "secret_or_configuration"
    if top_level in _RUNTIME_STATE or name.endswith((".lock", ".pid")):
        return "runtime_state"
    if top_level in _INSTALLATION_CONTENT:
        return "installation_content"
    if top_level in _PRIVATE_AUXILIARY_DATA:
        return "private_auxiliary_data"
    if name.endswith((".sqlite", ".sqlite-shm", ".sqlite-wal", ".db")):
        return "active_database"
    if top_level in {"cache", "ambient-suggestions"}:
        return "cache"
    return "unknown"
