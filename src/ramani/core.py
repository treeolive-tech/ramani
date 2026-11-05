# ramani: src/ramani/core.py
"""Add, refresh and strip path comments."""

import re
from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import Path

from .config import (
    COMMENT_STYLES,
    FRONT_MATTER_EXTS,
    IGNORE_DIRS,
    IGNORE_EXTS,
    KEEP_FIRST,
    MARKER,
    NAME_STYLES,
)
from .gitignore import Rule, is_gitignored, parse_gitignore

Styles = dict[str, tuple[str, str]]


def style_for(path: Path, extra: Styles | None = None) -> tuple[str, str] | None:
    """Return the (start, end) comment style for a file, or None if unsupported.

    ``extra`` maps extensions or file names to styles and beats the built-ins.

    Examples::

        style_for(Path("app.py"))  # ("#", "")
        style_for(Path("logo.png"))  # None
        style_for(Path("a.abc"), {".abc": ("//", "")})  # ("//", "")
    """
    extra = extra or {}
    suffix = path.suffix.lower()
    return (
        extra.get(path.name)
        or extra.get(suffix)
        or NAME_STYLES.get(path.name)
        or COMMENT_STYLES.get(suffix)
    )


def make_comment(rel: str, start: str, end: str = "") -> str:
    """Build the marker comment for a relative path.

    Examples::

        make_comment("src/a.py", "#")  # "# ramani: src/a.py"
        make_comment("a.html", "<!--", "-->")  # "<!-- ramani: a.html -->"
    """
    return f"{start} {MARKER} {rel}" + (f" {end}" if end else "")


def _mark_re(start: str, end: str) -> "re.Pattern[str]":
    """Regex matching a marker comment; the stored path is the ``rel`` group."""
    tail = rf"\s*{re.escape(end)}" if end else ""
    return re.compile(
        rf"^\s*{re.escape(start)}\s*{re.escape(MARKER)}\s*(?P<rel>.*?){tail}\s*$"
    )


def _preamble(lines: list[str], front_matter: bool = False) -> int:
    """Count leading lines the comment must come after (shebang, encoding, XML declaration, front matter).

    Examples::

        _preamble(["#!/bin/sh", "echo hi"])  # 1
        _preamble(["import os"])  # 0
        _preamble(["---\n", "title: A\n", "---\n", "# Hi\n"], front_matter=True)  # 3
    """
    n = 0
    if front_matter and lines and (fence := lines[0].rstrip()) in ("---", "+++"):
        closers = (fence, "...") if fence == "---" else (fence,)
        for j in range(1, len(lines)):
            if lines[j].rstrip() in closers:
                n = j + 1
                break
    while n < len(lines) and lines[n].startswith(KEEP_FIRST):
        n += 1
    return n


def mark_text(
    text: str, rel: str, start: str, end: str = "", front_matter: bool = False
) -> tuple[str, str]:
    r"""Add or refresh the path comment; returns (new_text, status).

    Status is "added", "updated" (path changed) or "unchanged".

    Examples::

        mark_text("x = 1\n", "a/b.py", "#")  # ("# ramani: a/b.py\nx = 1\n", "added")
        mark_text("# ramani: old.py\nx = 1\n", "new.py", "#")  # ("# ramani: new.py\nx = 1\n", "updated")
    """
    lines = text.splitlines(keepends=True)
    eol = "\r\n" if "\r\n" in text else "\n"
    i = _preamble(lines, front_matter)
    comment = make_comment(rel, start, end)

    line = lines[i] if i < len(lines) else ""
    bare = line.rstrip("\r\n")
    found = _mark_re(start, end).match(bare)
    if found:
        if found["rel"] == rel:
            return text, "unchanged"
        lines[i] = comment + line[len(bare) :]
        return "".join(lines), "updated"

    if i and not lines[i - 1].endswith(("\n", "\r")):
        lines[i - 1] += eol
    lines.insert(i, comment + eol)
    return "".join(lines), "added"


def strip_text(
    text: str, start: str, end: str = "", front_matter: bool = False
) -> tuple[str, bool]:
    r"""Remove the path comment if present; returns (new_text, removed).

    Examples::

        strip_text("# ramani: a.py\nx = 1\n", "#")  # ("x = 1\n", True)
        strip_text("x = 1\n", "#")  # ("x = 1\n", False)
    """
    lines = text.splitlines(keepends=True)
    i = _preamble(lines, front_matter)
    if i < len(lines) and _mark_re(start, end).match(lines[i].rstrip("\r\n")):
        del lines[i]
        return "".join(lines), True
    return text, False


