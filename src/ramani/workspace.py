# ramani: src/ramani/workspace.py
"""The ``.ramani`` folder: created only when needed, ignored by git and by ramani."""

from pathlib import Path

DIR = ".ramani"
START = "# >>> ramani managed block (do not edit) >>>"
END = "# <<< ramani managed block <<<"
BLOCK = f"{START}\n*\n{END}\n"


def merge_block(text: str) -> str:
    """Put ramani's block into ``.gitignore`` text, replacing an old copy and keeping the rest.

    Examples::

        merge_block("")  # BLOCK
        merge_block("keep.svg\n")  # "keep.svg\n" + BLOCK
        merge_block(merge_block("keep.svg\n"))  # same as the line above
    """
    start, end = text.find(START), text.find(END)
    if 0 <= start < end:
        end = text.find("\n", end)
        end = len(text) if end == -1 else end + 1
        return text[:start] + BLOCK + text[end:]
    if text and not text.endswith("\n"):
        text += "\n"
    return text + BLOCK


def ensure_dir(root: Path) -> Path:
    """Create ``root/.ramani`` with its ``.gitignore`` if needed; returns the folder.

    Examples::

        ensure_dir(Path("proj"))  # Path("proj/.ramani")
    """
    folder = root / DIR
    try:
        folder.mkdir(exist_ok=True)
        file = folder / ".gitignore"
        old = file.read_text(encoding="utf-8") if file.exists() else ""
        if (new := merge_block(old)) != old:
            file.write_text(new, encoding="utf-8")
    except OSError as err:
        raise RuntimeError(f"can't prepare {folder}: {err}") from None
    return folder
