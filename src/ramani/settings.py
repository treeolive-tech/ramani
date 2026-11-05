# ramani: src/ramani/settings.py
"""User-defined comment styles from ``--comment`` flags and ``[tool.ramani]``."""

import tomllib
from pathlib import Path

from .core import Styles


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


def load_pyproject_styles(directory: Path) -> Styles:
    """Read ``[tool.ramani.comments]`` from ``directory/pyproject.toml``.

    Values are a start string or a ``[start, end]`` list.

    Examples::

        # [tool.ramani.comments]
        # ".abc" = "//"
        # ".tpl" = ["<!--", "-->"]
        load_pyproject_styles(Path("."))  # {".abc": ("//", ""), ".tpl": ("<!--", "-->")}
    """
    file = directory / "pyproject.toml"
    if not file.is_file():
        return {}
    try:
        table = tomllib.loads(file.read_text(encoding="utf-8"))["tool"]["ramani"][
            "comments"
        ]
    except (KeyError, tomllib.TOMLDecodeError):
        return {}
    styles: Styles = {}
    for key, value in table.items():
        start, end = (
            (value, "")
            if isinstance(value, str)
            else (value[0], value[1] if len(value) > 1 else "")
        )
        styles[parse_style(f"{key}={start},{end}")[0]] = (start, end)
    return styles
