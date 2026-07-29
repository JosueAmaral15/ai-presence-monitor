import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_ROOT))

from ai_presence_monitor.interactive import main  # noqa: E402

if __name__ == "__main__":
    main()
