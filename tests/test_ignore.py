# ramani: tests/test_ignore.py
from ramani.cli import main
from ramani.settings import (
    load_pyproject_ignore_dirs,
    load_pyproject_ignore_exts,
    norm_ext,
)


def test_norm_ext():
    assert norm_ext("MD") == ".md"
    assert norm_ext(" .Txt ") == ".txt"


def test_pyproject_ignore_exts(tmp_path):
    assert load_pyproject_ignore_exts(tmp_path) == ()
    file = tmp_path / "pyproject.toml"
    file.write_text('[tool.ramani]\nignore-ext = [".txt", "CSV"]\n')
    assert load_pyproject_ignore_exts(tmp_path) == (".txt", ".csv")
    file.write_text('[tool.ramani]\nignore-ext = "js"\n')
    assert load_pyproject_ignore_exts(tmp_path) == (".js",)
    file.write_text("[project]\nname = 'x'\n")
    assert load_pyproject_ignore_exts(tmp_path) == ()


def test_cli_uses_pyproject_ignore_ext_for_marking_and_tree(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text('[tool.ramani]\nignore-ext = [".js"]\n')
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.js").write_text("var a;\n")
    main([str(tmp_path / "a.py"), "-t"])
    main([str(tmp_path), "-t"])
    assert "b.js" not in capsys.readouterr().out
    main([str(tmp_path)])
    assert (tmp_path / "a.py").read_text().startswith("# ramani:")
    assert (tmp_path / "b.js").read_text() == "var a;\n"


def test_cli_flag_adds_to_pyproject_ignore_ext(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.ramani]\nignore-ext = [".js"]\n')
    for name in ("a.py", "b.js", "c.go"):
        (tmp_path / name).write_text("x\n")
    main([str(tmp_path), "-e", "go"])
    assert (tmp_path / "a.py").read_text().startswith("# ramani:")
    assert (tmp_path / "b.js").read_text() == "x\n"
    assert (tmp_path / "c.go").read_text() == "x\n"


def test_pyproject_ignore_dirs(tmp_path):
    assert load_pyproject_ignore_dirs(tmp_path) == ()
    file = tmp_path / "pyproject.toml"
    file.write_text('[tool.ramani]\nignore-dir = ["gen", "out*"]\n')
    assert load_pyproject_ignore_dirs(tmp_path) == ("gen", "out*")
    file.write_text('[tool.ramani]\nignore-dir = "gen"\n')
    assert load_pyproject_ignore_dirs(tmp_path) == ("gen",)


def test_cli_uses_pyproject_ignore_dir_for_marking_and_tree(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text('[tool.ramani]\nignore-dir = ["gen*"]\n')
    for rel in ("a.py", "gen/b.py", "gen_x/c.py", "src/d.py"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n")
    main([str(tmp_path), "-t"])
    out = capsys.readouterr().out
    assert "gen" not in out and "src/" in out
    main([str(tmp_path), "-d", "src"])
    assert (tmp_path / "a.py").read_text().startswith("# ramani:")
    for rel in ("gen/b.py", "gen_x/c.py", "src/d.py"):
        assert (tmp_path / rel).read_text() == "x = 1\n"
