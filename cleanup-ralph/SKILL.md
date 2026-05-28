---
name: cleanup-ralph
description: Reap stale Claude Code auto-isolation worktrees in `.claude/worktrees/*` and prune their backing branches. Skips worktrees held by other live claude sessions. Use when asked to "clean up worktrees", "cleanup ralph", reap leftover `.claude/worktrees/*` directories, or shrink the auto-isolation pile.
---

# Cleanup Ralph

Reap stale worktrees under `.claude/worktrees/` and prune their backing
branches. The Claude Code harness creates a worktree at
`.claude/worktrees/<id>` on branch `worktree-<id>` for every `EnterWorktree`
(interactive) and every `Agent` call with `isolation: "worktree"`
(orchestrate-ralph workers); neither `ExitWorktree` nor session end reaps
them. This skill is the manual reaper. Healthy `orchestrate-ralph` runs
already clean worker worktrees at end-of-round, so the residue this skill
targets is the crash / `/quit`-mid-wave / interactive-`EnterWorktree` pile.

## Eligibility — all three must hold

1. The path is under `<primary-repo-root>/.claude/worktrees/`.
2. The path is not the current working directory.
3. The lock-pid is **not** another live claude session. Specifically: the
   pid is dead, or `ps -p <pid> -o comm=` does not return `claude`, or the
   pid is alive and *is* claude but matches **this** session's own claude
   pid.

The "matches this session" branch is essential. One long-running claude
session stamps every auto-isolation lock with its own pid; those locks are
the dominant cleanup target.

Worker leftovers and `EnterWorktree` leftovers cannot be told apart from
git metadata — both use the same `bridge-cse_<id>` /
`worktree-bridge-cse_<id>` naming. Both are equally safe to remove; the
skill does not try to discriminate.

## What to do

Run each step in order. Use **bare `Bash` calls** (no `&&` chains) so each
command's output is independently readable if something fails.

### Preflight: warn if running under enforcement

If `.claude/settings.local.json` exists in the primary repo root or in the
current worktree, this session may be running under enforcement. Under
`permissions.defaultMode: "dontAsk"`, any of the commands this skill
issues that aren't allowlisted will silently auto-deny mid-flight,
leaving the cleanup half-done with confusing output.

Before step 1, tell the user the skill needs these `Bash` allow entries
and that it may halt mid-run without them:

- `Bash(git worktree list:*)`
- `Bash(git worktree unlock:*)`
- `Bash(git worktree remove:*)`
- `Bash(git worktree prune:*)`
- `Bash(git branch:*)` (covers `-d`, `-D`, `--list`)
- `Bash(git merge-base:*)`
- `Bash(git rev-parse:*)`
- `Bash(kill -0:*)`
- `Bash(ps:*)`

Confirm the user wants to proceed; if they cancel, exit cleanly. If the
settings file is absent (unenforced interactive session), skip this
preflight and go straight to step 1.

### 1. Find this session's claude pid

Walk the parent-process tree from `$$` until a process with `comm=claude`
is found; remember it as the **self claude pid**. Robust to invocation
through nested shells.

Snippet that works:

```bash
pid=$$
while [ -n "$pid" ] && [ "$pid" != "1" ]; do
  comm=$(ps -o comm= -p "$pid" 2>/dev/null | tr -d ' ')
  if [ "$comm" = "claude" ]; then echo "$pid"; break; fi
  pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
done
```

If no claude ancestor is found, halt: without it the skill cannot tell
"my own locks" from "another session's locks", and pruning would risk
yanking another live session's workspace.

### 2. Resolve the primary repo root, the git common dir, and cwd

`git rev-parse --show-toplevel` returns the *active worktree's* root, not
the primary repo root. The primary root is the **first** `worktree` entry
in `git worktree list --porcelain`. Use that.

- **Primary root:** first `worktree <path>` line of `git worktree list
  --porcelain`.
- **Git common dir:** `git rev-parse --git-common-dir`. Lock files live at
  `<git-common-dir>/worktrees/<basename>/locked`.
- **Cwd:** `pwd`.

### 3. Classify each worktree

Iterate `git worktree list --porcelain`. For each entry, capture `path`
and `branch` (the `branch refs/heads/<name>` line in the same block, if
any — detached worktrees have no branch). Then:

