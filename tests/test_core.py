# ramani: tests/test_core.py
import pytest

from ramani import mark_text, run, strip_text
from ramani.cli import main


def write(root, rel, content="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")
    return path


def statuses(results):
    return dict(results)


# --- text level ---------------------------------------------------------


def test_adds_comment_at_top():
    assert mark_text("x = 1\n", "a/b.py", "#") == ("# ramani: a/b.py\nx = 1\n", "added")


def test_unchanged_when_path_matches():
    text = "# ramani: a/b.py\nx = 1\n"
    assert mark_text(text, "a/b.py", "#") == (text, "unchanged")


def test_updates_when_path_changes():
    new, status = mark_text("# ramani: old/b.py\nx = 1\n", "new/b.py", "#")
    assert (new, status) == ("# ramani: new/b.py\nx = 1\n", "updated")


def test_shebang_stays_first():
    new, _ = mark_text("#!/usr/bin/env python\nprint()\n", "s.py", "#")
    assert new == "#!/usr/bin/env python\n# ramani: s.py\nprint()\n"
    assert mark_text(new, "s.py", "#")[1] == "unchanged"


def test_shebang_and_coding_stay_first():
    text = "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nprint()\n"
    new, _ = mark_text(text, "s.py", "#")
    assert new.splitlines()[:2] == text.splitlines()[:2]
    assert new.splitlines()[2] == "# ramani: s.py"


def test_shebang_only_file_without_newline():
    assert mark_text("#!/bin/sh", "s.sh", "#")[0] == "#!/bin/sh\n# ramani: s.sh\n"


def test_crlf_preserved():
    new, _ = mark_text("a = 1\r\nb = 2\r\n", "x.py", "#")
    assert new == "# ramani: x.py\r\na = 1\r\nb = 2\r\n"
    assert mark_text(new, "y.py", "#")[0] == "# ramani: y.py\r\na = 1\r\nb = 2\r\n"


def test_empty_file():
    assert mark_text("", "pkg/__init__.py", "#") == (
        "# ramani: pkg/__init__.py\n",
        "added",
    )


def test_no_trailing_newline():
    assert mark_text("x = 1", "a.py", "#")[0] == "# ramani: a.py\nx = 1"


def test_block_comment_style():
    new, status = mark_text("<p>hi</p>\n", "t/a.html", "<!--", "-->")
    assert (new, status) == ("<!-- ramani: t/a.html -->\n<p>hi</p>\n", "added")
    assert (
        mark_text(new, "u/a.html", "<!--", "-->")[0]
        == "<!-- ramani: u/a.html -->\n<p>hi</p>\n"
    )


def test_xml_declaration_stays_first():
    new, _ = mark_text('<?xml version="1.0"?>\n<a/>\n', "a.xml", "<!--", "-->")
    assert new == '<?xml version="1.0"?>\n<!-- ramani: a.xml -->\n<a/>\n'


def test_ordinary_comment_is_not_mistaken_for_marker():
    new, status = mark_text("# just a note\nx = 1\n", "a.py", "#")
    assert status == "added"
    assert new == "# ramani: a.py\n# just a note\nx = 1\n"


@pytest.mark.parametrize(
    "original",
    ["x = 1\n", "", "x = 1", "#!/bin/sh\necho hi\n", "a\r\nb\r\n", "# note\nx = 1\n"],
)
def test_strip_restores_original(original):
    marked, _ = mark_text(original, "a.py", "#")
    restored, removed = strip_text(marked, "#")
    assert removed is True
    assert restored.rstrip("\n") == original.rstrip("\n")


def test_strip_without_marker():
    assert strip_text("x = 1\n", "#") == ("x = 1\n", False)


# --- filesystem level ---------------------------------------------------


def test_adds_then_is_idempotent(tmp_path):
    write(tmp_path, "src/app.py")
    assert statuses(run(tmp_path)) == {"src/app.py": "added"}
    after_first = (tmp_path / "src/app.py").read_text()
    assert after_first == "# ramani: src/app.py\nx = 1\n"
    assert statuses(run(tmp_path)) == {"src/app.py": "unchanged"}
    assert (tmp_path / "src/app.py").read_text() == after_first


