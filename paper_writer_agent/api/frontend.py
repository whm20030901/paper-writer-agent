from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_FRONTEND_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _FRONTEND_DIR / "templates"
_STATIC_DIR = _FRONTEND_DIR / "static"


@lru_cache(maxsize=1)
def load_index_html() -> str:
    return (_TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")


def frontend_static_dir() -> str:
    return str(_STATIC_DIR)
