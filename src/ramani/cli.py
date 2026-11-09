# ramani: src/ramani/cli.py
"""Command-line interface."""

import argparse
import sys
from collections import Counter
from dataclasses import replace
from itertools import islice
from pathlib import Path

from .color import paint, paint_count, paint_err, paint_path, paint_status
from .config import IGNORE_DIRS, IGNORE_EXTS
from .core import Filters, Styles, iter_files, run
from .formats import EXT_FORMATS, FORMAT_EXTS, FORMATS, format_for, render
from .settings import (
    env_flag,
    env_int,
    env_list,
    load_pyproject_ignore_dirs,
    load_pyproject_ignore_exts,
    load_pyproject_styles,
    norm_ext,
    parse_style,
)
from .tree import copy_to_clipboard, paint_tree
from .workspace import ensure_dir

CHANGED = {"added", "updated", "removed"}
HIDDEN = {"skipped", "unsupported"}
MAX_FILES = 1000


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


def _shown(path: Path) -> str:
    """Show a path relative to the current folder when it is inside it.

    Examples::

        _shown(Path.cwd() / "docs/map.md")  # "docs/map.md"
        _shown(Path("/elsewhere/map.md"))  # "/elsewhere/map.md"
    """
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def _too_many(root: Path, filters: Filters, limit: int) -> bool:
    """Tell whether ``root`` holds more than ``limit`` files, stopping the count early.

    Examples::

        _too_many(Path("C:/"), Filters(), 1000)  # True
        _too_many(Path("small-project"), Filters(), 1000)  # False
    """
    files = iter_files(root.resolve(), filters)
    return sum(1 for _ in islice(files, limit + 1)) > limit


def _confirmed(root: Path, limit: int) -> bool:
    """Ask whether to go on; False if declined or there is no terminal to ask.

    Examples::

        _confirmed(Path("."), 1000)  # True after typing "y"
    """
    warning = paint_err(
        f"ramani: more than {limit} files under {root.resolve()}.", "yellow", "bold"
    )
    if not sys.stdin.isatty():
        print(f"{warning} Pass --yes to continue.", file=sys.stderr)
        return False
    try:
        return input(f"{warning} Continue? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


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
        help="extra extension to skip, e.g. -e .txt (repeatable; also ignore-ext in [tool.ramani] or RAMANI_IGNORE_EXT)",
    )
    p.add_argument(
        "-d",
        "--ignore-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="extra folder name or glob to skip (repeatable; also ignore-dir in [tool.ramani] or RAMANI_IGNORE_DIR)",
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
        "--no-gitignore",
        action="store_true",
        help="don't read .gitignore files (also RAMANI_NO_GITIGNORE=1)",
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
        "--max-files",
        type=int,
        default=env_int("RAMANI_MAX_FILES", MAX_FILES),
        metavar="N",
        help=f"ask before writing to more than N files (default: {MAX_FILES}; also RAMANI_MAX_FILES)",
    )
    p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="don't ask for confirmation, even for a large number of files",
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
        "-f",
        "--format",
        choices=FORMATS,
        help="map the project in this format instead of marking files (same ignores)",
    )
    p.add_argument(
        "--copy",
        action="store_true",
        help="copy the map to the clipboard (a tree unless -f is given)",
    )
    p.add_argument(
        "-o",
        "--output",
        nargs="?",
        const="",
        default=None,
        metavar="FILE",
        help="save the map to FILE (format from its extension, or -f); with no FILE, save to .ramani/map.<ext> (put PATH before -o)",
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

    root = args.path if args.path.is_dir() else args.path.parent
    folders = list(dict.fromkeys([Path.cwd(), root.resolve()]))

    filters = Filters(
        dirs=(
            *IGNORE_DIRS,
            *(d for folder in folders for d in load_pyproject_ignore_dirs(folder)),
            *env_list("RAMANI_IGNORE_DIR"),
            *args.ignore_dir,
        ),
        exts=(
            *IGNORE_EXTS,
            *(ext for folder in folders for ext in load_pyproject_ignore_exts(folder)),
            *map(norm_ext, env_list("RAMANI_IGNORE_EXT")),
            *map(norm_ext, args.ignore_ext),
        ),
        gitignore=not (args.no_gitignore or env_flag("RAMANI_NO_GITIGNORE")),
    )

    if args.tree or args.copy or args.format or args.output is not None:
        if args.remove or args.check:
            parser.error(
                "--tree/--format/--copy/--output can't be combined with --remove or --check"
            )
        if args.tree and args.format not in (None, "tree"):
            parser.error(f"--tree can't be combined with --format {args.format}")
        fmt = args.format or ("tree" if args.tree else None)
        out = Path(args.output) if args.output else None
        if out is not None:
            if out.is_dir():
                parser.error(
                    f"{out} is a folder, not a file; put the folder before -o (ramani {out} -o)"
                )
            fmt = fmt or format_for(out)
            if fmt is None:
                parser.error(
                    f"can't tell the format of {out.name!r}: use -f, or one of "
                    f"{', '.join(EXT_FORMATS)}"
                )
            filters = replace(filters, skip=(str(out.resolve()),))
        fmt = fmt or "tree"
        text = render(args.path, fmt, filters)
        if args.output is None:
            print(paint_tree(text) if fmt == "tree" else text)
        else:
            try:
                dest = out or ensure_dir(root.resolve()) / f"map{FORMAT_EXTS[fmt]}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text + "\n", encoding="utf-8", newline="\n")
            except (OSError, RuntimeError) as err:
                failed = paint_err("ramani: could not save the map:", "red", "bold")
                print(f"{failed} {err}", file=sys.stderr)
                return 1
            print(paint_err(f"(saved to {_shown(dest)})", "green"), file=sys.stderr)
        if args.copy:
            try:
                copy_to_clipboard(text)
            except RuntimeError as err:
                failed = paint_err(
                    "ramani: could not copy to clipboard:", "red", "bold"
                )
                print(f"{failed} {err}", file=sys.stderr)
                return 1
            print(paint_err("(copied to clipboard)", "green"), file=sys.stderr)
        return 0

    styles: Styles = {}
    for folder in folders:
        styles.update(load_pyproject_styles(folder))
    try:
        styles.update(parse_style(spec) for spec in args.comment)
    except ValueError as err:
        parser.error(str(err))

    dry_run = args.dry_run or args.check
    if (
        not (dry_run or args.yes)
        and args.path.is_dir()
        and _too_many(args.path, filters, args.max_files)
        and not _confirmed(args.path, args.max_files)
    ):
        print(paint_err("aborted, nothing was changed", "red"), file=sys.stderr)
        return 1

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
