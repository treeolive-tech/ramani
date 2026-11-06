<!-- ramani: README.md -->
<h1 align="center">ramani</h1>

<p align="center">
  <strong>Every file knows where it lives.</strong><br>
  A line at the top of each file says where it sits in your project, and it follows the file when it moves.
</p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python 3.13+" src="https://img.shields.io/badge/python-3.13%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="https://docs.astral.sh/uv/"><img alt="Built with uv" src="https://img.shields.io/badge/built%20with-uv-DE5FE9"></a>
  <img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue">
  <img alt="ramani means map in Swahili" src="https://img.shields.io/badge/ramani-Swahili%20for%20%22map%22-006600">
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#folder-tree">Folder tree</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#supported-files">Supported files</a>
</p>

> **ramani** _(ra-MA-ni)_ is Swahili for **"map"**. That is the whole idea: ramani draws a map of your project _inside_ the project. Each file carries one comment with its own path, kept correct as files are renamed and moved, and the same tool can print the entire project as a tree.

```python
# ramani: src/shop/billing/pay.py
def pay(): ...
```

## Why

Files travel without their address. They get pasted into chats, issues, code reviews and AI prompts, and the question "which file is this, again?" comes up every time. With ramani the path is part of the file, so it travels with it.

## Features

- 🧭 **Move-aware.** Rename or move a file, run ramani again, and its comment follows. Nothing is duplicated.
- 🪶 **Careful placement.** The comment goes after shebangs, encoding lines, XML declarations and Markdown front matter, and never turns a docstring into a plain string.
- 🗂️ **Knows 60+ file types.** Python, JavaScript, Go, Rust, SQL, HTML, CSS, Markdown, Dockerfile and more, each with the right comment syntax. Add your own in one line.
- 🙈 **Respects your ignores.** Built-in lists for `__pycache__`, `node_modules` and friends, every `.gitignore` it finds (nested ones too), and flags for the rest.
- 🌳 **Prints a folder tree.** One flag draws your project as a tree, another copies it to the clipboard.
- 🔍 **CI-friendly.** `--check` exits with code 1 when any comment is missing or stale. `--dry-run` writes nothing.
- 🧹 **Reversible.** `--remove` strips every comment ramani added.

## Install

```bash
uv tool install ramani      # install the command globally (recommended)
uvx ramani --dry-run        # or run it once without installing anything
pipx install ramani         # pipx or plain pip work too: pip install ramani
```

Prefer to pin it to a single project, for CI or pre-commit? Add it as a dev dependency and run it through `uv run`:

```bash
uv add --dev ramani
uv run ramani --check
```

Then, inside a project:

```bash
ramani --dry-run            # see what would change
ramani                      # do it
```

## Usage

Point it at a folder (default: the current one) or a single file. Paths in the comments are relative to that folder.

```console
$ ramani
added     docs/setup.md
added     src/shop/cart.py
added     src/shop/index.html
added     src/shop/pay.py
added     README.md
5 added, 1 unsupported
no comment style for: .json x1
  add one with -c EXT=START[,END] or [tool.ramani.comments] in pyproject.toml
```

The comment uses each language's own syntax, and sits where it can't break anything:

```python
# ramani: src/shop/cart.py
"""Cart logic."""

import json
```

```html
<!-- ramani: src/shop/index.html -->
<h1>Hi</h1>
```

```text
---
title: Setup
---
<!-- ramani: docs/setup.md -->
# Setup
```

### When a file moves

Move `pay.py` into a new `billing/` folder and run ramani again. It recognises its own comment, sees the path is out of date, and rewrites it. Untouched files stay untouched.

```console
$ mkdir src/shop/billing && mv src/shop/pay.py src/shop/billing/
$ ramani
updated   src/shop/billing/pay.py
4 unchanged, 1 unsupported, 1 updated
```

```python
# ramani: src/shop/billing/pay.py
def pay(): ...
```

Add `ramani --check` to CI or a pre-commit hook to catch stale comments before they land. It changes nothing and exits with 1 if anything needs updating.

## Folder tree

`--tree` prints your project as a tree and writes nothing. It uses the same ignore rules as marking, so you see exactly the files ramani works on. Folders come first.

```console
$ ramani --tree
shop/
├── docs/
│   └── setup.md
├── src/
│   └── shop/
│       ├── billing/
│       │   └── pay.py
│       ├── cart.py
│       └── index.html
├── README.md
└── data.json
```

Add `--copy` to also put the tree on your clipboard, ready to paste into a chat, an issue or a doc.

