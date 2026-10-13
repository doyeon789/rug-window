# Contributing to Rug Window

Thanks for your interest! Bug reports, ideas, and pull requests are all
welcome. This is a small hobby project, so please be patient with replies.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
To report a security problem, see [SECURITY.md](SECURITY.md) instead of
opening a public issue.

## Reporting bugs and ideas

- Search [existing issues](https://github.com/pizza-playground/rug-window/issues)
  first.
- Use the issue templates. For bugs, include your Windows version, display
  scaling (e.g. 150%), GPU, and the relevant part of the log at
  `%LOCALAPPDATA%\rug-window\rug-window.log`.
- For larger changes, open an issue to discuss the idea before writing code.

## Development setup

Requirements: Windows 10/11, a GPU with OpenGL 3.3, and
[uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/pizza-playground/rug-window.git
cd rug-window
uv sync
uv run python -m rug_window   # run from source (quit from the tray icon)
```

Useful tools:

| Command | What it does |
|---|---|
| `uv run python tools/cloth_preview.py` | Preview the cloth simulation without the desktop window |
| `uv run python tools/make_shortcut.py` | Create a desktop shortcut to the dev build |
| `uv run python tools/build_release.py` | Build the release zip into `dist/` (close the running rug first) |

If PySide6 fails to load its DLLs after `uv sync`, reinstall it:
`uv sync --reinstall-package pyside6-essentials --reinstall-package shiboken6`.

## Before you open a pull request

All of these must pass:

```
uv run ruff format
uv run ruff check --fix
uv run pytest
uv run --with mypy --with types-pywin32 --with scipy-stubs mypy src
```

Code style:

- Python 3.11+, line length 88, formatted and linted with Ruff.
- Type hints on every function signature; Google-style docstrings on public
  modules, classes, and functions.
- Comments explain *why*, not *what*. No commented-out code.
- Add or update tests in `tests/` (mirroring `src/`) for behaviour changes.
  Pure functions (geometry, physics helpers) are the easiest to test.
- Write code, comments, docs, and commit messages in English.

## Branches, commits, and pull requests

- Branch from `main` as `<type>/<short-description>`, e.g. `fix/icon-bumps`.
- Commit messages follow
  [Conventional Commits](https://www.conventionalcommits.org/):
  `<type>(<optional scope>): <subject>`, with a lowercase, imperative subject
  of 50 characters or fewer and no trailing period. Types: `feat`, `fix`,
  `refactor`, `docs`, `test`, `style`, `chore`, `perf`, `build`, `ci`.
- Keep commits small enough to review in one sitting.
- In the pull request description, say what changed, why, and how you tested
  it (including what you checked on screen, since much of the app is visual).
- For new features or design changes, update or add an explainer in
  `docs/explainers/` (overview, background, structure, design decisions,
  caveats).

## Assets and licensing

Contributions are released under the [MIT License](LICENSE). Only add images
or other assets that are CC0 or otherwise compatible with redistribution, and
record their source and license in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