def test_detects_moved_file(tmp_path):
    write(tmp_path, "src/a.py")
    run(tmp_path)
    (tmp_path / "lib").mkdir()
    (tmp_path / "src/a.py").rename(tmp_path / "lib/a.py")
    assert statuses(run(tmp_path)) == {"lib/a.py": "updated"}
    assert (tmp_path / "lib/a.py").read_text() == "# ramani: lib/a.py\nx = 1\n"


def test_paths_are_relative_to_given_root(tmp_path):
    write(tmp_path, "proj/pkg/m.py")
    assert statuses(run(tmp_path / "proj")) == {"pkg/m.py": "added"}


def test_single_file_argument(tmp_path):
    write(tmp_path, "one.py")
    write(tmp_path, "two.py")
    assert statuses(run(tmp_path / "one.py")) == {"one.py": "added"}
    assert (tmp_path / "two.py").read_text() == "x = 1\n"


def test_default_ignores(tmp_path):
    write(tmp_path, "src/app.py")
    write(tmp_path, "src/__pycache__/app.cpython-313.pyc", "junk")
    write(tmp_path, "src/__pycache__/helper.py")
    write(tmp_path, "node_modules/lib/index.js", "var a;\n")
    write(tmp_path, ".git/hooks/pre-commit.py")
    write(tmp_path, "static/app.min.js", "var a;\n")
    assert statuses(run(tmp_path)) == {"src/app.py": "added"}


def test_extra_ignores(tmp_path):
    write(tmp_path, "a.py")
    write(tmp_path, "b.js", "var a;\n")
    write(tmp_path, "gen/c.py")
    results = run(tmp_path, ignore_dirs=("gen",), ignore_exts=(".js",))
    assert statuses(results) == {"a.py": "added"}


def test_unsupported_and_binary_files_are_skipped(tmp_path):
    write(tmp_path, "notes.txt", "hello\n")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (tmp_path / "bad.py").write_bytes(b"\xff\xfe\x00bad bytes")
    assert statuses(run(tmp_path)) == {
        "notes.txt": "unsupported",
        "logo.png": "unsupported",
        "bad.py": "skipped",
    }
    assert (tmp_path / "bad.py").read_bytes() == b"\xff\xfe\x00bad bytes"
    assert (tmp_path / "notes.txt").read_text() == "hello\n"


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("blob.py", b"MZ\x00\x01\x02data\n"),  # valid UTF-8, but NUL bytes mean binary
        ("tail.py", b"x = 1\n\x00"),
        ("page.md", b"---\ntitle: A\n---\n\x00\n"),
        ("shader.js", b"\x00\x00\x00\x00"),
    ],
)
def test_files_with_nul_bytes_are_never_modified(tmp_path, name, content):
    (tmp_path / name).write_bytes(content)
    assert statuses(run(tmp_path)) == {name: "skipped"}
    assert statuses(run(tmp_path, remove=True)) == {name: "skipped"}
    assert (tmp_path / name).read_bytes() == content


def test_gitignore_is_respected(tmp_path):
    write(tmp_path, ".gitignore", "secret/\n*.gen.py\n")
    write(tmp_path, "keep.py")
    write(tmp_path, "secret/s.py")
    write(tmp_path, "pkg/x.gen.py")
    results = statuses(run(tmp_path))
    assert results["keep.py"] == "added"
    assert "secret/s.py" not in results
    assert "pkg/x.gen.py" not in results


def test_no_gitignore_flag_processes_everything(tmp_path):
    write(tmp_path, ".gitignore", "secret/\n")
    write(tmp_path, "secret/s.py")
    results = statuses(run(tmp_path, use_gitignore=False))
    assert results["secret/s.py"] == "added"


def test_nested_gitignore_can_override_parent(tmp_path):
    write(tmp_path, ".gitignore", "gen_*.py\n")
    write(tmp_path, "sub/.gitignore", "!gen_keep.py\n")
    write(tmp_path, "gen_a.py")
    write(tmp_path, "sub/gen_keep.py")
    write(tmp_path, "sub/gen_b.py")
    results = statuses(run(tmp_path))
    assert "gen_a.py" not in results
    assert "sub/gen_b.py" not in results
    assert results["sub/gen_keep.py"] == "added"


