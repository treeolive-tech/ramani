# ramani: src/ramani/__init__.py
"""ramani (Swahili for "map"): keep a path comment at the top of every source file."""

from .cli import main
from .core import mark_text, run, strip_text

__all__ = ["main", "mark_text", "run", "strip_text"]
