from __future__ import annotations

import argparse
import json
import shlex
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import resolve_env_path

HOOK_MARKERS = ("codex_presence_hook.py", "ai_presence_monitor.codex_hook")
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop")


@dataclass(frozen=True)
class HookInstallResult:
    action: str
    target_path: Path
    changed: bool
    backup_path: Path | None
    presence_hooks: int
    rendered_json: str


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_user_hooks_path() -> Path:
    return Path.home() / ".codex" / "hooks.json"


def default_env_path() -> Path:
    return resolve_env_path()


def default_hook_script_path() -> Path:
    return project_root() / "hooks" / "codex_presence_hook.py"


def build_hook_command(
    *,
    env_file: Path,
    hook_script: Path | None = None,
    python_executable: str | None = None,
) -> str:
    python = python_executable or sys.executable
    command = [python]
    if hook_script is None:
        command.extend(["-m", "ai_presence_monitor.codex_hook"])
    else:
        command.append(str(hook_script))
    command.extend(["--env-file", str(env_file)])
    return shlex.join(command)


def build_presence_hooks(command: str, timeout: int = 5) -> dict[str, Any]:
    command_hook = {"type": "command", "command": command, "timeout": timeout}
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume",
                    "hooks": [
                        {
                            **command_hook,
                            "statusMessage": "Registrando presenca do Codex",
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [{"hooks": [command_hook]}],
            "PreToolUse": [{"matcher": "*", "hooks": [command_hook]}],
            "PostToolUse": [{"matcher": "*", "hooks": [command_hook]}],
            "Stop": [{"hooks": [command_hook]}],
        }
    }


