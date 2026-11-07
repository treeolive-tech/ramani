# ramani: src/ramani/settings.py
"""User-defined settings from command-line flags and ``[tool.ramani]``."""

import tomllib
from pathlib import Path

from .core import Styles


def norm_ext(ext: str) -> str:
    """Lower-case an extension and make sure it starts with a dot.

    Examples::

        norm_ext("MD")  # ".md"
        norm_ext(".txt")  # ".txt"
    """
    ext = ext.strip().lower()
    return ext if ext.startswith(".") else "." + ext


def parse_style(spec: str) -> tuple[str, tuple[str, str]]:
    """Parse ``EXT=START`` or ``EXT=START,END`` into ``(key, (start, end))``.

    Examples::

        parse_style(".abc=//")  # (".abc", ("//", ""))
        parse_style("vue=<!--,-->")  # (".vue", ("<!--", "-->"))
        parse_style("Jenkinsfile=//")  # ("Jenkinsfile", ("//", ""))
    """
    key, sep, value = spec.partition("=")
    key, start = key.strip(), value.split(",", 1)[0].strip()
    if not sep or not key or not start:
        raise ValueError(f"expected EXT=START or EXT=START,END, got {spec!r}")
    end = value.partition(",")[2].strip()
    if "." not in key and key.islower():
        key = "." + key
    return (key.lower() if key.startswith(".") else key), (start, end)


def _ramani_table(directory: Path) -> dict:
    """Return the ``[tool.ramani]`` table of ``directory/pyproject.toml`` ({} if missing).

    Examples::

        _ramani_table(Path("."))  # {"ignore-ext": [".txt"], "comments": {...}}
    """
    file = directory / "pyproject.toml"
    if not file.is_file():
        return {}
    try:
        return tomllib.loads(file.read_text(encoding="utf-8"))["tool"]["ramani"]
    except (KeyError, tomllib.TOMLDecodeError):
        return {}


def load_pyproject_styles(directory: Path) -> Styles:
    """Read ``[tool.ramani.comments]`` from ``directory/pyproject.toml``.

    Values are a start string or a ``[start, end]`` list.

    Examples::

        # [tool.ramani.comments]
        # ".abc" = "//"
        # ".tpl" = ["<!--", "-->"]
        load_pyproject_styles(Path("."))  # {".abc": ("//", ""), ".tpl": ("<!--", "-->")}
    """
    styles: Styles = {}
    for key, value in _ramani_table(directory).get("comments", {}).items():
        start, end = (
            (value, "")
            if isinstance(value, str)
            else (value[0], value[1] if len(value) > 1 else "")
        )
        styles[parse_style(f"{key}={start},{end}")[0]] = (start, end)
    return styles


def load_pyproject_ignore_exts(directory: Path) -> tuple[str, ...]:
    """Read ``ignore-ext`` from ``[tool.ramani]`` in ``directory/pyproject.toml``.

    Examples::

        # [tool.ramani]
        # ignore-ext = [".txt", "CSV"]
        load_pyproject_ignore_exts(Path("."))  # (".txt", ".csv")
    """
    value = _ramani_table(directory).get("ignore-ext", [])
    return tuple(
        norm_ext(ext) for ext in ([value] if isinstance(value, str) else value)
    )
