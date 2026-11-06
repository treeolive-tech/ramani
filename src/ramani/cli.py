# ramani: src/ramani/cli.py
"""Command-line interface."""

import argparse
import sys
from collections import Counter
from pathlib import Path

from .color import paint, paint_count, paint_err, paint_path, paint_status
from .config import IGNORE_DIRS, IGNORE_EXTS
from .core import Filters, Styles, run
from .settings import load_pyproject_styles, parse_style
from .tree import build_tree, copy_to_clipboard, paint_tree

CHANGED = {"added", "updated", "removed"}
HIDDEN = {"skipped", "unsupported"}


def _version() -> str:
    """Return the installed version, or "unknown" if ramani isn't installed.

    Examples::

        _version()  # "0.1.0a4"
    """
    from importlib.metadata import (
        PackageNotFoundError,
        version,
    )  # slow import, only needed here

    try:
        return version("ramani")
    except PackageNotFoundError:
        return "unknown"


def _label(rel: str) -> str:
    """Name a file type for the report: its extension, or the file name if it has none.

    Examples::

        _label("src/data.xyz")  # ".xyz"
        _label("bin/runner")  # "runner"
    """
    path = Path(rel)
    return path.suffix.lower() or path.name


def _norm_ext(ext: str) -> str:
    """Lower-case an extension and make sure it starts with a dot.

    Examples::

        _norm_ext("MD")  # ".md"
    """
    ext = ext.lower()
    return ext if ext.startswith(".") else "." + ext


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    p = argparse.ArgumentParser(
        prog="ramani",
        description="Keep a path comment at the top of every source file, refreshed when files move.",
    )
    p.add_argument(
        "-V", "--version", action="store_true", help="print the version and exit"
    )
    p.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="folder or file (default: current folder)",
    )
    p.add_argument(
        "-e",
        "--ignore-ext",
        action="append",
        default=[],
        metavar="EXT",
        help="extra extension to skip, e.g. -e .txt (repeatable)",
    )
    p.add_argument(
        "-d",
        "--ignore-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="extra folder name or glob to skip (repeatable)",
    )
    p.add_argument(
        "-c",
        "--comment",
        action="append",
        default=[],
        metavar="EXT=START[,END]",
        help="comment style for an extension, e.g. -c .abc=// or -c .tpl='<!--,-->' (repeatable)",
    )
    p.add_argument(
        "--no-gitignore", action="store_true", help="don't read .gitignore files"
    )
    p.add_argument(
        "--remove",
        action="store_true",
        help="strip ramani comments instead of adding them",
    )
    p.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="show what would change without writing",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="dry run that exits 1 if any file needs changes",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true", help="also list unchanged files"
    )
    p.add_argument(
        "-t",
        "--tree",
        action="store_true",
        help="print the folder structure as a tree instead of marking files (same ignores)",
    )
    p.add_argument(
        "--copy",
        action="store_true",
        help="copy the tree to the clipboard (implies --tree)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"{parser.prog} {_version()}")
        return 0
    if not args.path.exists():
        parser.error(f"path not found: {args.path}")

    filters = Filters(
        dirs=(*IGNORE_DIRS, *args.ignore_dir),
        exts=(*IGNORE_EXTS, *map(_norm_ext, args.ignore_ext)),
        gitignore=not args.no_gitignore,
    )

    if args.tree or args.copy:
        if args.remove or args.check:
            parser.error("--tree/--copy can't be combined with --remove or --check")
        tree = build_tree(args.path, filters)
        print(paint_tree(tree))
        if args.copy:
            try:
                copy_to_clipboard(tree)
            except RuntimeError as err:
                failed = paint_err(
                    "ramani: could not copy to clipboard:", "red", "bold"
                )
                print(f"{failed} {err}", file=sys.stderr)
                return 1
            print(paint_err("(copied to clipboard)", "green"), file=sys.stderr)
        return 0

    root = args.path if args.path.is_dir() else args.path.parent
    styles: Styles = {}
    for folder in dict.fromkeys([Path.cwd(), root.resolve()]):
        styles.update(load_pyproject_styles(folder))
    try:
        styles.update(parse_style(spec) for spec in args.comment)
    except ValueError as err:
        parser.error(str(err))

    dry_run = args.dry_run or args.check
    results = run(
        args.path,
        remove=args.remove,
        dry_run=dry_run,
        filters=filters,
        styles=styles,
    )

    spaced = (
        sys.stdout.isatty()
    )  # blank lines set the report apart from other tools' output
    if spaced:
        print()
    for rel, status in results:
        if status in CHANGED or (args.verbose and status not in HIDDEN):
            print(f"{paint_status(status)} {paint_path(rel)}")

    counts = Counter(status for _, status in results)
    summary = ", ".join(paint_count(n, s) for s, n in sorted(counts.items()))
    print(
        (paint("(dry run) ", "cyan", "bold") if dry_run else "")
        + (summary or paint("no files found", "yellow"))
    )

    unknown = Counter(_label(rel) for rel, status in results if status == "unsupported")
    if unknown:
        listed = ", ".join(
            f"{paint(label, None, 'bold')} x{n}" for label, n in sorted(unknown.items())
        )
        print(f"{paint('no comment style for:', 'yellow')} {listed}")
        flag = paint("-c EXT=START[,END]", "cyan")
        table = paint("[tool.ramani.comments]", "cyan")
        print(f"  add one with {flag} or {table} in pyproject.toml")

    changed = sum(counts[status] for status in CHANGED)
    if args.check:
        print(
            paint(
                f"✗ {changed} file(s) need changes; run ramani to fix them",
                "red",
                "bold",
            )
            if changed
            else paint("✓ all path comments are up to date", "green", "bold")
        )
    if spaced:
        print()
    return 1 if args.check and changed else 0
