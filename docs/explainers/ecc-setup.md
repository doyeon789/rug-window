# ECC Setup

> Status: **done** (as of ECC v2.2.3)
>
> Note: `.claude/` is no longer tracked in git. It holds the maintainer's
> local AI-assisted workflow, so the files described here exist only on the
> maintainer's machine. This document is kept as a record of that setup.

## 1. Overview

[ECC](https://github.com/affaan-m/ECC) is a third-party plugin bundle that adds skills, agents, and hooks to Claude Code in one go.
This document records how ECC was set up for this repository and why.

Reference: [gymcoding — ECC install and usage guide](https://www.gymcoding.co/articles/ecc-claude-code-install-usage-guide) (Korean)

Three things were done:

1. Enabled the plugin: added `"ecc@ecc": true` to `enabledPlugins` in `.claude/settings.json`.
2. Copied only the ECC rule files that fit this project into `.claude/rules/ecc/`.
3. Turned off the GateGuard hook. This lives in the personal settings file (`.claude/settings.local.json`) and is not committed.

## 2. Background

### The four parts of a plugin

| Part | What it does | Analogy |
|---|---|---|
| Skill | A task guide you call when needed, like `/ecc:plan` | A recipe in a drawer |
| Agent | A sub-Claude with a specific role (e.g. `ecc:python-reviewer`) | An expert you call in |
| Hook | A script that runs **automatically** before or after a tool is used | A porch motion light: it turns on as you walk by |
| Rules | Guidance documents Claude reads every session | Class rules on the classroom wall |

### Rules are not installed automatically

Installing the plugin does not deploy its `rules/` folder, so the rules must be copied by hand.
The originals are already in the plugin cache, so no `git clone` was needed.

```
~/.claude/plugins/cache/ecc/ecc/2.2.3/rules/
```

### Hook profiles and how to turn hooks off

ECC hooks come in strength profiles. There are three ways to turn them off.

- **Change the profile**: set the environment variable `ECC_HOOK_PROFILE` to `minimal`, `standard` (default), or `strict`.
- **Turn off single hooks**: list hook IDs, comma-separated, in `ECC_DISABLED_HOOKS`.
- **Turn off GateGuard only**: `ECC_GATEGUARD=off`. This is a dedicated switch; `scripts/hooks/gateguard-fact-force.js` was confirmed to read it.

## 3. Structure

```
.claude/
├── settings.json           # enabledPlugins: ecc@ecc
├── settings.local.json     # env.ECC_GATEGUARD=off   (personal)
└── rules/ecc/
    ├── common/   code-review, coding-style, git-workflow, hooks,
    │             patterns, performance, security
    └── python/   coding-style, hooks, patterns, security
```

## 4. Design decisions

### Rule files left out

| File | Why it was left out |
|---|---|
| `common/testing.md` | Enforces "Claude writes tests first (TDD) + 80% coverage". Conflicts with the CLAUDE.md rule "the user designs the test cases". |
| `common/development-workflow.md` | The same TDD enforcement, plus extra documents such as a PRD. |
| `common/agents.md` | Tells Claude to run agents without asking the user. Does not fit this project's understanding-first flow. |
| `python/testing.md` | Extends `common/testing.md`. |
| `python/fastapi.md` | Not relevant to this project. |

### Why in the project instead of globally

The reference article suggests `~/.claude/rules/ecc/` (global). Here they were put inside the project.

- They do not affect other projects.
- At the time they were in git, so the chosen rules could be reviewed and reverted.

### Why only GateGuard was turned off

GateGuard blocks the first command or file edit in each session with "write down your checks first".
Plan mode and the CLAUDE.md rules already play a similar checking role, so it only added a duplicate step.
The other hooks, such as the dangerous-command check, stay on the `standard` profile.

## 5. Caveats

### Small remaining conflicts: CLAUDE.md wins

The copied files were kept exactly as the originals, unmodified, so these sentences remain:

- `common/code-review.md`: its checklist includes "80% coverage".
- `python/coding-style.md`, `python/hooks.md`: mention black and mypy. This project uses Ruff.

### Other notes

- `code-review.md` and `git-workflow.md` link to files that were left out (`testing.md`, `agents.md`, `development-workflow.md`). Those links are broken.
- The copies do not follow plugin updates. Copy again after an update if needed.
- Some hooks, such as the observation hooks, write session records under `~/.claude/`. These stay local.
- **Unverified**: whether the project's `.claude/rules/` loads exactly like the global `~/.claude/rules/`. To be checked in a new session.
