# ramani: tests/test_env.py
from ramani.cli import main
from ramani.settings import env_flag, env_int, env_list


def make(root, count=3):
    for i in range(count):
        (root / f"f{i}.py").write_text("x = 1\n")


def test_env_helpers(monkeypatch):
    monkeypatch.setenv("RAMANI_IGNORE_EXT", " .txt, csv ,,")
    assert env_list("RAMANI_IGNORE_EXT") == [".txt", "csv"]
    assert env_list("RAMANI_MISSING") == []
    monkeypatch.setenv("RAMANI_NO_GITIGNORE", "YES")
    assert env_flag("RAMANI_NO_GITIGNORE") is True
    assert env_flag("RAMANI_MISSING") is False
    monkeypatch.setenv("RAMANI_MAX_FILES", "abc")
    assert env_int("RAMANI_MAX_FILES", 7) == 7
    monkeypatch.setenv("RAMANI_MAX_FILES", "5")
    assert env_int("RAMANI_MAX_FILES", 7) == 5


def test_env_ignores_for_marking_and_tree(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RAMANI_IGNORE_EXT", "js")
    monkeypatch.setenv("RAMANI_IGNORE_DIR", "gen*")
    for rel in ("a.py", "b.js", "gen/c.py"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n")
    main([str(tmp_path), "-t"])
    out = capsys.readouterr().out
    assert "a.py" in out and "b.js" not in out and "gen" not in out
    main([str(tmp_path)])
    assert (tmp_path / "a.py").read_text().startswith("# ramani:")
    assert (tmp_path / "b.js").read_text() == "x = 1\n"
    assert (tmp_path / "gen/c.py").read_text() == "x = 1\n"


def test_env_no_gitignore(tmp_path, monkeypatch):
    (tmp_path / ".gitignore").write_text("secret/\n")
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret/s.py").write_text("x = 1\n")
    monkeypatch.setenv("RAMANI_NO_GITIGNORE", "1")
    main([str(tmp_path)])
    assert (tmp_path / "secret/s.py").read_text().startswith("# ramani:")


def test_env_max_files_and_flag_wins(tmp_path, monkeypatch):
    make(tmp_path)
    monkeypatch.setenv("RAMANI_MAX_FILES", "2")
    assert main([str(tmp_path)]) == 1  # no terminal: aborts
    assert main([str(tmp_path), "--max-files", "3"]) == 0  # flag beats env
