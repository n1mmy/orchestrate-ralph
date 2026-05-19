---
name: orchestrate-ralph
description: Run a Ralph loop as an interactive orchestrator that dispatches worker sub-agents in parallel waves to grind a project's issue tracker to done. Use when asked to "orchestrate ralph", run the Ralph loop, or drive the issue tracker with sub-agents.
---

# Orchestrate Ralph

Run the interactive Ralph orchestrator over this repo's issue tracker.

## Prerequisites — check first, stop if any is missing

1. **`setup-ralph` has been run.** `docs/agents/ralph.md` and
   `.ralph/settings.json` must both exist. If not, tell the user to run
   `setup-ralph` (and `setup-matt-pocock-skills` before it) and stop.
2. **You are on a clean, dedicated integration branch — ideally in a separate
   worktree.** The branch you are on becomes the integration branch: workers
   branch off it, merges land on it, and `git reset --hard` may run on it
   (revert-and-serialize). So it must not be the repo's default branch
   (`main` / `master`), the working tree must be clean, and it should be a
   branch the user is happy to hand back. A fresh `git worktree` satisfies all
   of this and keeps the run off the user's primary checkout — strongly
   preferred. If you are in the primary checkout, stop and ask before
   proceeding.

## Session setup — worker permissions

Worker sub-agents inherit this session's permissions. `.ralph/settings.json`
holds the curated worker allowlist and the remote-git `deny` block; the user's
own `.claude/settings.local.json` deliberately does not. Before starting:

1. If `.claude/settings.local.json` exists, back it up to
   `.claude/settings.local.json.pre-ralph` — but if that backup already exists
   (an earlier interrupted run), leave it untouched.
2. Copy `.ralph/settings.json` to `.claude/settings.local.json`.
3. When the run ends, on any stop condition: restore the backup if there is
   one, then remove it.

In a fresh worktree there is usually no `.claude/settings.local.json` to back
up (it is gitignored and not checked out), so this is mostly a no-op safety
net for the main-checkout case.

## Run the loop

Read `ORCHESTRATOR.md` (in this skill folder) in full and become the
orchestrator it describes. Run that loop until a stop condition fires.

`ORCHESTRATOR.md` is the single source of truth for the loop's behaviour —
wave selection, dispatch, retries, merge and gate-verify, escalation, stop
conditions. This skill only points at it; do not paraphrase or second-guess it
here.

## Watching a run

`watch-steps.py` (in this skill folder) turns the workers' transcripts into a
compact one-line-per-tool-call log. Run it in a separate terminal:
`python3 <skill-folder>/watch-steps.py <repo-worktree-path>`. It is a plain
process, not an agent — nothing it reads enters any agent's context.
