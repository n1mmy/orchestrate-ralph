---
name: orchestrate-ralph
description: Run a Ralph loop as an interactive orchestrator that dispatches worker sub-agents in parallel waves to grind a project's issue tracker to done. Use when asked to "orchestrate ralph", run the Ralph loop, or drive the issue tracker with sub-agents.
---

# Orchestrate Ralph

Run the interactive Ralph orchestrator over this repo's issue tracker.

## Prerequisites — check first, stop if any is missing

Run each check as its own **single bare `Bash` call** — no `&&` / `;` / `|`
chains, no redirects, no `echo`-labelled bundles. A compound command is a
distinct pattern the permission matcher does not recognise; it prompts (or,
unattended, fails) right at the start of the run. For the file-existence
checks in item 1, prefer `Read` or `Glob` — no `Bash` is needed at all.

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

## Session setup — placement and restart

The orchestrator runs in **this** claude session, and it does its work under
the same enforced permission environment as workers: `.ralph/settings.json`
placed at `.claude/settings.local.json` **and loaded by claude at session
startup**. Claude Code reads settings at startup only — a mid-session
placement is not re-read. If your session predates the placement, the
orchestrator inherits your interactive defaults instead of the loop's
enforcement, and doctrine alone has to keep it from misbehaving; empirically
that is not enough. Hence: place, then restart, then run.

Three states:

1. **`.claude/settings.local.json` does not exist.** Copy
   `.ralph/settings.json` to it. Then **halt with restart instructions:**
   *"Settings placed. Exit claude (`/quit`) and re-launch it from this
   worktree, then run `/orchestrate-ralph` again. Claude Code loads settings
   at session startup; this session predates the placement."*

2. **It exists and differs from `.ralph/settings.json`.** Fatal. A
   pre-existing `.claude/settings.local.json` is the user's own interactive
   allow/deny list — valuable, not stale; never overwrite, swap, or back it
   up. Tell the user to run in a fresh worktree (the recommended location
   anyway). **Do not suggest they delete the file.**

3. **It exists and is byte-identical to `.ralph/settings.json`.** It was
   placed by an earlier run — but whether *this* claude session actually
   loaded it at startup is a separate question. Probe by running one bare
   `Bash` call: `cd .`. The `Bash(cd:*)` entry in the deny block exists
   precisely so this canary works — `cd` is a perfect no-op in Claude Code
   (cwd does not persist across `Bash` calls) and has no external
   dependencies. Under enforcement, the deny block catches it and returns a
   clean tool error (no prompt). Under a session that predates the
   placement, `cd` is not on your interactive allowlist either, so the
   call prompts you to allow or deny — which is fine, because the probe
   runs at the moment you invoked this skill, with you at the keyboard.
   - **Errored cleanly with "permission denied" / no prompt → proceed.**
     The orchestrator is under enforcement.
   - **Prompted you, or succeeded → halt with restart instructions** as
     in (1). Deny the prompt if it appears; either outcome tells you the
     file is on disk but this session never loaded it.

Worker sub-agents inherit this session's enforced permissions — same hooks,
same `deny` block, same `dontAsk` — by the same startup-load mechanism, one
nesting level deeper.

The loop does not restore or remove `.claude/settings.local.json` when it
ends: the run happens in a disposable worktree, the file is gitignored, and
the worktree is thrown away afterwards. Leaving it in place is correct.

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
