# Plan — `cleanup-ralph` skill

A new skill `/cleanup-ralph` that removes stale Claude Code auto-isolation
worktrees in `.claude/worktrees/` plus their backing branches.

## Why

Each Claude Code session that uses `EnterWorktree` (interactive workflow)
or `Agent` with `isolation: "worktree"` (orchestrate-ralph worker
dispatch) creates a worktree at `.claude/worktrees/<id>` on a branch
named `worktree-<id>`. The harness does not reap these on session end or
on `ExitWorktree`; they accumulate. Field evidence at the time of
writing: this repo has 22 such worktrees from a single long-running
claude session.

Per [ADR 0007](../docs/adr/0007-single-worker-default-two-skill-split.md)
Decision #6, the orchestrator now reaps worker worktrees in step 6 and
deletes worker branches at end-of-round — so healthy runs don't leak.
`cleanup-ralph`'s remaining scope is the residue from runs that
*didn't* reach end-of-round cleanly: claude crash, `/quit` mid-wave,
permission-halt before step 8, plus interactive `EnterWorktree`
sessions the user never explicitly removed. The pile is smaller post
ADR 0007, but the skill is still needed for those failure modes.

## Eligibility criterion

A worktree is cleanup-eligible iff **all three** hold:

1. Its path is under `<repo-root>/.claude/worktrees/`.
2. Its path is not the current working directory.
3. Its lock-pid is *not* a live `claude` process belonging to **another**
   session. (Either the pid is dead, or the pid is the current
   session's own claude pid, or the pid is alive but is not a `claude`
   process.)

The third condition prevents nuking a workspace held by a concurrent
claude session. The "lock-pid is *this* session's own pid" branch is
essential — empirically a single long-running claude session leaves
dozens of auto-isolation locks all stamped with its own pid, and those
are the dominant cleanup target.

Distinguishing orchestrator-worker leftovers from `EnterWorktree`
leftovers is **impossible from git metadata** — both use the same
`bridge-cse_<id>` / `worktree-bridge-cse_<id>` naming scheme. Both are
equally safe to remove; both are equally worth cleaning. The skill does
not try to discriminate.

## Skill behaviour

`SKILL.md` instructs claude to do this, top to bottom:

1. **Resolve the parent claude pid.** Walk the parent-process tree
   (`ps -o ppid= -p $$`, then repeat against the printed pid) until a
   process named `claude` is found; record that pid. Robust to
   invocation through nested shells.
2. **Resolve the current cwd** via `pwd` (or `git rev-parse
   --show-toplevel` for the repo root).
3. **Iterate** `git worktree list --porcelain`. For each entry:
   - Skip if path is not under `<repo-root>/.claude/worktrees/`.
   - Skip if path equals current cwd.
   - Read `<git-common-dir>/worktrees/<basename>/locked`. Parse out
     `pid <N>` from its content.
   - If `<N>` is alive AND `ps -p <N> -o comm=` returns `claude` AND
     `<N>` differs from the parent claude pid → skip (held by another
     live claude session).
   - Otherwise → mark eligible.
4. For each eligible entry, gather: path basename, branch name, branch
   tip SHA, branch reachability (is the branch reachable from `HEAD`,
   or from `main` / `master` / the repo's default branch, whichever
   exists?). This answers "is pruning this branch loss-free?"
5. **Print a table** of eligible entries with the gathered fields.
   Visually mark unreachable entries so the user knows pruning will
   report them as kept-branches.
6. **Print the skipped list** (held by other live claude sessions, if
   any) so the user can confirm none of those are accidental.
7. **Ask once:** `Remove these N worktrees and prune reachable branches? [y/N]`.
8. On `y`:
   - For each eligible entry, two separate bare `Bash` calls:
     `git worktree unlock <path>` then `git worktree remove --force
     <path>`. No `&&` chain — preserves per-step output for diagnosis
     if either side fails.
   - For each removed worktree's branch: `git branch -d <branch>`
     (note: **`-d`, not `-D`**). `-d` refuses to delete branches that
     aren't reachable from another ref; the skill collects those
     errors and reports kept branches with their tip SHAs.
   - Optional final `git worktree prune` to clean stale `.git/worktrees/`
     metadata refs (no-op if everything went well).
9. **Print a summary:**
   - Removed worktrees: N
   - Pruned branches: M
   - Kept branches (unreachable, `-d` refused): K with their tip SHAs
   - Skipped worktrees (held by other claude sessions): S

