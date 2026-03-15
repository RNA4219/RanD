from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists():
    src_text = str(SRC)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)
