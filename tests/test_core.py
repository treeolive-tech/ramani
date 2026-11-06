# ramani: tests/test_core.py
import pytest

from ramani import mark_text, run, strip_text
from ramani.cli import main
from ramani.core import Filters


def write(root, rel, content="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")
    return path


def statuses(results):
    return dict(results)


def py_files(results):
    return {rel for rel, _ in results if rel.endswith(".py")}


# --- text level ---------------------------------------------------------

HTML = ("<!--", "-->")

MARK_CASES = {
    "add": ("x = 1\n", "a/b.py", "#", "", "# ramani: a/b.py\nx = 1\n", "added"),
    "unchanged": ("# ramani: a.py\nx\n", "a.py", "#", "", "# ramani: a.py\nx\n", "unchanged"),
    "update": ("# ramani: old.py\nx\n", "new.py", "#", "", "# ramani: new.py\nx\n", "updated"),
    "shebang": ("#!/bin/sh\necho\n", "s.sh", "#", "", "#!/bin/sh\n# ramani: s.sh\necho\n", "added"),
    "shebang_coding": (
        "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nprint()\n", "s.py", "#", "",
        "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n# ramani: s.py\nprint()\n", "added",
    ),
    "shebang_only": ("#!/bin/sh", "s.sh", "#", "", "#!/bin/sh\n# ramani: s.sh\n", "added"),
    "crlf": ("a = 1\r\n", "x.py", "#", "", "# ramani: x.py\r\na = 1\r\n", "added"),
    "crlf_update": ("# ramani: o.py\r\na\r\n", "x.py", "#", "", "# ramani: x.py\r\na\r\n", "updated"),
    "empty": ("", "pkg/__init__.py", "#", "", "# ramani: pkg/__init__.py\n", "added"),
    "no_trailing_newline": ("x = 1", "a.py", "#", "", "# ramani: a.py\nx = 1", "added"),
    "block_comment": ("<p>hi</p>\n", "a.html", *HTML, "<!-- ramani: a.html -->\n<p>hi</p>\n", "added"),
    "block_update": ("<!-- ramani: o.html -->\n<p/>\n", "a.html", *HTML, "<!-- ramani: a.html -->\n<p/>\n", "updated"),
    "xml_declaration": (
        '<?xml version="1.0"?>\n<a/>\n', "a.xml", *HTML,
        '<?xml version="1.0"?>\n<!-- ramani: a.xml -->\n<a/>\n', "added",
    ),
    "other_comment": ("# note\nx\n", "a.py", "#", "", "# ramani: a.py\n# note\nx\n", "added"),
}  # fmt: skip


@pytest.mark.parametrize("case", MARK_CASES.values(), ids=MARK_CASES)
def test_mark_text(case):
    text, rel, start, end, expected, status = case
    assert mark_text(text, rel, start, end) == (expected, status)


@pytest.mark.parametrize(
    "original",
    ["x = 1\n", "", "x = 1", "#!/bin/sh\necho hi\n", "a\r\nb\r\n", "# note\nx = 1\n"],
)
def test_strip_restores_original(original):
    marked, _ = mark_text(original, "a.py", "#")
    restored, removed = strip_text(marked, "#")
    assert removed is True
    assert restored.rstrip("\n") == original.rstrip("\n")
    assert strip_text(original, "#") == (original, False)


def test_long_headers_fall_back_to_the_whole_file():
    front = "---\n" + "tag: x\n" * 3000 + "---\nbody\n"  # front matter longer than HEAD
    marked, _ = mark_text(front, "p.md", "<!--", "-->", front_matter=True)
    assert marked.endswith("---\n<!-- ramani: p.md -->\nbody\n")
    assert strip_text(marked, "<!--", "-->", front_matter=True) == (front, True)
    late_crlf = "x = 1\n" * 3000 + "y = 2\r\n"  # CRLF only after the first 8 KB
    assert mark_text(late_crlf, "a.py", "#")[0].startswith("# ramani: a.py\nx = 1\n")


# --- filesystem level ---------------------------------------------------


