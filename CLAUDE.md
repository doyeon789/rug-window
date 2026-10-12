# CLAUDE.md

Rules Claude must follow when working in this repository.

## Language

- Code, comments, docstrings, commit messages, PR titles/descriptions: **English**.
- Conversation with the user and explainers (`docs/explainers/`): **Korean**.

## Workflow

The user must fully understand every piece of code that lands in this repo.
Optimize for the user's comprehension, not just for working code.

### Planning

Sessions start in plan mode (`.claude/settings.json`). Every plan must include:

- **Background knowledge**: concepts, libraries, or patterns the user needs to
  understand the change, explained before the steps.
- **Alternatives and rationale**: other approaches considered and why this one
  was chosen.
- **Uncertainties**: clearly separate verified facts from assumptions or
  guesses. Never present a guess as fact.

### Explainers

Each feature gets an explainer at `docs/explainers/<feature-name>.md`
(kebab-case, matching the branch description). Write explainers in **Korean**.

- **Create** it right after the plan is approved, from the plan and the
  discussion that led to it.
- **Update** it once the implementation works, so it matches the actual code
  (not the original plan). Note anything that changed from the plan and why.
- Contents:
  1. 개요: what the feature does and why it exists
  2. 배경 지식: concepts needed to understand the code
  3. 구조: key files, classes, and data flow
  4. 설계 결정: alternatives considered and why they were rejected
  5. 주의할 점: edge cases, known limitations, open questions
- Read existing explainers before modifying a feature.

### Live Examples

When a plan introduces a concept the user likely hasn't used before, offer to
build a live example. Do not build it unless the user agrees.

- Location: `examples/<concept-name>.py` (or `.html` if it is visual).
- Must run standalone (`python examples/<name>.py`) with no project setup.
- Keep it small and focused on one concept; link it from the explainer.

### Skills

When the user asks for the same kind of task a third time, suggest turning it
into a project skill under `.claude/skills/`. Only suggest; do not create it
without approval.

## Python Style

- Target Python 3.11+.
- Format and lint with **Ruff** (`ruff format`, `ruff check --fix`). Code must pass both before committing.
- Line length: 88.
- Add type hints to all function signatures (parameters and return values).
- Use Google-style docstrings for public modules, classes, and functions.
- Prefer `pathlib` over `os.path`, f-strings over `%`/`.format()`.
- Imports: standard library → third-party → local, one group per block (Ruff `I` rules handle ordering). No wildcard imports.
- Keep functions small and single-purpose. Avoid premature abstraction.
- Comments explain *why*, not *what*. Do not leave commented-out code.

## Naming

| Target | Convention | Example |
|---|---|---|
| Module / package / file | `snake_case` | `window_manager.py` |
| Function / method / variable | `snake_case` | `load_config()` |
| Class / exception | `PascalCase` | `RugWindow`, `ConfigError` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_RETRY` |
| Private member | leading `_` | `_cache` |
| Boolean | `is_` / `has_` / `can_` prefix | `is_visible` |
| Test file / function | `test_` prefix | `test_window_manager.py`, `test_load_config_missing_file()` |

- Use descriptive names; avoid unclear abbreviations (`cfg` → `config`, `btn` is fine for well-known ones).
- Exception classes end with `Error`.

## Testing

- Use `pytest`. Tests live in `tests/`, mirroring the source layout.
- Every behavior change needs tests, but **the user designs the test cases**.
  Thinking through inputs, outputs, edge cases, and corner cases is how the
  user learns the code, so do not take that away.
  1. Do not write or propose test cases first. Ask the user for their cases
     (inputs, expected outputs, edge/corner cases).
  2. After the user lists them, point out gaps as **questions**, not answers
     (e.g. "What should happen when the list is empty?").
  3. Once the cases are agreed, help turn them into `pytest` code.

## Git

### Branches

- `main` is always deployable. Do not commit directly to `main`.
- Work on a branch named `<type>/<short-description>` in kebab-case, then merge via PR.
  - e.g. `feat/window-resize`, `fix/config-loading`, `docs/readme-setup`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <subject>

<optional body: what and why>
```

- **type**: `feat`, `fix`, `refactor`, `docs`, `test`, `style`, `chore`, `perf`, `build`, `ci`
- **subject**: imperative mood, lowercase, no trailing period, ≤ 50 chars
  - ✅ `feat(window): add resize handler`
  - ❌ `Added resize handler.`
- Body wraps at 72 chars; explain *why* when it isn't obvious.
- Commit or push only when the user asks.

### Commit Granularity

Split commits into **units the user can review and understand in one sitting**.

- **Scaffolding first**: commit the skeleton (files, classes, function
  signatures with docstrings, stubs raising `NotImplementedError`) before any
  implementation. Then implement in follow-up commits, one coherent piece each.
- **Propose the split before committing**: show the planned commits (message +
  files + one-line summary each) and wait for approval.
  - Exception: when addressing PR review comments ("리뷰 반영해줘"), commit and
    push the fixes directly, then report the commits in the per-comment
    replies. The review comments already defined the scope.

### Pull Requests

- Title follows the same format as commit messages.
- Description includes: summary of changes, motivation, how it was tested, and
  a link to the related explainer.
- **Split PRs by what the user has understood**: a feature may span several
  PRs. Before opening a PR, ask which commits to include.
- **Never merge a PR.** The user merges after deciding they understand it.

### Review Iteration

The user reviews PRs on GitHub and leaves comments. When asked to address
review comments:

1. Read them with `gh` (e.g. `gh api repos/{owner}/{repo}/pulls/{n}/comments`).
2. For change requests, fix the code and reply per comment with what changed.
3. For questions, answer without changing code, and add the answer to the
   explainer if it fills a knowledge gap.
4. Update the explainer if the design changed.
