# ramani: tests/test_formats.py
import json

import pytest

from ramani.cli import main
from ramani.core import Filters
from ramani.formats import FORMATS, build_nested, render


def touch(root, rel, content="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def proj(tmp_path):
    touch(tmp_path, "proj/src/app/main.py")
    touch(tmp_path, "proj/src/util.py")
    touch(tmp_path, "proj/README.md", "hi\n")
    return tmp_path / "proj"


def test_paths(proj):
    assert render(proj, "paths") == "src/app/main.py\nsrc/util.py\nREADME.md"


def test_markdown(proj):
    assert render(proj, "markdown") == (
        "- `proj/`\n"
        "  - `src/`\n"
        "    - `app/`\n"
        "      - `main.py`\n"
        "    - `util.py`\n"
        "  - `README.md`"
    )


def test_json(proj):
    main_py = {"name": "main.py", "type": "file"}
    app = {"name": "app", "type": "dir", "children": [main_py]}
    src = {
        "name": "src",
        "type": "dir",
        "children": [app, {"name": "util.py", "type": "file"}],
    }
    readme = {"name": "README.md", "type": "file"}
    expected = {"name": "proj", "type": "dir", "children": [src, readme]}
    assert json.loads(render(proj, "json")) == expected


def test_mermaid(proj):
    assert render(proj, "mermaid") == (
        "flowchart TD\n"
        '    n0["proj/"]\n'
        '    n1["src/"]\n'
        "    n0 --> n1\n"
        '    n2["app/"]\n'
        "    n1 --> n2\n"
        '    n3["main.py"]\n'
        "    n2 --> n3\n"
        '    n4["util.py"]\n'
        "    n1 --> n4\n"
        '    n5["README.md"]\n'
        "    n0 --> n5"
    )


def test_single_file(tmp_path):
    touch(tmp_path, "a.py")
    file = tmp_path / "a.py"
    assert render(file, "paths") == "a.py"
    assert render(file, "markdown") == "- `a.py`"
    assert render(file, "mermaid") == 'flowchart TD\n    n0["a.py"]'
    assert build_nested(file) == {"name": "a.py", "type": "file"}


def test_formats_apply_ignores(proj):
    touch(proj, "gen/out.py")
    touch(proj, "__pycache__/a.py")
    assert "gen" not in render(proj, "paths", Filters(dirs=("gen", "__pycache__")))
    assert "README.md" not in render(proj, "markdown", Filters(exts=(".md",)))
    assert "__pycache__" not in render(proj, "paths")


def test_unknown_format(proj):
    with pytest.raises(ValueError, match="unknown format"):
        render(proj, "yaml")


@pytest.mark.parametrize("fmt", FORMATS)
def test_cli_format_prints_without_modifying(proj, capsys, fmt):
    assert main([str(proj), "-f", fmt]) == 0
    assert capsys.readouterr().out.rstrip("\n") == render(proj, fmt)
    assert (proj / "src/util.py").read_text() == "x = 1\n"
