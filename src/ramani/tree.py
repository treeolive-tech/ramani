# ramani: src/ramani/tree.py
"""Render a folder as a text tree and copy text to the clipboard."""

from pathlib import Path

from .config import IGNORE_DIRS, IGNORE_EXTS
from .core import GitStack, visible_children


def build_tree(
    root: Path,
    ignore_dirs: tuple[str, ...] = IGNORE_DIRS,
    ignore_exts: tuple[str, ...] = IGNORE_EXTS,
    use_gitignore: bool = True,
) -> str:
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

    def walk(directory: Path, stack: GitStack, prefix: str) -> None:
        children, stack = visible_children(
            directory, stack, ignore_dirs, ignore_exts, use_gitignore
        )
        for i, (entry, is_dir) in enumerate(children):
            last = i == len(children) - 1
            lines.append(
                f"{prefix}{'└── ' if last else '├── '}{entry.name}{'/' if is_dir else ''}"
            )
            if is_dir:
                walk(entry, stack, prefix + ("    " if last else "│   "))

    walk(root, [], "")
    return "\n".join(lines)


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
