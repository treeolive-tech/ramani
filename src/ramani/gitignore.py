# ramani: src/ramani/gitignore.py
"""Minimal .gitignore parsing and matching."""

import re

# (compiled regex, negated, dir_only)
type Rule = tuple["re.Pattern[str]", bool, bool]


def _glob_to_regex(pattern: str) -> str:
    """Translate a gitignore glob into a regex body.

    Examples::

        _glob_to_regex("*.py")  # "[^/]*\\.py"
        _glob_to_regex("a/**/b")  # "a/(?:.*/)?b"
        _glob_to_regex("a/**b")  # "a/[^/]*b"  (** needs a slash or end on both sides)
        _glob_to_regex("a**/b")  # "a(?:.*/)?b"  (git: first wildcard of a slashed pattern)
    """
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            stars = len(pattern[i:]) - len(pattern[i:].lstrip("*"))
            after = pattern[i + stars : i + stars + 1]
            # git quirk: besides after "/" or at the start, a ** that is the first wildcard
            # of a pattern containing "/" is special too (so `a**/b` matches `a/x/b` and `ab`)
            first_wildcard = "/" in pattern and not any(
                ch in "*?[\\" for ch in pattern[:i]
            )
            if (
                stars >= 2
                and after in ("", "/")
                and (i == 0 or pattern[i - 1] == "/" or first_wildcard)
            ):
                out.append("(?:.*/)?" if after else ".*")
                i += stars + len(after)
                continue
            out.append("[^/]*")
            i += stars
            continue
        elif c == "?":
            out.append("[^/]")
        elif c == "[" and (j := pattern.find("]", i + 2)) != -1:
            body = pattern[i + 1 : j].replace("\\", "\\\\")
            out.append("[" + ("^" + body[1:] if body.startswith("!") else body) + "]")
            i = j
        elif c == "\\" and i + 1 < n:
            i += 1
            out.append(re.escape(pattern[i]))
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


def parse_gitignore(text: str) -> list[Rule]:
    """Parse .gitignore text into rules.

    Examples::

        len(parse_gitignore("*.log"))  # 1
        parse_gitignore("# note")  # []
    """
    rules: list[Rule] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        dir_only = line.endswith("/")
        line = line.rstrip("/")
        if not line:
            continue
        anchored = "/" in line
        line = line.lstrip("/")
        prefix = "" if anchored else "(?:.*/)?"
        rules.append(
            (re.compile(f"^{prefix}{_glob_to_regex(line)}$"), negated, dir_only)
        )
    return rules


def match_rules(rel: str, is_dir: bool, rules: list[Rule]) -> bool | None:
    """Last matching rule wins: True = ignored, False = re-included, None = no match.

    Examples::

        match_rules("a.log", False, parse_gitignore("*.log"))  # True
        match_rules("a.log", False, parse_gitignore("*.log\n!a.log"))  # False
    """
    verdict = None
    for regex, negated, dir_only in rules:
        if (is_dir or not dir_only) and regex.match(rel):
            verdict = not negated
    return verdict


def is_gitignored(rel: str, is_dir: bool, stack: list[tuple[str, list[Rule]]]) -> bool:
    """Check ``rel`` against nested .gitignore rules, outermost first so inner files win.

    Each stack entry is (folder relative to the root, its rules); "" is the root.

    Examples::

        is_gitignored("a.log", False, [("", parse_gitignore("*.log"))])  # True
        is_gitignored("sub/a.log", False, [("sub", parse_gitignore("!a.log"))])  # False
    """
    verdict = False
    for base, rules in stack:
        local = rel[len(base) + 1 :] if base else rel
        result = match_rules(local, is_dir, rules)
        if result is not None:
            verdict = result
    return verdict