def test_add_is_idempotent_and_follows_moves(tmp_path):
    write(tmp_path, "src/a.py")
    assert statuses(run(tmp_path)) == {"src/a.py": "added"}
    assert (tmp_path / "src/a.py").read_text() == "# ramani: src/a.py\nx = 1\n"
    assert statuses(run(tmp_path)) == {"src/a.py": "unchanged"}
    (tmp_path / "lib").mkdir()
    (tmp_path / "src/a.py").rename(tmp_path / "lib/a.py")
    assert statuses(run(tmp_path)) == {"lib/a.py": "updated"}
    assert (tmp_path / "lib/a.py").read_text() == "# ramani: lib/a.py\nx = 1\n"


def test_paths_are_relative_to_the_given_root_or_file(tmp_path):
    write(tmp_path, "proj/pkg/m.py")
    write(tmp_path, "proj/other.py")
    assert statuses(run(tmp_path / "proj/pkg/m.py")) == {"m.py": "added"}
    assert statuses(run(tmp_path / "proj")) == {
        "other.py": "added",
        "pkg/m.py": "updated",
    }


def test_dry_run_writes_nothing_and_remove_undoes(tmp_path):
    write(tmp_path, "a.py")
    assert statuses(run(tmp_path, dry_run=True)) == {"a.py": "added"}
    assert (tmp_path / "a.py").read_text() == "x = 1\n"
    run(tmp_path)
    assert statuses(run(tmp_path, remove=True)) == {"a.py": "removed"}
    assert (tmp_path / "a.py").read_text() == "x = 1\n"
    assert statuses(run(tmp_path, remove=True)) == {"a.py": "unchanged"}


def test_default_and_extra_ignores(tmp_path):
    write(tmp_path, "src/app.py")
    write(tmp_path, "src/__pycache__/helper.py")
    write(tmp_path, "node_modules/lib/index.js", "var a;\n")
    write(tmp_path, "static/app.min.js", "var a;\n")
    write(tmp_path, "b.js", "var a;\n")
    write(tmp_path, "gen/c.py")
    assert statuses(run(tmp_path, dry_run=True)) == {
        "b.js": "added",
        "gen/c.py": "added",
        "src/app.py": "added",
    }
    results = run(
        tmp_path,
        dry_run=True,
        filters=Filters(dirs=("gen", "__pycache__"), exts=(".js",)),
    )
    assert statuses(results) == {"src/app.py": "added"}


def test_unsupported_unreadable_and_binary_files_are_left_alone(tmp_path):
    files = {
        "notes.txt": (b"hello\n", "unsupported"),
        "logo.png": (b"\x89PNG\r\n\x1a\n\x00", "unsupported"),
        "bad.py": (b"\xff\xfe\x00bad bytes", "skipped"),
        "blob.py": (b"MZ\x00\x01\x02data\n", "skipped"),  # valid UTF-8 but has NULs
        "tail.py": (b"x = 1\n\x00", "skipped"),
        "page.md": (b"---\ntitle: A\n---\n\x00\n", "skipped"),
    }
    for name, (content, _) in files.items():
        (tmp_path / name).write_bytes(content)
    expected = {name: status for name, (_, status) in files.items()}
    assert statuses(run(tmp_path)) == expected
    assert statuses(run(tmp_path, remove=True)) == expected
    for name, (content, _) in files.items():
        assert (tmp_path / name).read_bytes() == content


def test_gitignore_rules_nesting_and_opt_out(tmp_path):
    write(tmp_path, ".gitignore", "secret/\n*.gen.py\ngen_*.py\n")
    write(tmp_path, "sub/.gitignore", "!gen_keep.py\nlocal.py\n")
    for rel in ["keep.py", "secret/s.py", "x.gen.py", "gen_a.py", "local.py"]:
        write(tmp_path, rel)
    for rel in ["sub/gen_keep.py", "sub/gen_b.py", "sub/local.py"]:
        write(tmp_path, rel)
    assert py_files(run(tmp_path, dry_run=True)) == {
        "keep.py", "local.py", "sub/gen_keep.py",
    }  # fmt: skip
    everything = statuses(run(tmp_path, dry_run=True, filters=Filters(gitignore=False)))
    assert "secret/s.py" in everything and "sub/local.py" in everything


def test_gitignore_double_star_matches_git(tmp_path):
    write(tmp_path, ".gitignore", "a/**b\ndocs/**/*.tmp\n")
    for rel in ["a/xb", "a/x/yb.py", "a/x/b.py", "a/sub/c.py"]:
        write(tmp_path, rel)
    for rel in ["docs/a.tmp", "docs/x/y/b.tmp", "docs/x/keep.py"]:
        write(tmp_path, rel)
    # a/xb and a/sub/ end in "b", so ** acts as *; docs/**/ crosses folders
    assert py_files(run(tmp_path, dry_run=True)) == {
        "a/x/yb.py", "a/x/b.py", "docs/x/keep.py",
    }  # fmt: skip


