# ramani: src/ramani/config.py
"""Defaults: comment styles and ignore lists."""

MARKER = "ramani:"

_HASH = (
    ".py",
    ".pyi",
    ".sh",
    ".bash",
    ".zsh",
    ".rb",
    ".pl",
    ".r",
    ".jl",
    ".ex",
    ".exs",
    ".yml",
    ".yaml",
    ".toml",
    ".cfg",
    ".conf",
    ".tf",
    ".ps1",
    ".mk",
    ".nix",
    ".graphql",
)
_SLASH = (
    ".js",
    ".mjs",
    ".cjs",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".swift",
    ".dart",
    ".scss",
    ".less",
    ".proto",
    ".sol",
    ".zig",
)
_DASH = (".sql", ".lua", ".hs", ".elm")
_HTML = (".html", ".htm", ".xml", ".svg", ".vue", ".svelte", ".md", ".markdown")
_JINJA = (".j2", ".jinja", ".jinja2")

# extension -> (comment start, comment end); end is "" for line comments
COMMENT_STYLES: dict[str, tuple[str, str]] = {
    **dict.fromkeys(_HASH, ("#", "")),
    **dict.fromkeys(_SLASH, ("//", "")),
    **dict.fromkeys(_DASH, ("--", "")),
    **dict.fromkeys(_HTML, ("<!--", "-->")),
    **dict.fromkeys(_JINJA, ("{#", "#}")),
    ".css": ("/*", "*/"),
    ".tex": ("%", ""),
    ".mdx": ("{/*", "*/}"),  # MDX 2+ has no HTML comments
}

# Markdown files may open with a front matter block (--- ... --- or +++ ... +++) that must stay first
FRONT_MATTER_EXTS = (".md", ".markdown", ".mdx")

# files with no useful extension, matched by exact name
NAME_STYLES: dict[str, tuple[str, str]] = {
    "Dockerfile": ("#", ""),
    "Makefile": ("#", ""),
    ".gitignore": ("#", ""),
    ".dockerignore": ("#", ""),
    ".editorconfig": ("#", ""),
}

# first lines that must stay first (shebang, encoding, XML declaration, Dockerfile directives)
KEEP_FIRST = ("#!", "# -*-", "# coding", "<?xml", "# syntax=", "# escape=")

# folder names (globs allowed) and file endings skipped by default
IGNORE_DIRS = (
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".next",
    "*.egg-info",
    ".ramani",
)
IGNORE_EXTS = (".pyc", ".pyo", ".min.js", ".min.css", ".map", ".lock", ".log")
