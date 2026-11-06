# ramani: tests/test_color.py
import sys

from ramani.cli import main
from ramani.color import paint, paint_count, paint_err, paint_path, paint_status


def tag(text, color=None, *attrs):
    return f"<{color or '-'}{''.join('+' + a for a in attrs)}>{text}</>"


def test_paint_path_dims_folders_and_bolds_the_name():
    assert paint_path("src/a.py", tag) == "<white+dark>src/</><-+bold>a.py</>"
    assert paint_path("a.py", tag) == "<-+bold>a.py</>"


def test_paint_count_and_status_use_the_status_colour():
    assert paint_count(5, "added", tag) == "<green>5 added</>"
    assert paint_count(2, "unsupported", tag) == "<magenta>2 unsupported</>"
    assert paint_count(1, "mystery", tag) == "<->1 mystery</>"
    assert paint_status("updated", tag) == "<yellow>updated  </>"


def test_paint_force_colours_even_when_piped():
    assert paint("x", "green", force=True) == "\x1b[32mx\x1b[0m"


def test_paint_err_follows_stderr_not_stdout(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    assert paint_err("oops", "red") == "oops"
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    assert paint_err("oops", "red") == "\x1b[31moops\x1b[0m"


def test_cli_check_verdict(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")
    assert main([str(tmp_path), "--check"]) == 1
    assert "1 file(s) need changes" in capsys.readouterr().out
    main([str(tmp_path)])
    capsys.readouterr()
    assert main([str(tmp_path), "--check"]) == 0
    assert "all path comments are up to date" in capsys.readouterr().out
