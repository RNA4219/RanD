from pathlib import Path

_pkg_dir = Path(__file__).resolve().parent
_src_pkg = _pkg_dir.parent / "src" / "rand_research"
__path__ = [str(_src_pkg)]
