# Task 056 - Secure Codex History Synchronization

## Goal

Synchronize eligible Codex conversation history between paired computers while
preserving provenance, preventing secret disclosure and avoiding destructive
updates to a live `~/.codex` directory.

## Security boundary

An AnyDesk-style numeric identifier can be a discovery label, but it is not an
authentication secret. The product must use a one-time pairing code plus a
device key pair and mutual authentication. A reusable short password alone is
not sufficient for an Internet-facing synchronization service.

The first implementation must not copy the complete `.codex` tree. It excludes
authentication material, configuration, environment files, MCP credentials,
logs not explicitly classified as conversation records, SQLite WAL/SHM files,
locks, caches and active runtime state.

## Architecture

1. Build a read-only inventory that records paths, formats, sizes and schema
   versions without recording content or secrets.
2. Define a versioned export envelope for immutable conversation events. Each
   event has a stable ID, source device, source path or session, timestamp,
   content hash and schema version.
3. Merge append-only events by stable ID. Preserve both variants when the same
   logical record has different content and report the conflict; never use a
   last-writer-wins overwrite for conversation content.
4. Pair devices with a one-time code, mutually authenticated device keys and
   explicit human approval on both endpoints. Store private keys in the
   platform credential store, not in project files.
5. Encrypt records end to end before relay or remote storage. The relay must
   not receive plaintext conversation content.
6. Import only through a tested compatibility adapter or an official Codex
   interface. Until then, expose merged history as a separate read-only archive
   rather than modifying the live `.codex` repository.

## Phases

- Phase 1: sanitized inventory and format report.
- Phase 2: two-directory export/merge prototype with fixtures.
- Phase 3: local-network pairing and encrypted transfer.
- Phase 4: relay discovery, revocation and recovery.
- Phase 5: real two-device E2E and compatibility matrix.

## Phase 1 implementation

The read-only command below reports aggregate categories without opening file
contents, printing session filenames or returning the absolute home path:

```bash
ai-presence inspect-codex-repository --root "$HOME/.codex"
```

`conversation_candidate` means schema review only. It is not permission to
export or merge the file. Every unknown extension or location fails closed.
Symlinks are skipped and reported only as a count.

## Gates

- no secret-bearing path or raw credential enters an export;
- interrupted sync is idempotent and resumable;
- concurrent histories merge without deletion or silent replacement;
- pairing can be revoked per device;
- tests cover malicious archives, path traversal, replay and schema drift.
