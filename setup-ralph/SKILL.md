---
name: setup-ralph
description: Scaffold the per-repo configuration the Ralph orchestrator needs — autodetect the verification gate, gather loop config, and write docs/agents/ralph.md plus .ralph/settings.json. Run once per repo before the first orchestrate-ralph run.
disable-model-invocation: true
---

# Setup Ralph

One-time, per-repo scaffolding for the `orchestrate-ralph` skill. This is
prompt-driven, not a deterministic script: explore, present what you found,
confirm with the user, then write.

## Prerequisite

Ralph reads its issue queue through the issue-tracker configuration that
`setup-matt-pocock-skills` writes. Check that `docs/agents/issue-tracker.md`
and `docs/agents/triage-labels.md` exist. If they do not, tell the user to run
`setup-matt-pocock-skills` first, and stop — do not guess the tracker.

## Process

### 1. Explore

Read the repo; don't assume.

- **The gate** — the project's verification commands. Look at `package.json`
  `scripts` (`typecheck`, `lint`, `test`, `build`), `Makefile` targets,
  `Cargo.toml`, `pyproject.toml` / `tox.ini`, and any CI workflow files.
  Assemble a candidate ordered list, cheap checks first.
- **The integration base branch** — `git symbolic-ref refs/remotes/origin/HEAD`,
  or the current default branch.
- **Env bootstrap** — is there a committed env template (`.env.example`,
  `.env.sample`, a `.env.*` checked into git) that a fresh worktree must
  materialise before the gate will pass?
- **The tracker** — read `docs/agents/issue-tracker.md`. Is it local-markdown,
  GitHub, GitLab, or something else? Does it expose a dependency relation
  between issues?

### 2. Present and confirm

Walk the user through these one at a time — present, get an answer, move on:

- **Gate** — show the autodetected command list; let the user correct it.
  Order matters: a change must pass each command in turn.
- **Integration base branch** — confirm.
- **Env bootstrap** — confirm the step in one line, or record "None".
- **Parallelism** — `parallel-safe` is true only if the tracker exposes a
  dependency relation the orchestrator can read (an issue's `Blocked by`, or
  the equivalent). Confirm from the tracker type; when unsure, default false —
  the orchestrator then runs serially, which is always correct.

### 3. Write

- **`docs/agents/ralph.md`** — from [templates/ralph.md](./templates/ralph.md),
  filled in with the answers from step 2.
- **`.ralph/settings.json`** — from
  [templates/settings.template.json](./templates/settings.template.json), with
  one `Bash(<cmd> *)` allow entry added per distinct gate command (e.g.
  `Bash(pnpm *)`, `Bash(cargo *)`, `Bash(make *)`). Show the user the final
  file before writing.
- **`docs/agents/issue-tracker.md`** — append a `## Ralph loop` section using
  the matching fragment: [local-markdown](./templates/issue-tracker-local.md),
  [GitHub](./templates/issue-tracker-github.md), or
  [GitLab](./templates/issue-tracker-gitlab.md). For any other tracker, write
  the section from scratch with the user, covering all six operations:
  discover, read, dependencies, feature grouping, transition, comment.
- **The `## Agent skills` block** in `CLAUDE.md` / `AGENTS.md` (whichever
  `setup-matt-pocock-skills` already edited) — add a `### Ralph loop` line:
  "Loop config and worker permissions. See `docs/agents/ralph.md`."

**Never write `.claude/settings.local.json`.** That is the user's own file;
its broad worker allowlist would leak into their everyday sessions. The
`orchestrate-ralph` skill copies `.ralph/settings.json` into place at run time
and restores afterwards.

### 4. Done

Tell the user setup is complete: `orchestrate-ralph` can now be run from a
fresh git worktree. They can edit `docs/agents/ralph.md` by hand later;
re-running this skill is only needed to start over.
