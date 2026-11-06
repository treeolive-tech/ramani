# ramani: src/ramani/color.py
"""Colour helpers; termcolor decides whether stdout can show colour."""

from collections.abc import Callable

Paint = Callable[..., str]

STATUS_COLORS = {
    "added": ("green", ()),
    "updated": ("yellow", ()),
    "removed": ("red", ()),
    "unchanged": ("white", ("dark",)),
}


def paint(text: str, color: str | None = None, *attrs: str) -> str:
    """Colour ``text``; plain when stdout isn't a terminal, or NO_COLOR is set.

    Examples::

        paint("added", "green", "bold")  # "\\x1b[1m\\x1b[32madded\\x1b[0m" in a terminal
        paint("added", "green")  # "added" when piped
    """
    from termcolor import colored  # only needed once there is output to colour

    return colored(text, color, attrs=list(attrs) or None)


def paint_status(status: str, paint_fn: Paint = paint) -> str:
    """Colour a status word, padded to 9 characters before colouring.

    Examples::

        paint_status("added", lambda t, c, *a: f"<{c}>{t}</>")  # "<green>added    </>"
    """
    color, attrs = STATUS_COLORS.get(status, (None, ()))
    return paint_fn(f"{status:<9}", color, *attrs)
