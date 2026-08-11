from __future__ import annotations

import argparse
import subprocess
import sys


def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=creationflags,
        )
    except OSError:
        process.kill()
        return
    if result.returncode != 0:
        process.kill()


def run(argv: list[str], duration: float) -> int:
    if duration <= 0:
        return 2
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except OSError:
        return 2
    try:
        return process.wait(timeout=duration)
    except subprocess.TimeoutExpired:
        _terminate_tree(process)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return 1
        return 124
    except KeyboardInterrupt:
        _terminate_tree(process)
        return 130


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(args)
    command = parsed.command[1:] if parsed.command[:1] == ["--"] else parsed.command
    if not command:
        return 2
    return run(command, parsed.duration)


if __name__ == "__main__":
    sys.exit(main())