def test_gitignore_only_applies_below_its_folder(tmp_path):
    write(tmp_path, "sub/.gitignore", "local.py\n")
    write(tmp_path, "sub/local.py")
    write(tmp_path, "local.py")
    results = statuses(run(tmp_path))
    assert "sub/local.py" not in results
    assert results["local.py"] == "added"


def test_gitignore_double_star_next_to_text_does_not_cross_folders(tmp_path):
    write(tmp_path, ".gitignore", "a/**b\n")
    write(tmp_path, "a/xb")  # matches a/*b: ignored
    write(tmp_path, "a/x/yb.py")  # git does not ignore this one
    write(tmp_path, "a/x/b.py")  # nor this one
    write(tmp_path, "a/sub/c.py")  # "sub" ends in b, so the whole folder is ignored
    results = statuses(run(tmp_path))
    assert results["a/x/yb.py"] == "added"
    assert results["a/x/b.py"] == "added"
    assert "a/xb" not in results
    assert "a/sub/c.py" not in results


def test_gitignore_double_star_between_slashes_crosses_folders(tmp_path):
    write(tmp_path, ".gitignore", "docs/**/*.tmp\n")
    write(tmp_path, "docs/a.tmp")
    write(tmp_path, "docs/x/y/b.tmp")
    write(tmp_path, "docs/x/keep.py")
    results = statuses(run(tmp_path))
    assert "docs/a.tmp" not in results
    assert "docs/x/y/b.tmp" not in results
    assert results["docs/x/keep.py"] == "added"


def test_bom_is_kept_at_start(tmp_path):
    (tmp_path / "b.py").write_bytes(b"\xef\xbb\xbfx = 1\n")
    run(tmp_path)
    assert (tmp_path / "b.py").read_bytes() == b"\xef\xbb\xbf# ramani: b.py\nx = 1\n"


def test_dockerfile_by_name(tmp_path):
    write(tmp_path, "Dockerfile", "# syntax=docker/dockerfile:1\nFROM python\n")
    run(tmp_path)
    assert (tmp_path / "Dockerfile").read_text() == (
        "# syntax=docker/dockerfile:1\n# ramani: Dockerfile\nFROM python\n"
    )


def test_dry_run_writes_nothing(tmp_path):
    write(tmp_path, "a.py")
    assert statuses(run(tmp_path, dry_run=True)) == {"a.py": "added"}
    assert (tmp_path / "a.py").read_text() == "x = 1\n"


def test_remove(tmp_path):
    write(tmp_path, "a.py")
    run(tmp_path)
    assert statuses(run(tmp_path, remove=True)) == {"a.py": "removed"}
    assert (tmp_path / "a.py").read_text() == "x = 1\n"
    assert statuses(run(tmp_path, remove=True)) == {"a.py": "unchanged"}


# --- CLI ----------------------------------------------------------------


def test_cli_adds_and_reports(tmp_path, capsys):
    write(tmp_path, "src/a.py")
    assert main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "added" in out and "src/a.py" in out
    assert (tmp_path / "src/a.py").read_text().startswith("# ramani: src/a.py\n")


def test_cli_check_exit_codes(tmp_path):
    write(tmp_path, "a.py")
    assert main([str(tmp_path), "--check"]) == 1
    assert (tmp_path / "a.py").read_text() == "x = 1\n"
    main([str(tmp_path)])
    assert main([str(tmp_path), "--check"]) == 0


def test_cli_ignore_flags(tmp_path):
    write(tmp_path, "a.py")
    write(tmp_path, "b.js", "var a;\n")
    write(tmp_path, "gen/c.py")
    main([str(tmp_path), "-e", "js", "-d", "gen"])
    assert (tmp_path / "a.py").read_text().startswith("# ramani:")
    assert (tmp_path / "b.js").read_text() == "var a;\n"
    assert (tmp_path / "gen/c.py").read_text() == "x = 1\n"


