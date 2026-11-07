# ramani: src/ramani/formats.py
"""Other ways to map a project: flat paths, Markdown, JSON and Mermaid."""

import json
import os
from collections.abc import Iterator
from itertools import count
from pathlib import Path

from .core import DEFAULT, Filters, GitStack, join_rel, visible_children
from .tree import build_tree

FORMATS = ("tree", "paths", "markdown", "json", "mermaid")

Node = dict  # {"name": str, "type": "dir" | "file", "children": [Node]} (dirs only)


def build_nested(root: Path, filters: Filters = DEFAULT) -> Node:
    """Read ``root`` into nested dicts, honouring the same ignores as marking.

    Examples::

        build_nested(Path("proj"))
        # {"name": "proj", "type": "dir", "children": [{"name": "a.py", "type": "file"}]}
    """
    root = root.resolve()
    if root.is_file():
        return {"name": root.name, "type": "file"}

    def walk(directory: str, rel: str, stack: GitStack) -> list[Node]:
        children, stack = visible_children(directory, rel, stack, filters)
        return [
            {
                "name": name,
                "type": "dir",
                "children": walk(
                    os.path.join(directory, name), join_rel(rel, name), stack
                ),
            }
            if is_dir
            else {"name": name, "type": "file"}
            for name, is_dir in children
        ]

    return {"name": root.name, "type": "dir", "children": walk(str(root), "", [])}


def _label(node: Node) -> str:
    """Return a node's name, with a trailing slash for folders.

    Examples::

        _label({"name": "src", "type": "dir", "children": []})  # "src/"
    """
    return node["name"] + ("/" if node["type"] == "dir" else "")


def _paths(node: Node) -> Iterator[str]:
    """Yield the path of every file under a folder node, relative to it.

    Examples::

        list(_paths(build_nested(Path("proj"))))  # ["src/app.py", "README.md"]
    """
    for child in node.get("children", []):
        if child["type"] == "file":
            yield child["name"]
        else:
            yield from (f"{child['name']}/{path}" for path in _paths(child))


def _bullets(node: Node, depth: int = 0) -> Iterator[str]:
    """Yield an indented Markdown bullet for a node and everything below it.

    Examples::

        list(_bullets({"name": "a.py", "type": "file"}))  # ["- `a.py`"]
    """
    yield f"{'  ' * depth}- `{_label(node)}`"
    for child in node.get("children", []):
        yield from _bullets(child, depth + 1)


def _mermaid(node: Node, ids: Iterator[int], parent: str = "") -> Iterator[str]:
    """Yield Mermaid node and edge lines for a node and everything below it.

    Examples::

        list(_mermaid({"name": "a.py", "type": "file"}, count()))  # ['    n0["a.py"]']
    """
    me = f"n{next(ids)}"
    yield f'    {me}["{_label(node).replace(chr(34), "#quot;")}"]'
    if parent:
        yield f"    {parent} --> {me}"
    for child in node.get("children", []):
        yield from _mermaid(child, ids, me)


def render(root: Path, fmt: str = "tree", filters: Filters = DEFAULT) -> str:
    """Map ``root`` in one of the ``FORMATS``.

    Examples::

        render(Path("proj"), "paths")  # "src/app.py\\nREADME.md"
        render(Path("proj"), "markdown")  # "- `proj/`\\n  - `src/`\\n ..."
    """
    if fmt == "tree":
        return build_tree(root, filters)
    node = build_nested(root, filters)
    if fmt == "paths":
        return node["name"] if node["type"] == "file" else "\n".join(_paths(node))
    if fmt == "markdown":
        return "\n".join(_bullets(node))
    if fmt == "json":
        return json.dumps(node, indent=2, ensure_ascii=False)
    if fmt == "mermaid":
        return "\n".join(["flowchart TD", *_mermaid(node, count())])
    raise ValueError(f"unknown format {fmt!r}; choose from {', '.join(FORMATS)}")
