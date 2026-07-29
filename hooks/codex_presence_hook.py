#!/usr/bin/env python3
from pathlib import Path
import sys


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from ai_presence_monitor.codex_hook import main  # noqa: E402


if __name__ == "__main__":
    main()
