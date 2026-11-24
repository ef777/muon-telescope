import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "server", ROOT / "sim"):
    sys.path.insert(0, str(p))
