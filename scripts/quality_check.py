from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str], *, cwd: Path = PROJECT_ROOT, clean_pythonpath: bool = False) -> None:
    env = os.environ.copy()
    if clean_pythonpath:
        env.pop("PYTHONPATH", None)
    else:
        source = str(PROJECT_ROOT / "src")
        current = env.get("PYTHONPATH")
        env["PYTHONPATH"] = source if not current else os.pathsep.join((source, current))
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> int:
    python = sys.executable
    run(
        [
            python,
            "-m",
            "compileall",
            "-q",
            "src/ai_presence_monitor",
            "hooks",
            "scripts",
            "tests",
            "main.py",
        ]
    )
    run([python, "-m", "unittest", "discover", "-s", "tests", "-q"])
    run([python, "-m", "coverage", "erase"])
    run([python, "-m", "coverage", "run", "-m", "unittest", "discover", "-s", "tests"])
    run([python, "-m", "coverage", "report", "--fail-under=80"])
    run([python, "-m", "ruff", "check", "src", "hooks", "scripts", "tests", "main.py"])
    run(
        [
            python,
            "-m",
            "mypy",
            "src/ai_presence_monitor",
            "scripts/build_release.py",
            "scripts/release_lib.py",
            "scripts/verify_release.py",
        ]
    )
    run(
        [
            "bash",
            "-n",
            "scripts/install-linux.sh",
            "scripts/install-user-command.sh",
            "scripts/quality-check.sh",
            "scripts/release-gate.sh",
            "scripts/test-python-matrix.sh",
        ],
        clean_pythonpath=True,
    )
    with tempfile.TemporaryDirectory() as workspace:
        build_output = Path(workspace) / "dist"
        run(
            [
                python,
                "-m",
                "build",
                "--no-isolation",
                str(PROJECT_ROOT),
                "--outdir",
                str(build_output),
            ],
            cwd=Path(workspace),
            clean_pythonpath=True,
        )
    run(["git", "diff", "--check"], clean_pythonpath=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