def test_cli_no_gitignore_flag(tmp_path):
    write(tmp_path, ".gitignore", "secret/\n")
    write(tmp_path, "secret/s.py")
    main([str(tmp_path)])
    assert (tmp_path / "secret/s.py").read_text() == "x = 1\n"
    main([str(tmp_path), "--no-gitignore"])
    assert (tmp_path / "secret/s.py").read_text().startswith("# ramani: secret/s.py")


def test_cli_missing_path(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "nope")])
    assert exc.value.code == 2


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_cli_version(flag, capsys):
    assert main([flag]) == 0
    assert capsys.readouterr().out.startswith("ramani ")


def test_cli_version_ignores_other_arguments(tmp_path, capsys):
    assert main(["--version", str(tmp_path / "missing")]) == 0
    assert capsys.readouterr().out.startswith("ramani ")


def test_importlib_metadata_is_not_imported_at_startup():
    import os
    import subprocess
    import sys
    from pathlib import Path

    import ramani

    env = {**os.environ, "PYTHONPATH": str(Path(ramani.__file__).parent.parent)}
    code = "import sys, ramani; sys.exit('importlib.metadata' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], env=env, check=False)
    assert result.returncode == 0


# --- markdown -----------------------------------------------------------


def test_markdown_uses_html_comment(tmp_path):
    write(tmp_path, "docs/guide.md", "# Title\n\ntext\n")
    run(tmp_path)
    assert (
        tmp_path / "docs/guide.md"
    ).read_text() == "<!-- ramani: docs/guide.md -->\n# Title\n\ntext\n"


def test_markdown_front_matter_stays_first(tmp_path):
    original = "---\ntitle: A\ntags: [x]\n---\n# Title\n"
    write(tmp_path, "post.md", original)
    run(tmp_path)
    marked = (tmp_path / "post.md").read_text()
    assert (
        marked == "---\ntitle: A\ntags: [x]\n---\n<!-- ramani: post.md -->\n# Title\n"
    )
    assert statuses(run(tmp_path)) == {"post.md": "unchanged"}
    run(tmp_path, remove=True)
    assert (tmp_path / "post.md").read_text() == original


def test_markdown_toml_front_matter(tmp_path):
    write(tmp_path, "post.md", '+++\ntitle = "A"\n+++\nbody\n')
    run(tmp_path)
    assert (
        tmp_path / "post.md"
    ).read_text() == '+++\ntitle = "A"\n+++\n<!-- ramani: post.md -->\nbody\n'


def test_markdown_unclosed_front_matter_is_not_treated_as_front_matter(tmp_path):
    write(tmp_path, "rule.md", "---\nnot front matter\n")
    run(tmp_path)
    assert (
        (tmp_path / "rule.md").read_text().startswith("<!-- ramani: rule.md -->\n---\n")
    )


def test_markdown_move_updates_comment(tmp_path):
    write(tmp_path, "a/doc.md", "---\ntitle: A\n---\nbody\n")
    run(tmp_path)
    (tmp_path / "b").mkdir()
    (tmp_path / "a/doc.md").rename(tmp_path / "b/doc.md")
    assert statuses(run(tmp_path)) == {"b/doc.md": "updated"}
    assert (
        tmp_path / "b/doc.md"
    ).read_text() == "---\ntitle: A\n---\n<!-- ramani: b/doc.md -->\nbody\n"


def test_mdx_uses_expression_comment(tmp_path):
    write(tmp_path, "page.mdx", "---\ntitle: A\n---\nimport X from 'x'\n")
    run(tmp_path)
    assert (tmp_path / "page.mdx").read_text() == (
        "---\ntitle: A\n---\n{/* ramani: page.mdx */}\nimport X from 'x'\n"
    )
    assert statuses(run(tmp_path)) == {"page.mdx": "unchanged"}


def test_yaml_file_with_document_marker_is_not_treated_as_front_matter(tmp_path):
    write(tmp_path, "a.yml", "---\nkey: 1\n---\nkey: 2\n")
    run(tmp_path)
    assert (tmp_path / "a.yml").read_text().startswith("# ramani: a.yml\n---\n")
