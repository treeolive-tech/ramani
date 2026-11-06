# ramani: tests/test_tree.py
import sys

import pytest

from ramani.cli import main
from ramani.core import Filters
from ramani.tree import build_tree, copy_to_clipboard


def touch(root, rel, content="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_build_tree_shape(tmp_path):
    touch(tmp_path, "proj/src/app/main.py")
    touch(tmp_path, "proj/src/util.py")
    touch(tmp_path, "proj/tests/test_a.py")
    touch(tmp_path, "proj/README.md", "hi\n")
    assert build_tree(tmp_path / "proj") == (
        "proj/\n"
        "├── src/\n"
        "│   ├── app/\n"
        "│   │   └── main.py\n"
        "│   └── util.py\n"
        "├── tests/\n"
        "│   └── test_a.py\n"
        "└── README.md"
    )


def test_build_tree_applies_ignores(tmp_path):
    touch(tmp_path, "p/a.py")
    touch(tmp_path, "p/__pycache__/a.pyc", "junk")
    touch(tmp_path, "p/node_modules/x/index.js")
    touch(tmp_path, "p/gen/out.py")
    touch(tmp_path, "p/.gitignore", "gen/\n")
    touch(tmp_path, "p/notes.txt", "n\n")
    assert build_tree(tmp_path / "p") == "p/\n├── .gitignore\n├── a.py\n└── notes.txt"
    assert "gen/" in build_tree(tmp_path / "p", Filters(gitignore=False))
    assert "notes.txt" not in build_tree(tmp_path / "p", Filters(exts=(".txt",)))


def test_build_tree_folders_first_empty_folder_and_single_file(tmp_path):
    touch(tmp_path, "p/a.py")
    (tmp_path / "p/empty").mkdir()
    assert build_tree(tmp_path / "p") == "p/\n├── empty/\n└── a.py"
    assert build_tree(tmp_path / "p/a.py") == "a.py"


def test_cli_tree_prints_without_modifying_and_respects_flags(tmp_path, capsys):
    touch(tmp_path, "p/src/a.py")
    touch(tmp_path, "p/gen/b.py")
    touch(tmp_path, "p/c.js", "var a;\n")
    assert main([str(tmp_path / "p"), "--tree"]) == 0
    assert (
        capsys.readouterr().out
        == "p/\n├── gen/\n│   └── b.py\n├── src/\n│   └── a.py\n└── c.js\n"
    )
    main([str(tmp_path / "p"), "-t", "-d", "gen", "-e", "js"])
    assert capsys.readouterr().out == "p/\n└── src/\n    └── a.py\n"
    assert (tmp_path / "p/src/a.py").read_text() == "x = 1\n"


def test_copy_without_pyperclip_installed(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "pyperclip", None
    )  # makes `import pyperclip` raise ImportError
    with pytest.raises(RuntimeError, match="not installed"):
        copy_to_clipboard("x")


@pytest.mark.parametrize("flag", ["--remove", "--check"])
def test_tree_conflicts_with_remove_and_check(tmp_path, flag):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "--tree", flag])
    assert exc.value.code == 2
