# ramani: src/ramani/color.py
"""Colour helpers; termcolor decides whether stdout can show colour."""

import sys
from collections.abc import Callable

Paint = Callable[..., str]

STATUS_COLORS = {
    "added": ("green", ()),
    "updated": ("yellow", ()),
    "removed": ("red", ()),
    "unchanged": ("white", ("dark",)),
    "unsupported": ("magenta", ()),
    "skipped": ("yellow", ("dark",)),
}


def paint(text: str, color: str | None = None, *attrs: str, force: bool = False) -> str:
    """Colour ``text``; plain when stdout isn't a terminal, or NO_COLOR is set.

    Examples::

        paint("added", "green", "bold")  # "\\x1b[1m\\x1b[32madded\\x1b[0m" in a terminal
        paint("added", "green")  # "added" when piped
    """
    from termcolor import colored  # only needed once there is output to colour

    return colored(text, color, attrs=list(attrs) or None, force_color=force or None)


def paint_err(text: str, color: str | None = None, *attrs: str) -> str:
    """Colour ``text`` for stderr: only when stderr itself is a terminal.

    Examples::

        paint_err("failed", "red")  # "failed" in red on a terminal, plain when redirected
    """
    if not sys.stderr.isatty():
        return text
    return paint(text, color, *attrs, force=True)  # NO_COLOR still wins


def paint_status(status: str, paint_fn: Paint = paint) -> str:
    """Colour a status word, padded to 9 characters before colouring.

    Examples::

        paint_status("added", lambda t, c, *a: f"<{c}>{t}</>")  # "<green>added    </>"
    """
    color, attrs = STATUS_COLORS.get(status, (None, ()))
    return paint_fn(f"{status:<9}", color, *attrs)


def paint_count(n: int, status: str, paint_fn: Paint = paint) -> str:
    """Colour a "5 added" style count with its status colour.

    Examples::

        paint_count(5, "added", lambda t, c, *a: f"<{c}>{t}</>")  # "<green>5 added</>"
    """
    color, attrs = STATUS_COLORS.get(status, (None, ()))
    return paint_fn(f"{n} {status}", color, *attrs)


def paint_path(rel: str, paint_fn: Paint = paint) -> str:
    """Dim the folders of a path and bold the file name, so the name stands out.

    Examples::

        paint_path("src/a.py", lambda t, c, *a: f"<{t}>")  # "<src/><a.py>"
    """
    folder, sep, name = rel.rpartition("/")
    dim = paint_fn(folder + sep, "white", "dark") if sep else ""
    return dim + paint_fn(name, None, "bold")
