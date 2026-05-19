# orchestrate-ralph

A skills package for running a **Ralph loop** as an interactive orchestrator —
an agent that grinds a project's issue tracker to done by dispatching worker
sub-agents in parallel waves.

"Ralph" is the term of art for the brute-force agent loop: pick a
ready-for-agent issue, hand it to a fresh agent, repeat. This package ships the
*interactive orchestrator* flavour — parallel worker waves in isolated git
worktrees, smart retries, and merge-and-gate integration — and nothing else.
There is deliberately no headless driver (see [ADR 0001](docs/adr/0001-tracker-agnostic-prose-adapter.md)).

## What's in here

Two skills:

- **`setup-ralph/`** — one-time, per-repo scaffolding. Autodetects the
  project's verification gate, gathers the orchestrator's config, and writes
  `docs/agents/ralph.md` and `.ralph/settings.json`. Run it once per repo.
- **`orchestrate-ralph/`** — runs the loop. Reads `ORCHESTRATOR.md`, becomes
  the orchestrator, and dispatches workers until the queue is drained. Also
  carries `PROMPT.md` (worker doctrine) and `watch-steps.py` (a terminal step
  viewer for a run).

## Prerequisites

Ralph reads its issue queue through the issue-tracker configuration that
[`setup-matt-pocock-skills`](https://github.com/mattpocock) writes —
`docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`,
`docs/agents/domain.md`. Run that skill first, then `setup-ralph`.

Ralph is **tracker-agnostic** — local-markdown, GitHub, and GitLab are
supported out of the box; any other tracker is described during `setup-ralph`.
Its parallel waves are only safe on a tracker that exposes a readable
dependency relation; without one, the orchestrator runs serially. See ADR 0001.

## Install

Copy or symlink the two skill directories into your skills directory
(`~/.claude/skills/` or `~/.agents/skills/`):

```
~/.claude/skills/setup-ralph        →  setup-ralph/
~/.claude/skills/orchestrate-ralph  →  orchestrate-ralph/
```

## Layout

```
orchestrate-ralph/
├── README.md
├── docs/adr/
│   ├── 0001-tracker-agnostic-prose-adapter.md
│   └── 0002-worker-worktree-escapes.md
├── setup-ralph/
│   ├── SKILL.md
│   └── templates/
│       ├── settings.template.json
│       ├── ralph.md
│       ├── issue-tracker-local.md
│       ├── issue-tracker-github.md
│       └── issue-tracker-gitlab.md
└── orchestrate-ralph/
    ├── SKILL.md
    ├── ORCHESTRATOR.md
    ├── PROMPT.md
    └── watch-steps.py
```
