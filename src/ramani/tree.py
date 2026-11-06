# ramani: src/ramani/tree.py
"""Render a folder as a text tree and copy text to the clipboard."""

import os
from pathlib import Path

from .color import Paint, paint
from .core import DEFAULT, Filters, GitStack, join_rel, visible_children


def build_tree(root: Path, filters: Filters = DEFAULT) -> str:
    """Draw ``root`` and everything under it, honouring the same ignores as marking.

    Examples::

        build_tree(Path("proj"))
        # proj/
        # ├── src/
        # │   └── app.py
        # └── README.md
    """
    root = root.resolve()
    if root.is_file():
        return root.name

    lines = [f"{root.name}/"]

    def walk(directory: str, rel: str, stack: GitStack, prefix: str) -> None:
        children, stack = visible_children(directory, rel, stack, filters)
        for i, (name, is_dir) in enumerate(children):
            last = i == len(children) - 1
            lines.append(
                f"{prefix}{'└── ' if last else '├── '}{name}{'/' if is_dir else ''}"
            )
            if is_dir:
                walk(
                    os.path.join(directory, name),
                    join_rel(rel, name),
                    stack,
                    prefix + ("    " if last else "│   "),
                )

    walk(str(root), "", [], "")
    return "\n".join(lines)


def paint_tree(tree: str, paint_fn: Paint = paint) -> str:
    """Colour a drawn tree: folders bold blue, branch lines dim.

    Examples::

        paint_tree("proj/\\n└── a.py")  # same text with colour codes in a terminal
    """
    out = []
    for line in tree.splitlines():
        name = line.lstrip("│├└─ ")
        branch = line[: len(line) - len(name)]
        if name.endswith("/"):
            name = paint_fn(name, "blue", "bold")
        out.append((paint_fn(branch, "white", "dark") if branch else "") + name)
    return "\n".join(out)


def copy_to_clipboard(text: str) -> None:
    """Copy ``text`` with pyperclip; raises RuntimeError with a readable reason on failure.

    Examples::

        copy_to_clipboard("proj/\\n└── a.py")  # None
    """
    try:
        import pyperclip
    except ImportError:
        raise RuntimeError("pyperclip is not installed (uv add pyperclip)") from None
    try:
        pyperclip.copy(text)
    except pyperclip.PyperclipException as err:
        raise RuntimeError(f"no clipboard available: {err}") from None
