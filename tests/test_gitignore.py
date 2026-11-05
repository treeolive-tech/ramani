# ramani: tests/test_gitignore.py
import pytest

from ramani.gitignore import match_rules, parse_gitignore


@pytest.mark.parametrize(
    ("patterns", "rel", "is_dir", "expected"),
    [
        ("*.log", "a.log", False, True),
        ("*.log", "deep/er/a.log", False, True),
        ("*.log", "a.txt", False, None),
        ("*.log\n!keep.log", "keep.log", False, False),
        ("build/", "build", True, True),
        ("build/", "build", False, None),
        ("build/", "src/build", True, True),
        ("/top.txt", "top.txt", False, True),
        ("/top.txt", "sub/top.txt", False, None),
        ("docs/*.md", "docs/a.md", False, True),
        ("docs/*.md", "docs/x/a.md", False, None),
        ("docs/**/*.tmp", "docs/a.tmp", False, True),
        ("docs/**/*.tmp", "docs/x/y/a.tmp", False, True),
        ("docs/**/*.tmp", "other/a.tmp", False, None),
        ("**/cache", "a/b/cache", True, True),
        ("logs/**", "logs/x/y.txt", False, True),
        ("file?.txt", "file1.txt", False, True),
        ("file[0-9].txt", "file7.txt", False, True),
        ("file[!0-9].txt", "file7.txt", False, None),
        ("# comment\n\n*.tmp", "a.tmp", False, True),
        (r"\#hash", "#hash", False, True),
    ],
)
def test_match_rules(patterns, rel, is_dir, expected):
    assert match_rules(rel, is_dir, parse_gitignore(patterns)) is expected


# Expected values below were checked against `git check-ignore` (git 2.43).
@pytest.mark.parametrize(
    ("pattern", "rel", "expected"),
    [
        # ** next to other text is a plain *, so it can't cross a slash
        ("a/**b", "a/xb", True),
        ("a/**b", "a/b", True),
        ("a/**b", "a/x/b", None),
        ("a/**b", "a/x/yb", None),
        ("src/**.py", "src/m.py", True),
        ("src/**.py", "src/p/m.py", None),
        ("**foo", "x/foo", True),
        ("foo**", "foobar", True),
        # ** between slashes, or at either end, is special
        ("a/**/b", "a/b", True),
        ("a/**/b", "a/x/y/b", True),
        ("**/b", "q/b", True),
        ("a/**", "a/x/y", True),
        ("a/**", "a", None),
        ("a/b/**", "a/b/c/d", True),
        ("**", "x/y/z", True),
        # three or more asterisks count as **, like git
        ("a/***/b", "a/b", True),
        ("a/***/b", "a/x/y/b", True),
        # git also treats the first ** of a pattern with a slash as special
        ("a**/b", "a/x/b", True),
        ("a**/b", "ax/b", True),
        ("a**/b", "ab", True),
        ("a/b**", "a/bx/y", True),
    ],
)
def test_double_star_follows_git(pattern, rel, expected):
    assert match_rules(rel, False, parse_gitignore(pattern)) is expected
