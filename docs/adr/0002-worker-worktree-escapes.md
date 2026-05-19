# Worker worktree isolation does not sandbox file writes

A worker sub-agent is dispatched with `isolation: "worktree"`. That isolates
the worker's **git branch and index** — not its filesystem. A worktree is a
second checkout, not a sandbox: the worker process shares one filesystem with
the orchestrator and every other checkout, and `Write` / `Bash` can target any
absolute path the OS permits.

A live run confirmed this. Workers wrote project files into another checkout's
working tree via a wrongly-rooted path — an absolute path into a sibling
checkout, or a `../..` climb past the worktree root. The worker's *branch* was
correct in each case; the escaped files were a side-effect duplicate. The
committed-escape variant (a worker committing onto the integration branch
directly) was also observed earlier.

## Decision

1. **Treat escapes as mitigate-and-detect, not prevent.** No filesystem
   sandbox is available to the skill, so the loop cannot stop an escape — it
   hardens worker path discipline and checks for escapes after each wave.

2. **Worker doctrine forbids the actual failure mode.** `PROMPT.md` already
   bans `cd` / `git -C` / full binary paths; it now also requires project
   files be addressed by worktree-relative paths only, forbids constructing an
   absolute path into the repo or climbing above the worktree root, and has
   the worker pin its root (`git rev-parse --show-toplevel`) at setup.

3. **The orchestrator runs two escape checks at step 5, before merging.** A
   *committed* escape (the integration tip moved) halts the loop — trust is
   broken. An *untracked* escape (`git status --porcelain` shows stray project
   files) is non-fatal: the worker's branch is still correct, so the loop
   notes it, recovers, and continues.

4. **Narrow cleanup authorisation.** When a merge aborts because untracked
   escape litter would be overwritten, the orchestrator may run `git clean -f`
   on exactly the paths git named — those files are about to be replaced by
   the merge's correct version, so removal is loss-free. No other untracked
   removal is authorised.

## Alternatives considered

- **Repo-wide ref/file scan to find every escape.** Rejected: it cannot
  distinguish a worker escape from a teammate's concurrent commit or untracked
  WIP in another worktree, so it false-positives and would halt the loop on
  unrelated work. Detection is scoped to refs and the working tree the
  orchestrator owns.
- **Run the orchestrator in a separate worktree as the fix.** Rejected as a
  *fix*: worktree placement is a blast-radius lever, not prevention. The
  absolute-path variant ignores it entirely, and for the climb variant a
  separate worktree merely redirects the escape onto the orchestrator's own
  integration worktree. Still worth doing for blast radius — but not a cure.
- **Broad `rm` allowlist for cleanup.** Rejected: an unattended `rm` of
  untracked files risks deleting gitignored build artifacts or a user's work.
  `git clean -f` scoped to merge-named pathspecs is loss-free by construction.

## Consequences

- Escapes can still happen. The loop now detects both variants; the untracked
  variant self-recovers, the committed variant halts for the user.
- Non-colliding untracked litter is left in place and reported — the
  orchestrator cleans only what blocks a merge.
- The true fix is a filesystem sandbox confining a worker's writes to its
  worktree. That is a Claude Code harness capability the skill cannot provide.
  If the harness gains it, the step-5 escape checks become a backstop rather
  than the primary defence.
