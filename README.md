# orchestrate-ralph

A skills package for running a Ralph loop inside a Claude Code interface.
It runs as an orchestrator reading from the project's issues list
and dispatching workers as sub-agents in isolated git worktrees. This allows
more flexible loop mechanics and avoids using `claude --print`. 

Included are both a traditional serial ralph loop, `/orchestrate-ralph`, and
an opt-in `/orchestrate-ralph-parallel` skill that runs multiple workers simultaneously
and merges the results. If your tasks are spread across multiple areas of code
and have good `Blocked-by` markers parallel execution can save a lot of wall time.
However if you have frequent
conflicts from parallel tasks it can burn lots of tokens and actually be slower
than the serial loop.

Projects must be set up with `/setup-ralph` before use. The source of issues
read by ralph is described in markdown files in the repo and is designed to be
initialized with [`/setup-matt-pocock-skills`](https://github.com/mattpocock/skills)

## Contents

Four skills:

- `/setup-ralph` — per-repo configuration. A fresh run autodetects the
  project's verification gate, gathers the orchestrator's config, and writes
  `docs/agents/ralph.md` and `.ralph/settings.json`. A later run can repair an
  existing config from a complaint (eg. `/setup-ralph workers need permission for new test command`).
- `/orchestrate-ralph` — run the loop. Reads `ORCHESTRATOR.md`, becomes the orchestrator, and runs until
  the queue is drained. Carries `PROMPT.md` (the worker doctrine).
- `/orchestrate-ralph-parallel` — parallel-wave mode. Dispatches
  multiple workers per round and merges the results, dropping branches
  that conflict.
- `/cleanup-ralph` — cleanup script that removes abandoned worktrees
  that can result from interrupted ralph runs. Will prompt before doing any
  deletions.

## Prerequisites

Ralph reads its issue queue through the issue-tracker configuration that
[`setup-matt-pocock-skills`](https://github.com/mattpocock/skills) writes —
`docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`. Run that
skill first, then `setup-ralph`.

Ralph is **tracker-agnostic** — local-markdown, GitHub, and GitLab are
supported out of the box; any other tracker is described during `setup-ralph`.
Parallel-wave mode (the `/orchestrate-ralph-parallel` skill) is only safe on
a tracker that exposes a readable dependency relation; the single worker
`/orchestrate-ralph` only needs issues to be sorted in an order that satisfies
dependencies.

## Install

Copy or symlink the four skill directories into your skills directory
(`~/.claude/skills/` or `<project>/.claude/skills`):

```
~/.claude/skills/setup-ralph                 →  setup-ralph/
~/.claude/skills/orchestrate-ralph           →  orchestrate-ralph/
~/.claude/skills/orchestrate-ralph-parallel  →  orchestrate-ralph-parallel/
~/.claude/skills/cleanup-ralph               →  cleanup-ralph/
```