## Touch list

| File | Action |
|---|---|
| `cleanup-ralph/SKILL.md` | New: the entire skill — instructions per "Skill behaviour" above |
| `cleanup-ralph/` | New folder; no `PROMPT.md` or `ORCHESTRATOR.md`. The skill has no sub-agents; everything runs in the invoking session. |
| `setup-ralph/templates/settings.template.json` | Verify `Bash(git worktree:*)` and `Bash(git branch:*)` are allowlisted. They are already required by `orchestrate-ralph`'s step-6 reaping, so this should be a no-op — but check. |
| `README.md` | Add `cleanup-ralph` to the "Three skills" list (alongside the split from the other plan). |

## Argument surface

`/cleanup-ralph` with no args runs the interactive flow above.

Optional flags (deferred unless needed):
- `--dry-run` — print the eligible list and exit without prompting.
- `--yes` — skip the confirmation prompt (unattended scripts).

If both flags are absent, the interactive flow is the only path.

## Safety choices

- **`-d` not `-D` when pruning branches.** The orchestrator's integration
  branch from a recent run *might* be in the eligible set, with
  unmerged work the user hasn't pushed up. `-d` refuses to delete a
  branch not reachable from another ref → the user sees it in the
  "kept" summary and decides manually. This is the single biggest
  safety gain; cost is one line of extra summary output per kept
  branch.
- **Single confirmation, not per-worktree.** The eligible-list table
  shows everything before any destructive action. Per-entry
  confirmation defeats the framing of the skill.
- **Path filter first.** Even if the lock-pid check is somehow wrong,
  only `.claude/worktrees/*` paths are ever candidates — never the
  primary checkout, never custom worktrees living elsewhere.

## Edge cases

- **Cwd is the only `.claude/worktrees/*` entry.** Print "no eligible
  worktrees" and exit cleanly.
- **Repo has no `.claude/worktrees/` directory.** Same — no eligible
  worktrees; exit cleanly.
- **A concurrent claude session has dispatched a worker right now.** The
  worker's lock has a live claude pid that differs from this session's
  parent pid. Skipped; appears in the "skipped" summary so the user
  knows it was deliberate.
- **A worktree under `.claude/worktrees/` has a lock with no pid field**
  (someone hand-locked it without using Claude Code). The "pid is
  claude" check is false → no skip → eligible. Acceptable: the user
  put it there manually and can re-create it.
- **A worktree outside `.claude/worktrees/`** (e.g., `probe-group-m` in
  this repo). The path filter excludes it.
- **The branch being pruned is the integration branch of a recent
  orchestrate-ralph run that the user hasn't merged into main.** The
  `-d` refusal catches this; the branch stays. The user sees it in
  the "kept" summary and can decide.

## Validation

- Run on this repo's current 22-worktree state. Expected: 21 removed, 1
  kept (current cwd). All 21 branches pruned (their tips are reachable
  from `main` or from the current `HEAD`).
- Run again immediately. Expected: 0 eligible, no-op summary.
- Create a hand-made worktree outside `.claude/worktrees/` (e.g.
  `git worktree add ../scratch HEAD~5`). Run. Expected: untouched.
- Fork a sleeping process and rename its `comm` to `claude` (or
  similar simulation), then create a worktree with a lock-pid pointing
  at it. Run cleanup-ralph from a different session. Expected: the
  faux-claude-held worktree appears in the "skipped" list.
- Create a branch with an unmerged commit (`git checkout -b lost
  HEAD~3; git commit --allow-empty -m unmerged`), attach a worktree
  to it (`git worktree add ../lost-tree lost`), then remove the
  worktree (`git worktree remove ../lost-tree`). Move that worktree
  shell into `.claude/worktrees/` namespace if needed for the path
  filter to apply, then run cleanup-ralph. Expected: worktree
  removed, branch reported as kept (unreachable) because `git branch
  -d` refused.

## Open follow-ups not in this plan

- Should `cleanup-ralph` run automatically as part of `orchestrate-ralph`
  session setup? Probably not — surprise destructive actions on a
  per-run basis is the wrong default. Keep user-invoked.
- Should the skill cover worktrees that live in `.git/worktrees/` but
  whose working directory is missing (i.e., the directory was `rm
  -rf`'d but `git worktree remove` was never called)? Currently caught
  by `git worktree prune` at step 8. If the failure mode is more
  visible than that, treat as a separate plan.