def test_first_line_directives_stay_first(tmp_path):
    (tmp_path / "b.py").write_bytes(b"\xef\xbb\xbfx = 1\n")
    write(tmp_path, "Dockerfile", "# syntax=docker/dockerfile:1\nFROM python\n")
    run(tmp_path)
    assert (tmp_path / "b.py").read_bytes() == b"\xef\xbb\xbf# ramani: b.py\nx = 1\n"
    assert (tmp_path / "Dockerfile").read_text() == (
        "# syntax=docker/dockerfile:1\n# ramani: Dockerfile\nFROM python\n"
    )


MARKDOWN_CASES = {
    "plain": ("a.md", "# T\n", "<!-- ramani: a.md -->\n# T\n"),
    "yaml_front_matter": ("a.md", "---\ntitle: A\n---\nbody\n", "---\ntitle: A\n---\n<!-- ramani: a.md -->\nbody\n"),
    "toml_front_matter": ("a.md", "+++\nt = 1\n+++\nbody\n", "+++\nt = 1\n+++\n<!-- ramani: a.md -->\nbody\n"),
    "unclosed_front_matter": ("a.md", "---\nnot front matter\n", "<!-- ramani: a.md -->\n---\nnot front matter\n"),
    "mdx": ("a.mdx", "---\nt: 1\n---\nimport X\n", "---\nt: 1\n---\n{/* ramani: a.mdx */}\nimport X\n"),
    "yaml_file_is_not_markdown": ("a.yml", "---\nk: 1\n---\nk: 2\n", "# ramani: a.yml\n---\nk: 1\n---\nk: 2\n"),
}  # fmt: skip


@pytest.mark.parametrize("case", MARKDOWN_CASES.values(), ids=MARKDOWN_CASES)
def test_markdown_comments_and_front_matter(tmp_path, case):
    name, original, expected = case
    write(tmp_path, name, original)
    run(tmp_path)
    assert (tmp_path / name).read_text() == expected
    assert statuses(run(tmp_path)) == {name: "unchanged"}
    run(tmp_path, remove=True)
    assert (tmp_path / name).read_text() == original


# --- CLI ----------------------------------------------------------------


def test_cli_reports_and_check_exit_codes(tmp_path, capsys):
    write(tmp_path, "src/a.py")
    assert main([str(tmp_path), "--check"]) == 1
    assert (tmp_path / "src/a.py").read_text() == "x = 1\n"
    assert main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "added" in out and "src/a.py" in out and "\x1b" not in out
    assert main([str(tmp_path), "--check"]) == 0


def test_cli_ignore_flags(tmp_path):
    write(tmp_path, ".gitignore", "secret/\n")
    write(tmp_path, "a.py")
    write(tmp_path, "b.js", "var a;\n")
    write(tmp_path, "gen/c.py")
    write(tmp_path, "secret/s.py")
    main([str(tmp_path), "-e", "js", "-d", "gen"])
    assert (tmp_path / "a.py").read_text().startswith("# ramani:")
    for rel in ["b.js", "gen/c.py", "secret/s.py"]:
        assert not (tmp_path / rel).read_text().startswith(("# ramani", "//"))
    main([str(tmp_path), "--no-gitignore"])
    assert (tmp_path / "secret/s.py").read_text().startswith("# ramani: secret/s.py")


def test_cli_missing_path(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "nope")])
    assert exc.value.code == 2


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_cli_version(flag, capsys):
    assert main([flag, "missing-path"]) == 0
    assert capsys.readouterr().out.startswith("ramani ")


def test_importlib_metadata_is_not_imported_at_startup():
    import os
    import subprocess
    import sys
    from pathlib import Path

    import ramani

    env = {**os.environ, "PYTHONPATH": str(Path(ramani.__file__).parent.parent)}
    code = "import sys, ramani; sys.exit('importlib.metadata' in sys.modules)"
    assert (
        subprocess.run([sys.executable, "-c", code], env=env, check=False).returncode
        == 0
    )
