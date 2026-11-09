# ramani: tests/test_output.py
from pathlib import Path

import pytest

from ramani.cli import main
from ramani.core import Filters
from ramani.formats import FORMATS, format_for, render
from ramani.workspace import BLOCK, END, START, ensure_dir, merge_block


def touch(root, rel, content="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def proj(tmp_path):
    touch(tmp_path, "proj/src/app.py")
    touch(tmp_path, "proj/README.md", "hi\n")
    return tmp_path / "proj"


# --- .ramani folder and its managed .gitignore block -----------------------


def test_merge_block_adds_keeps_and_is_idempotent():
    assert merge_block("") == BLOCK
    once = merge_block("keep.svg")
    assert once == "keep.svg\n" + BLOCK
    assert merge_block(once) == once


def test_merge_block_replaces_only_its_own_part():
    stale = f"top\n{START}\n!keep\n{END}\nbottom\n"
    assert merge_block(stale) == f"top\n{BLOCK}bottom\n"


def test_merge_block_with_damaged_markers_appends_a_fresh_block():
    damaged = f"top\n{START}\n"
    merged = merge_block(damaged)
    assert merged.startswith("top\n") and merged.endswith(BLOCK)


def test_ensure_dir_creates_once_and_keeps_user_lines(tmp_path):
    folder = ensure_dir(tmp_path)
    assert folder == tmp_path / ".ramani"
    gitignore = folder / ".gitignore"
    assert gitignore.read_text() == BLOCK
    gitignore.write_text("keep.svg\n" + BLOCK)
    assert ensure_dir(tmp_path) == folder
    assert gitignore.read_text() == "keep.svg\n" + BLOCK


def test_ensure_dir_reports_problems_readably(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(RuntimeError, match="can't prepare"):
        ensure_dir(blocker)


def test_the_folder_appears_only_for_a_bare_output(proj, monkeypatch):
    monkeypatch.setattr("ramani.cli.copy_to_clipboard", lambda text: None)
    for argv in (
        [str(proj)],
        [str(proj), "-t"],
        [str(proj), "-f", "json"],
        [str(proj), "--copy"],
        [str(proj), "-o", str(proj / "out.md")],
    ):
        assert main(argv) == 0
    assert not (proj / ".ramani").exists()
    assert main([str(proj), "-o"]) == 0
    assert (proj / ".ramani").is_dir()


def test_the_folder_is_never_listed_or_marked(proj):
    assert main([str(proj), "--no-gitignore", "-o"]) == 0
    touch(proj, ".ramani/notes.py")
    for fmt in FORMATS:
        assert ".ramani" not in render(proj, fmt, Filters(gitignore=False))
    main([str(proj), "--no-gitignore"])
    assert (proj / ".ramani/notes.py").read_text() == "x = 1\n"
    assert ".ramani" not in (proj / ".ramani/map.txt").read_text()


# --- -o with no file: .ramani/map.<ext> ------------------------------------


def test_bare_output_saves_a_snapshot_quietly(proj, capsys):
    assert main([str(proj), "-o"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "saved to" in captured.err
    assert (proj / ".ramani/map.txt").read_text() == render(proj, "tree") + "\n"
    assert (proj / ".ramani/.gitignore").read_text() == BLOCK


@pytest.mark.parametrize(
    ("fmt", "name"),
    [
        ("tree", "map.txt"),
        ("paths", "map.txt"),
        ("markdown", "map.md"),
        ("json", "map.json"),
        ("mermaid", "map.mmd"),
    ],
)
def test_bare_output_extension_follows_the_format(proj, fmt, name):
    assert main([str(proj), "-o", "-f", fmt]) == 0
    assert (proj / ".ramani" / name).read_text() == render(proj, fmt) + "\n"


def test_bare_output_for_a_single_file_uses_its_folder(proj):
    assert main([str(proj / "README.md"), "-o"]) == 0
    assert (proj / ".ramani/map.txt").read_text() == "README.md\n"


def test_snapshot_overwrites_the_previous_one(proj):
    main([str(proj), "-o"])
    touch(proj, "extra.py")
    main([str(proj), "-o"])
    assert "extra.py" in (proj / ".ramani/map.txt").read_text()


# --- -o FILE ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("m.txt", "tree"),
        ("m.md", "markdown"),
        ("m.MARKDOWN", "markdown"),
        ("m.json", "json"),
        ("m.mmd", "mermaid"),
    ],
)
def test_output_format_comes_from_the_extension(proj, tmp_path, name, fmt):
    out = tmp_path / name
    assert main([str(proj), "-o", str(out)]) == 0
    assert out.read_text() == render(proj, fmt) + "\n"


def test_format_flag_beats_the_extension(proj, tmp_path):
    out = tmp_path / "m.txt"
    assert main([str(proj), "-o", str(out), "-f", "json"]) == 0
    assert out.read_text() == render(proj, "json") + "\n"


def test_unknown_extension_is_an_error_unless_f_settles_it(proj, tmp_path):
    out = tmp_path / "m.xyz"
    with pytest.raises(SystemExit) as exc:
        main([str(proj), "-o", str(out)])
    assert exc.value.code == 2 and not out.exists()
    assert main([str(proj), "-o", str(out), "-f", "paths"]) == 0
    assert out.read_text() == render(proj, "paths") + "\n"


def test_output_pointing_at_a_folder_is_an_error(proj, capsys):
    with pytest.raises(SystemExit) as exc:
        main([str(proj), "-o", str(proj / "src")])
    assert exc.value.code == 2
    assert "before -o" in capsys.readouterr().err


def test_output_creates_missing_folders(proj, tmp_path):
    out = tmp_path / "a/b/map.md"
    assert main([str(proj), "-o", str(out)]) == 0
    assert out.is_file()


def test_output_that_cannot_be_written_exits_1(proj, tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert main([str(proj), "-o", str(blocker / "m.md")]) == 1
    assert "could not save" in capsys.readouterr().err


def test_output_file_inside_the_project_does_not_list_itself(proj):
    out = proj / "map.md"
    out.write_text("old\n")
    assert "map.md" in render(proj, "paths")
    assert main([str(proj), "-o", str(out)]) == 0
    assert "map.md" not in out.read_text()


def test_output_and_copy_work_together(proj, tmp_path, monkeypatch):
    copied = []
    monkeypatch.setattr("ramani.cli.copy_to_clipboard", copied.append)
    out = tmp_path / "m.json"
    assert main([str(proj), "-o", str(out), "--copy"]) == 0
    assert copied == [render(proj, "json")]
    assert out.read_text() == copied[0] + "\n"


@pytest.mark.parametrize("flag", ["--remove", "--check"])
def test_output_conflicts_with_remove_and_check(tmp_path, flag):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "-o", flag])
    assert exc.value.code == 2


def test_format_for():
    assert format_for(Path("A.JSON")) == "json"
    assert format_for(Path("A.xyz")) is None
