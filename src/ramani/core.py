# ramani: src/ramani/core.py
"""Add, refresh and strip path comments."""

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from functools import cache
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


@cache
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


HEAD = 8192  # characters looked at first; longer headers fall back to the whole file


def _head(text: str, front_matter: bool) -> tuple[list[str], int]:
    """Return the first lines of ``text`` and how many the comment must follow.

    Only splits the start of the file unless the header is unusually long.

    Examples::

        _head("#!/bin/sh\necho hi\n", False)  # (["#!/bin/sh\n", "echo hi\n"], 1)
    """
    chunk = text[:HEAD]
    lines = chunk.splitlines(keepends=True)
    if len(chunk) == len(text):
        return lines, _preamble(lines, front_matter)
    lines.pop()  # the last line may be cut off
    i = _preamble(lines, front_matter)
    opens_front_matter = (
        front_matter and bool(lines) and lines[0].rstrip() in ("---", "+++")
    )
    if i >= len(lines) or (opens_front_matter and i == 0):
        lines = text.splitlines(keepends=True)
        i = _preamble(lines, front_matter)
    return lines, i


def mark_text(
    text: str, rel: str, start: str, end: str = "", front_matter: bool = False
) -> tuple[str, str]:
    r"""Add or refresh the path comment; returns (new_text, status).

    Status is "added", "updated" (path changed) or "unchanged".

    Examples::

        mark_text("x = 1\n", "a/b.py", "#")  # ("# ramani: a/b.py\nx = 1\n", "added")
        mark_text("# ramani: old.py\nx = 1\n", "new.py", "#")  # ("# ramani: new.py\nx = 1\n", "updated")
    """
    head, i = _head(text, front_matter)
    eol = "\r\n" if "\r\n" in text[:HEAD] else "\n"
    comment = make_comment(rel, start, end)

    line = head[i] if i < len(head) else ""
    bare = line.rstrip("\r\n")
    pos = sum(map(len, head[:i]))
    if found := _mark_re(start, end).match(bare):
        if found["rel"] == rel:
            return text, "unchanged"
        new = comment + line[len(bare) :]
        return text[:pos] + new + text[pos + len(line) :], "updated"

    fix = eol if i and not head[i - 1].endswith(("\n", "\r")) else ""
    return text[:pos] + fix + comment + eol + text[pos:], "added"


def strip_text(
    text: str, start: str, end: str = "", front_matter: bool = False
) -> tuple[str, bool]:
    r"""Remove the path comment if present; returns (new_text, removed).

    Examples::

        strip_text("# ramani: a.py\nx = 1\n", "#")  # ("x = 1\n", True)
        strip_text("x = 1\n", "#")  # ("x = 1\n", False)
    """
    head, i = _head(text, front_matter)
    if i < len(head) and _mark_re(start, end).match(head[i].rstrip("\r\n")):
        pos = sum(map(len, head[:i]))
        return text[:pos] + text[pos + len(head[i]) :], True
    return text, False


@dataclass(frozen=True)
class Filters:
    """What the walk skips: folder globs, extensions, exact files, and whether .gitignore is read.

    Examples::

        Filters(dirs=("gen",), exts=(".js",))  # skip gen/ and *.js
        Filters(gitignore=False)  # ignore .gitignore files
        Filters(skip=("/proj/map.md",))  # skip that one file (absolute path)
    """

    dirs: tuple[str, ...] = IGNORE_DIRS
    exts: tuple[str, ...] = IGNORE_EXTS
    gitignore: bool = True
    skip: tuple[str, ...] = ()


DEFAULT = Filters()

GitStack = list[tuple[str, list[Rule]]]  # (folder relative to the root, its rules)


def join_rel(rel: str, name: str) -> str:
    """Append ``name`` to a relative posix path ("" is the root).

    Examples::

        join_rel("", "src")  # "src"
        join_rel("src", "app.py")  # "src/app.py"
    """
    return f"{rel}/{name}" if rel else name


def visible_children(
    directory: str,
    rel: str,
    stack: GitStack,
    filters: Filters = DEFAULT,
) -> tuple[list[tuple[str, bool]], GitStack]:
    """List a folder's non-ignored entries as (name, is_dir), folders first, plus the updated .gitignore stack.

    ``rel`` is the folder's path relative to the walk root ("" for the root).

    Examples::

        visible_children("/proj", "", [])  # ([("src", True), ("README.md", False)], [...])
    """
    if filters.gitignore:
        try:
            with open(
                os.path.join(directory, ".gitignore"), encoding="utf-8", errors="ignore"
            ) as f:
                stack = [*stack, (rel, parse_gitignore(f.read()))]
        except OSError:
            pass
    try:
        with os.scandir(directory) as it:
            entries = sorted(it, key=lambda e: e.name)
    except PermissionError:
        return [], stack
    exts = tuple(e.lower() for e in filters.exts)
    kept = []
    for entry in entries:
        if entry.is_symlink():
            continue
        name = entry.name
        is_dir = entry.is_dir(follow_symlinks=False)
        if is_dir and any(fnmatch(name, pattern) for pattern in filters.dirs):
            continue
        if not is_dir and name.lower().endswith(exts):
            continue
        if not is_dir and os.path.join(directory, name) in filters.skip:
            continue
        if stack and is_gitignored(join_rel(rel, name), is_dir, stack):
            continue
        kept.append((name, is_dir))
    kept.sort(key=lambda item: not item[1])
    return kept, stack


def iter_files(root: Path, filters: Filters = DEFAULT) -> Iterator[tuple[Path, str]]:
    """Yield (path, relative posix path) for files under ``root``, skipping ignored folders, extensions and symlinks.

    Examples::

        list(iter_files(Path(".")))  # [(PosixPath("/p/src/app.py"), "src/app.py"), ...]
    """

    def walk(directory: str, rel: str, stack: GitStack) -> Iterator[tuple[Path, str]]:
        children, stack = visible_children(directory, rel, stack, filters)
        for name, is_dir in children:
            path, child_rel = os.path.join(directory, name), join_rel(rel, name)
            if is_dir:
                yield from walk(path, child_rel, stack)
            else:
                yield Path(path), child_rel

    yield from walk(str(root), "", [])


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
    filters: Filters = DEFAULT,
    styles: Styles | None = None,
) -> list[tuple[str, str]]:
    """Process every file under ``root``; returns (relative path, status) pairs.

    Examples::

        run(Path("."), dry_run=True)  # [("src/app.py", "added"), ("data.xyz", "unsupported")]
    """
    root = root.resolve()
    if root.is_file():
        files = [(root, root.name)]
    else:
        files = iter_files(root, filters)
    return [
        (rel, process_file(path, rel, remove=remove, dry_run=dry_run, styles=styles))
        for path, rel in files
    ]