```bash
ramani --copy               # print the tree and copy it
ramani ./src -t -d tests    # tree of ./src, leaving out tests
```

> On Linux, the clipboard needs `xclip`, `xsel` or `wl-clipboard` installed. If none is available the tree is still printed, with a note on stderr and exit code 1.

## Options

| Option                          | What it does                                                        |
| ------------------------------- | ------------------------------------------------------------------- |
| `PATH`                          | Folder or file to process (default: current folder)                 |
| `-e, --ignore-ext EXT`          | Also skip this extension, e.g. `-e .txt` (repeatable)               |
| `-d, --ignore-dir NAME`         | Also skip this folder name or glob, e.g. `-d "build*"` (repeatable) |
| `-c, --comment EXT=START[,END]` | Comment style for an extension or file name (repeatable)            |
| `--no-gitignore`                | Ignore `.gitignore` files                                           |
| `-n, --dry-run`                 | Show what would change, write nothing                               |
| `--check`                       | Dry run that exits 1 if anything is missing or stale                |
| `--remove`                      | Strip ramani comments instead of adding them                        |
| `-t, --tree`                    | Print the folder tree instead of marking files                      |
| `--copy`                        | Copy the tree to the clipboard (implies `--tree`)                   |
| `-V, --version`                 | Print the installed version and exit                                |
| `-v, --verbose`                 | Also list unchanged files                                           |

## Configuration

Teach ramani a file type on the command line:

```bash
ramani -c .abc=//                 # line comment
ramani -c ".tpl=<!--,-->"         # block comment: start,end
ramani -c Jenkinsfile=//          # by exact file name
```

or once and for all in your `pyproject.toml`:

```toml
[tool.ramani.comments]
".abc" = "//"
".tpl" = ["<!--", "-->"]
```

Flags beat `pyproject.toml`, which beats the built-in styles, so you can override those too.

## Supported files

| Comment    | Looks like                  | Files                                                                                                                                    |
| ---------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `#`        | `# ramani: a/b.py`          | `.py` `.pyi` `.sh` `.rb` `.pl` `.r` `.jl` `.ex` `.yml` `.yaml` `.toml` `.cfg` `.tf` `.ps1` `.nix` `Dockerfile` `Makefile` `.gitignore` … |
| `//`       | `// ramani: a/b.ts`         | `.js` `.mjs` `.jsx` `.ts` `.tsx` `.java` `.kt` `.scala` `.c` `.h` `.cpp` `.cs` `.go` `.rs` `.swift` `.dart` `.scss` `.proto` …           |
| `--`       | `-- ramani: a/b.sql`        | `.sql` `.lua` `.hs` `.elm`                                                                                                               |
| `<!-- -->` | `<!-- ramani: a/b.html -->` | `.html` `.htm` `.xml` `.svg` `.vue` `.svelte` `.md` `.markdown`                                                                          |
| `/* */`    | `/* ramani: a/b.css */`     | `.css`                                                                                                                                   |
| `{# #}`    | `{# ramani: a/b.j2 #}`      | `.j2` `.jinja` `.jinja2`                                                                                                                 |
| `{/* */}`  | `{/* ramani: a/b.mdx */}`   | `.mdx`                                                                                                                                   |
| `%`        | `% ramani: a/b.tex`         | `.tex`                                                                                                                                   |

Formats with no comment syntax, such as `.json` and `.csv`, are left alone and listed at the end of each run so nothing is skipped silently. The full table lives in `src/ramani/config.py`.

## How it works

1. Skip anything that must stay first: a shebang, an encoding line, an XML declaration, a `# syntax=` line, or front matter in Markdown.
2. Look at the next line. If it is a ramani comment with the **same** path, do nothing.
3. If it is a ramani comment with a **different** path, the file has moved. Rewrite that one line.
4. If it is not a ramani comment, insert one.

Line endings (LF or CRLF) and UTF-8 byte-order marks are preserved. Symlinks, files that are not UTF-8, and binary files (anything containing a NUL byte) are never touched.

## Development

```bash
uv sync
uv run poe test
```

Ramani has two small runtime dependencies: [`termcolor`](https://pypi.org/project/termcolor/) for coloured output and [`pyperclip`](https://pypi.org/project/pyperclip/) for `--copy`. Colour appears only in a terminal; pipes, files and the clipboard get plain text, and `NO_COLOR=1` turns it off.

## License

MIT © Treeolive Tech Ltd. Use it, change it, ship it; just keep the copyright notice.