- **Skip silently** if `path` is not under `<primary-root>/.claude/worktrees/`.
- **Mark as current** if `path` equals cwd — listed in the summary as
  "kept (current)" but never removed.
- Otherwise locate the lock file at
  `<git-common-dir>/worktrees/<basename>/locked`. If the file is missing
  or has no `pid <N>` field, eligibility check 3 vacuously passes.
- If a lock-pid is present and alive (`kill -0`) and `ps -p <pid> -o
  comm=` returns `claude` and the pid is **not** the self claude pid →
  mark as **skipped** (held by another live claude). Record the pid in
  the summary.
- Otherwise → **eligible**.

### 4. Gather metadata for each eligible entry

- basename of the path
- branch name (from the porcelain block) — empty if detached
- branch tip SHA (`git rev-parse <branch>`, short form for display)
- branch reachability: would `git branch -d <branch>` succeed?
  Check `git merge-base --is-ancestor <branch> <ref>` against:
  - the current `HEAD`,
  - the default branch (`main` or `master`, whichever exists locally).
  If reachable from any of them, mark **reachable**; else **unreachable**.

Reachability previews which branches `git branch -d` will prune vs.
refuse.

### 5. Print the plan

A table of eligible entries: basename, branch (or `(detached)`), tip SHA,
reachable yes/no. Visually mark unreachable rows so the user sees which
branches will end up in the "kept" summary.

If there are any skipped entries, print them too: basename + the claude
pid holding the lock. This lets the user confirm those skips were
intended.

If there are zero eligible entries, print that and exit cleanly. Do not
prompt.

### 6. Confirm once

Ask exactly once:

> Remove these N worktrees and prune their branches? [y/N]

Default no on empty input or anything other than `y` / `Y`.

### 7. On confirm: remove

For each eligible entry, two **separate** bare `Bash` calls (do **not**
chain with `&&` — preserve per-step output):

```
git worktree unlock <path>
git worktree remove --force <path>
```

A `git worktree unlock` failure for a never-locked worktree is non-fatal;
let `git worktree remove --force` proceed regardless.

Then per branch:

```
git branch -d <branch>
```

**`-d`, not `-D`.** `-d` refuses to delete a branch that isn't reachable
from another ref — exactly the safety net that catches an integration
branch with unmerged work the user hasn't merged or pushed. Collect the
refusals; they go in the summary.

Finally one `git worktree prune` to tidy any stale `.git/worktrees/`
metadata refs that remain.

### 8. Print summary

- **Removed worktrees:** N
- **Pruned branches:** M
- **Kept branches** (`-d` refused, not reachable from `HEAD` /
  `main` / `master`): K — list each with its tip SHA so the user can
  recover with `git branch <name> <sha>` if needed, or `git branch -D
  <name>` to force-delete.
- **Skipped worktrees** (held by other live claude sessions): S — list
  basename + holder pid.

## Edge cases

- **Cwd is the only entry under `.claude/worktrees/`.** Zero eligible;
  print the empty state and exit.
- **Repo has no `.claude/worktrees/`.** Zero eligible; exit.
- **Lock file missing or no `pid` field.** Eligibility check 3 passes —
  the worktree is eligible. A manually-locked worktree the user created
  with no pid stamp is acceptable to reap; they put it there and can
  recreate it.
- **A worktree's working directory was already `rm -rf`'d.** `git worktree
  remove --force` may complain; the final `git worktree prune` clears
  the leftover metadata regardless.
- **A worktree was created in detached HEAD** (no `branch` line in the
  porcelain block). Skip the `git branch -d` step for it; the worktree
  removal alone is sufficient.

## Safety choices baked in

- **Path filter first.** Only paths under
  `<primary-repo-root>/.claude/worktrees/` are ever candidates. Even if
  the lock-pid check is wrong, the primary checkout and any custom-named
  worktrees elsewhere are out of scope.
- **`-d` not `-D` for branch pruning.** A recent orchestrator's
  integration branch holding unmerged work survives as a "kept" entry
  the user decides about manually.
- **Single confirmation, not per-entry.** The full plan is shown before
  any destructive action; the table is the framing.

## Argument surface

`/cleanup-ralph` with no arguments runs the interactive flow above. No
flags are supported in this revision — `--dry-run` and `--yes` are
deferred to a follow-up plan if a real need surfaces.