def load_hooks_file(target_path: Path) -> dict[str, Any]:
    if not target_path.exists():
        return {}
    data = json.loads(target_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{target_path} precisa conter um objeto JSON.")
    return data


def contains_presence_hook(hook: Any) -> bool:
    if not isinstance(hook, dict):
        return False
    command = str(hook.get("command", ""))
    return any(marker in command for marker in HOOK_MARKERS)


def count_presence_hooks(config: dict[str, Any]) -> int:
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return 0

    count = 0
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks", [])
            if not isinstance(handlers, list):
                continue
            count += sum(1 for handler in handlers if contains_presence_hook(handler))
    return count


def prune_presence_hooks(config: dict[str, Any]) -> dict[str, Any]:
    pruned = json.loads(json.dumps(config))
    hooks = pruned.get("hooks")
    if hooks is None:
        pruned["hooks"] = {}
        return pruned
    if not isinstance(hooks, dict):
        raise ValueError("Campo 'hooks' precisa ser um objeto.")

    for event_name in list(hooks):
        groups = hooks[event_name]
        if not isinstance(groups, list):
            raise ValueError(f"hooks.{event_name} precisa ser uma lista.")

        kept_groups = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue

            handlers = group.get("hooks", [])
            if not isinstance(handlers, list):
                kept_groups.append(group)
                continue

            next_handlers = [
                handler for handler in handlers if not contains_presence_hook(handler)
            ]
            if next_handlers:
                next_group = dict(group)
                next_group["hooks"] = next_handlers
                kept_groups.append(next_group)

        if kept_groups:
            hooks[event_name] = kept_groups
        else:
            del hooks[event_name]

    return pruned


def merge_presence_hooks(existing: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    merged = prune_presence_hooks(existing)
    hooks = merged.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Campo 'hooks' precisa ser um objeto.")

    generated_hooks = generated.get("hooks", {})
    if not isinstance(generated_hooks, dict):
        raise ValueError("Hooks gerados invalidos.")

    for event_name, groups in generated_hooks.items():
        if not isinstance(groups, list):
            raise ValueError(f"hooks.{event_name} gerado precisa ser lista.")
        hooks.setdefault(event_name, [])
        if not isinstance(hooks[event_name], list):
            raise ValueError(f"hooks.{event_name} precisa ser uma lista.")
        hooks[event_name].extend(groups)

    return merged


def render_hooks(config: dict[str, Any]) -> str:
    return json.dumps(config, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def backup_hooks_file(target_path: Path) -> Path | None:
    if not target_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = target_path.with_name(f"{target_path.name}.backup-{timestamp}")
    shutil.copy2(target_path, backup_path)
    return backup_path


def write_hooks_file(target_path: Path, config: dict[str, Any], backup: bool = True) -> Path | None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = backup_hooks_file(target_path) if backup else None
    tmp_path = target_path.with_name(f"{target_path.name}.tmp")
    tmp_path.write_text(render_hooks(config), encoding="utf-8")
    tmp_path.replace(target_path)
    target_path.chmod(0o600)
    return backup_path


def install_codex_hook(
    *,
    target_path: Path | None = None,
    env_file: Path | None = None,
    hook_script: Path | None = None,
    python_executable: str | None = None,
    timeout: int = 5,
    dry_run: bool = False,
    backup: bool = True,
) -> HookInstallResult:
    target = (target_path or default_user_hooks_path()).expanduser()
    env = (env_file or default_env_path()).expanduser()
    command = build_hook_command(
        env_file=env,
        hook_script=hook_script,
        python_executable=python_executable,
    )
    existing = load_hooks_file(target)
    merged = merge_presence_hooks(existing, build_presence_hooks(command, timeout=timeout))
    changed = render_hooks(existing) != render_hooks(merged)
    backup_path = None
    if changed and not dry_run:
        backup_path = write_hooks_file(target, merged, backup=backup)

    return HookInstallResult(
        action="install",
        target_path=target,
        changed=changed,
        backup_path=backup_path,
        presence_hooks=count_presence_hooks(merged),
        rendered_json=render_hooks(merged),
    )


def uninstall_codex_hook(
    *,
    target_path: Path | None = None,
    dry_run: bool = False,
    backup: bool = True,
) -> HookInstallResult:
    target = (target_path or default_user_hooks_path()).expanduser()
    existing = load_hooks_file(target)
    pruned = prune_presence_hooks(existing)
    changed = render_hooks(existing) != render_hooks(pruned)
    backup_path = None
    if changed and not dry_run:
        backup_path = write_hooks_file(target, pruned, backup=backup)

    return HookInstallResult(
        action="uninstall",
        target_path=target,
        changed=changed,
        backup_path=backup_path,
        presence_hooks=count_presence_hooks(pruned),
        rendered_json=render_hooks(pruned),
    )


def print_result(result: HookInstallResult, dry_run: bool = False) -> None:
    mode = "dry-run" if dry_run else "ok"
    print(f"[{mode}] action={result.action}")
    print(f"target={result.target_path}")
    print(f"changed={str(result.changed).lower()}")
    print(f"presence_hooks={result.presence_hooks}")
    if result.backup_path:
        print(f"backup={result.backup_path}")
    if dry_run:
        print(result.rendered_json, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Instala/remove hooks do Codex.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Instala hooks do Codex.")
    install_parser.add_argument("--target", type=Path, help="Caminho do hooks.json.")
    install_parser.add_argument("--env-file", type=Path, help="Arquivo .env usado pelo hook.")
    install_parser.add_argument("--hook-script", type=Path, help="Script de hook.")
    install_parser.add_argument(
        "--python",
        help="Executavel Python. Padrao: o mesmo Python desta instalacao.",
    )
    install_parser.add_argument("--timeout", type=int, default=5, help="Timeout do hook.")
    install_parser.add_argument("--dry-run", action="store_true", help="Nao escreve arquivo.")
    install_parser.add_argument("--no-backup", action="store_true", help="Nao cria backup.")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove hooks instalados.")
    uninstall_parser.add_argument("--target", type=Path, help="Caminho do hooks.json.")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Nao escreve arquivo.")
    uninstall_parser.add_argument("--no-backup", action="store_true", help="Nao cria backup.")

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "install":
        result = install_codex_hook(
            target_path=args.target,
            env_file=args.env_file,
            hook_script=args.hook_script,
            python_executable=args.python,
            timeout=args.timeout,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
    else:
        result = uninstall_codex_hook(
            target_path=args.target,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
    print_result(result, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
