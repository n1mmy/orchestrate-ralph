# orchestrate-ralph

A skills package for running a **Ralph loop** as an interactive orchestrator —
an agent that grinds a project's issue tracker to done by dispatching worker
sub-agents in isolated git worktrees.

"Ralph" is the term of art for the brute-force agent loop: pick a
ready-for-agent issue, hand it to a fresh agent, repeat. This package ships
the *interactive orchestrator* flavour — one canonical single-worker skill
plus an opt-in parallel-wave skill, both with isolated worktrees, smart
retries, and merge-and-gate integration — and nothing else. There is
deliberately no headless driver (see [ADR 0001](docs/adr/0001-tracker-agnostic-prose-adapter.md)).

## What's in here

Four skills:

- **`setup-ralph/`** — per-repo configuration. A fresh run autodetects the
  project's verification gate, gathers the orchestrator's config, and writes
  `docs/agents/ralph.md` and `.ralph/settings.json`. A later run *repairs* an
  existing config from a complaint ("workers keep prompting for permissions")
  instead of re-scaffolding.
- **`orchestrate-ralph/`** — the canonical loop. Dispatches **one worker per
  round**. Reads `ORCHESTRATOR.md`, becomes the orchestrator, and runs until
  the queue is drained. Carries `PROMPT.md` (worker doctrine).
- **`orchestrate-ralph-parallel/`** — opt-in parallel-wave mode. Dispatches
  multiple workers per round; requires the repo to declare itself
  `parallel-safe: true` in `docs/agents/ralph.md` (a *capability declaration*
  that the tracker exposes a readable dependency relation). Shares
  `PROMPT.md` with the canonical skill via a symlink. See
  [ADR 0007](docs/adr/0007-single-worker-default-two-skill-split.md) for
  why the canonical mode is single-worker.
- **`cleanup-ralph/`** — interactive reaper for the
  `.claude/worktrees/*` auto-isolation pile that builds up across
  crashed runs, `/quit`-mid-wave, and `EnterWorktree` sessions the user
  never explicitly removed. Skips worktrees held by other live claude
  sessions; uses `git branch -d` (not `-D`) so unmerged integration
  branches survive as "kept" entries the user decides about manually.

## Prerequisites

Ralph reads its issue queue through the issue-tracker configuration that
[`setup-matt-pocock-skills`](https://github.com/mattpocock) writes —
`docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`,
`docs/agents/domain.md`. Run that skill first, then `setup-ralph`.

Ralph is **tracker-agnostic** — local-markdown, GitHub, and GitLab are
supported out of the box; any other tracker is described during `setup-ralph`.
Parallel-wave mode (the `/orchestrate-ralph-parallel` skill) is only safe on
a tracker that exposes a readable dependency relation; the canonical
`/orchestrate-ralph` skill ignores that requirement and dispatches one
worker per round.

## Install

Copy or symlink the four skill directories into your skills directory
(`~/.claude/skills/` or `~/.agents/skills/`):

```
~/.claude/skills/setup-ralph                 →  setup-ralph/
~/.claude/skills/orchestrate-ralph           →  orchestrate-ralph/
~/.claude/skills/orchestrate-ralph-parallel  →  orchestrate-ralph-parallel/
~/.claude/skills/cleanup-ralph               →  cleanup-ralph/
```

`orchestrate-ralph-parallel/PROMPT.md` is a relative symlink to
`../orchestrate-ralph/PROMPT.md`; installers may preserve the symlink or
flatten it into two physical copies and either works (doctrine is
N-invariant).

## Layout

```
orchestrate-ralph/
├── README.md
├── docs/adr/
│   ├── 0001-tracker-agnostic-prose-adapter.md
│   ├── 0002-worker-worktree-escapes.md
│   ├── 0003-setup-ralph-repair-mode.md
│   ├── 0004-orchestrator-under-enforcement.md
│   ├── 0005-descriptive-doctrine-after-the-matcher-catalog.md
│   ├── 0006-orchestrator-owns-merge-and-transition.md
│   └── 0007-single-worker-default-two-skill-split.md
├── setup-ralph/
│   ├── SKILL.md
│   ├── repair-symptoms.md
│   └── templates/
│       ├── settings.template.json
│       ├── hook-path-guard.py
│       ├── ralph.md
│       ├── issue-tracker-local.md
│       ├── issue-tracker-github.md
│       └── issue-tracker-gitlab.md
├── orchestrate-ralph/
│   ├── SKILL.md
│   ├── ORCHESTRATOR.md
│   └── PROMPT.md
├── orchestrate-ralph-parallel/
│   ├── SKILL.md
│   ├── ORCHESTRATOR.md
│   └── PROMPT.md  → ../orchestrate-ralph/PROMPT.md
└── cleanup-ralph/
    └── SKILL.md
```
