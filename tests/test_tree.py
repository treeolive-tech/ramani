# ramani: tests/test_tree.py
import sys
import types

import pytest

from ramani.cli import main
from ramani.tree import build_tree, copy_to_clipboard


def touch(root, rel, content="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def fake_pyperclip(monkeypatch, *, fail=False):
    """Install a stand-in pyperclip module and return the list of copied strings."""
    copied: list[str] = []
    module = types.ModuleType("pyperclip")

    class PyperclipException(RuntimeError):
        pass

    def copy(text):
        if fail:
            raise PyperclipException("no copy/paste mechanism")
        copied.append(text)

    module.__dict__.update({"PyperclipException": PyperclipException, "copy": copy})
    monkeypatch.setitem(sys.modules, "pyperclip", module)
    return copied


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
    assert "gen/" in build_tree(tmp_path / "p", use_gitignore=False)
    assert "notes.txt" not in build_tree(tmp_path / "p", ignore_exts=(".txt",))


def test_build_tree_folders_first_and_empty_folder(tmp_path):
    touch(tmp_path, "p/a.py")
    (tmp_path / "p/empty").mkdir()
    assert build_tree(tmp_path / "p") == "p/\n├── empty/\n└── a.py"


def test_build_tree_single_file(tmp_path):
    touch(tmp_path, "a.py")
    assert build_tree(tmp_path / "a.py") == "a.py"


def test_cli_tree_prints_and_does_not_modify(tmp_path, capsys):
    touch(tmp_path, "p/src/a.py")
    assert main([str(tmp_path / "p"), "--tree"]) == 0
    assert capsys.readouterr().out == "p/\n└── src/\n    └── a.py\n"
    assert (tmp_path / "p/src/a.py").read_text() == "x = 1\n"


def test_cli_tree_respects_ignore_flags(tmp_path, capsys):
    touch(tmp_path, "p/a.py")
    touch(tmp_path, "p/gen/b.py")
    touch(tmp_path, "p/c.js", "var a;\n")
    main([str(tmp_path / "p"), "-t", "-d", "gen", "-e", "js"])
    assert capsys.readouterr().out == "p/\n└── a.py\n"


def test_cli_copy_copies_tree_and_implies_tree(tmp_path, monkeypatch, capsys):
    copied = fake_pyperclip(monkeypatch)
    touch(tmp_path, "p/a.py")
    assert main([str(tmp_path / "p"), "--copy"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "p/\n└── a.py\n"
    assert copied == ["p/\n└── a.py"]
    assert "copied to clipboard" in captured.err
    assert (tmp_path / "p/a.py").read_text() == "x = 1\n"


def test_cli_tree_without_copy_does_not_touch_clipboard(tmp_path, monkeypatch):
    copied = fake_pyperclip(monkeypatch)
    touch(tmp_path, "a.py")
    main([str(tmp_path), "--tree"])
    assert copied == []


def test_cli_copy_failure_still_prints_tree(tmp_path, monkeypatch, capsys):
    fake_pyperclip(monkeypatch, fail=True)
    touch(tmp_path, "p/a.py")
    assert main([str(tmp_path / "p"), "--copy"]) == 1
    captured = capsys.readouterr()
    assert "a.py" in captured.out
    assert "could not copy to clipboard: no clipboard available" in captured.err


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