GitStack = list[tuple[Path, list[Rule]]]


def visible_children(
    directory: Path,
    stack: GitStack,
    ignore_dirs: tuple[str, ...] = IGNORE_DIRS,
    ignore_exts: tuple[str, ...] = IGNORE_EXTS,
    use_gitignore: bool = True,
) -> tuple[list[tuple[Path, bool]], GitStack]:
    """List a folder's non-ignored entries as (path, is_dir), folders first, plus the updated .gitignore stack.

    Examples::

        visible_children(Path("."), [])  # ([(Path("src"), True), (Path("README.md"), False)], [...])
    """
    gitignore = directory / ".gitignore"
    if use_gitignore and gitignore.is_file():
        rules = parse_gitignore(gitignore.read_text(encoding="utf-8", errors="ignore"))
        stack = [*stack, (directory, rules)]
    try:
        entries = sorted(directory.iterdir(), key=lambda p: p.name)
    except PermissionError:
        return [], stack
    exts = tuple(e.lower() for e in ignore_exts)
    kept = []
    for entry in entries:
        if entry.is_symlink():
            continue
        is_dir = entry.is_dir()
        if is_dir and any(fnmatch(entry.name, pattern) for pattern in ignore_dirs):
            continue
        if not is_dir and entry.name.lower().endswith(exts):
            continue
        if use_gitignore and is_gitignored(entry, is_dir, stack):
            continue
        kept.append((entry, is_dir))
    kept.sort(key=lambda item: not item[1])
    return kept, stack


def iter_files(
    root: Path,
    ignore_dirs: tuple[str, ...] = IGNORE_DIRS,
    ignore_exts: tuple[str, ...] = IGNORE_EXTS,
    use_gitignore: bool = True,
) -> Iterator[Path]:
    """Yield files under ``root``, skipping ignored folders, extensions and symlinks.

    Examples::

        list(iter_files(Path(".")))  # [PosixPath("src/app.py"), ...]
    """

    def walk(directory: Path, stack: GitStack) -> Iterator[Path]:
        children, stack = visible_children(
            directory, stack, ignore_dirs, ignore_exts, use_gitignore
        )
        for entry, is_dir in children:
            if is_dir:
                yield from walk(entry, stack)
            else:
                yield entry

    yield from walk(root, [])


def process_file(
    path: Path,
    rel: str,
    *,
    remove: bool = False,
    dry_run: bool = False,
    styles: Styles | None = None,
) -> str:
    """Add, refresh or strip one file's comment; returns its status.

    Status is "added", "updated", "removed", "unchanged", "unsupported" (no comment
    style known) or "skipped" (unreadable, not UTF-8, or binary: contains NUL bytes).

    Examples::

        process_file(Path("app.py"), "app.py")  # "added"
        process_file(Path("data.xyz"), "data.xyz")  # "unsupported"
        process_file(Path("blob.py"), "blob.py")  # "skipped" (has NUL bytes)
    """
    style = style_for(path, styles)
    if style is None:
        return "unsupported"
    try:
        raw = path.read_text(encoding="utf-8", newline="")
    except (UnicodeDecodeError, OSError):
        return "skipped"
    if "\0" in raw:
        return "skipped"

    bom, text = ("﻿", raw[1:]) if raw.startswith("﻿") else ("", raw)
    front = path.suffix.lower() in FRONT_MATTER_EXTS
    if remove:
        new, removed = strip_text(text, *style, front_matter=front)
        status = "removed" if removed else "unchanged"
    else:
        new, status = mark_text(text, rel, *style, front_matter=front)

    if new != text and not dry_run:
        path.write_text(bom + new, encoding="utf-8", newline="")
    return status


def run(
    root: Path,
    *,
    remove: bool = False,
    dry_run: bool = False,
    ignore_dirs: tuple[str, ...] = IGNORE_DIRS,
    ignore_exts: tuple[str, ...] = IGNORE_EXTS,
    use_gitignore: bool = True,
    styles: Styles | None = None,
) -> list[tuple[str, str]]:
    """Process every file under ``root``; returns (relative path, status) pairs.

    Examples::

        run(Path("."), dry_run=True)  # [("src/app.py", "added"), ("data.xyz", "unsupported")]
    """
    root = root.resolve()
    if root.is_file():
        files, base = [root], root.parent
    else:
        files, base = iter_files(root, ignore_dirs, ignore_exts, use_gitignore), root
    results = []
    for file in files:
        rel = file.relative_to(base).as_posix()
        results.append(
            (
                rel,
                process_file(file, rel, remove=remove, dry_run=dry_run, styles=styles),
            )
        )
    return results
