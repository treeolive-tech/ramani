# ramani: tests/test_settings.py
from pathlib import Path

import pytest

from ramani.cli import main
from ramani.core import style_for
from ramani.settings import load_pyproject_styles, parse_style


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (".abc=//", (".abc", ("//", ""))),
        ("abc=//", (".abc", ("//", ""))),
        (".ABC=//", (".abc", ("//", ""))),
        (".tpl=<!--,-->", (".tpl", ("<!--", "-->"))),
        (".tpl=<!-- , --> ", (".tpl", ("<!--", "-->"))),
        ("Jenkinsfile=//", ("Jenkinsfile", ("//", ""))),
    ],
)
def test_parse_style(spec, expected):
    assert parse_style(spec) == expected


@pytest.mark.parametrize("spec", ["", "abc", ".abc=", "=//"])
def test_parse_style_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        parse_style(spec)


def test_extra_style_beats_builtin_and_matches_file_names():
    assert style_for(Path("a.py"), {".py": ("//", "")}) == ("//", "")
    assert style_for(Path("a.py")) == ("#", "")
    assert style_for(Path("Jenkinsfile"), {"Jenkinsfile": ("//", "")}) == ("//", "")


def test_pyproject_styles(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ramani.comments]\n".abc" = "//"\ntpl = ["<!--", "-->"]\n'
    )
    assert load_pyproject_styles(tmp_path) == {
        ".abc": ("//", ""),
        ".tpl": ("<!--", "-->"),
    }


def test_pyproject_without_section_or_file(tmp_path):
    assert load_pyproject_styles(tmp_path) == {}
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert load_pyproject_styles(tmp_path) == {}
    (tmp_path / "pyproject.toml").write_text("not [ valid toml")
    assert load_pyproject_styles(tmp_path) == {}


def test_cli_reports_unsupported_types(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")
    main([str(tmp_path)])
    assert "no comment style" not in capsys.readouterr().out
    (tmp_path / "b.xyz").write_text("data\n")
    (tmp_path / "c.xyz").write_text("data\n")
    (tmp_path / "runner").write_text("data\n")
    main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "3 unsupported" in out
    assert "no comment style for: .xyz x2, runner x1" in out
    assert "-c EXT=START" in out
    assert (tmp_path / "b.xyz").read_text() == "data\n"


def test_cli_comment_flag_and_pyproject(tmp_path, capsys):
    (tmp_path / "b.xyz").write_text("data\n")
    (tmp_path / "t.tpl").write_text("<p/>\n")
    main([str(tmp_path), "-c", ".xyz=//", "-c", ".tpl=<!--,-->"])
    assert (tmp_path / "b.xyz").read_text() == "// ramani: b.xyz\ndata\n"
    assert (tmp_path / "t.tpl").read_text() == "<!-- ramani: t.tpl -->\n<p/>\n"
    assert "no comment style" not in capsys.readouterr().out
    (tmp_path / "pyproject.toml").write_text('[tool.ramani.comments]\n".abc" = "%"\n')
    (tmp_path / "d.abc").write_text("data\n")
    (tmp_path / "e.abc").write_text("data\n")
    main([str(tmp_path / "d.abc")])  # style from pyproject.toml
    main([str(tmp_path / "e.abc"), "-c", ".abc=#"])  # the flag wins
    assert (tmp_path / "d.abc").read_text() == "% ramani: d.abc\ndata\n"
    assert (tmp_path / "e.abc").read_text() == "# ramani: e.abc\ndata\n"


def test_cli_bad_comment_spec(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "-c", "nonsense"])
    assert exc.value.code == 2
