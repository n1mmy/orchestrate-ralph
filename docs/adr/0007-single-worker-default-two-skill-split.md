# Single-worker default; orchestrate-ralph splits into two skills

The orchestrator was designed parallel-first: `MAX_PARALLEL = 5` by
default, with serial mode reachable only via `parallel-safe: false` in
`docs/agents/ralph.md`. The ~700-line `ORCHESTRATOR.md` reads as a wave
loop, with single-worker behaviour described as the degenerate case
(`MAX_PARALLEL = 1` collapses the algorithm). Step 9's A–F recovery
(per-branch verify, leave-one-out, singleton fallback) and step 6's
merge-ordering rule exist *only* because a wave can contain multiple
workers whose branches may conflict or whose merged tip may break the
gate.

Field experience: on conflict-heavy projects (issues touching shared
files — hot dependency manifests, shared config, common helpers — that
lose merge races and re-collide on the next wave) the parallel feature's
N× throughput benefit is offset by the throughput cost of conflict
re-runs. The cognitive cost of the multi-branch doctrine is paid every
time anyone reads `ORCHESTRATOR.md`, regardless of whether that run
actually used parallelism.

## Decision

1. **Single-worker is the canonical Ralph loop.** A run dispatches one
   worker per round. The orchestrator doctrine reads as a single-worker
   loop end-to-end; the words "wave," "parallel," "MAX_PARALLEL,"
   "merged set," and "survivor" do not appear.

2. **Parallel mode is a separate skill: `/orchestrate-ralph-parallel`.**
   Discoverable as a distinct entry in the skill index; the user opts in
   per-invocation (the choice depends on the issue set, not just the
   repo). The skill argument `/orchestrate-ralph parallel [N]` is also
   accepted as muscle-memory parity, but the separate skill is the
   canonical entry.

3. **Two fully separate `ORCHESTRATOR.md` files.** The single skill's
   file collapses every multi-branch construct to its N=1 shape; the
   parallel skill keeps today's doctrine, including the step-6
   merge-ordering rule and the full step-9 A–F recovery. The two files
   share no source; drift between them is accepted as a known
   maintenance cost.

4. **`PROMPT.md` is a symlink from the parallel skill to the single
   skill's file.** Worker doctrine is identical in both modes — same
   reset-to-tip preamble, same root-pin, same path-guard self-test, same
   report shape. The harness's `isolation: "worktree"` creates a fresh
   worktree branched off a possibly-stale base regardless of N, so the
   reset preamble is necessary at N=1 too.

5. **Worker still runs in `isolation: "worktree"` in single mode.** The
   merge step survives as a trivial fast-forward: the worker resets to
   the integration tip before working, so the merge cannot conflict by
   construction. Rollback on red-gate is `git reset --hard
   <pre-worker-tip>` on integration.

6. **Worker branches are deleted at end-of-round.** In both modes, after
   all tracker writes are complete (post step 8 in single mode; post
   step 9 in parallel mode if recovery ran), the orchestrator runs
   `git branch -D <branch>` for every worker dispatched in the round.
   Branches survive long enough to be used by step 9's per-branch
   verify, re-merge, and leave-one-out (parallel only); after that
   they have no further role. The reflog retains the commits for 90
   days, so accidental losses are recoverable; the day-to-day
   `git branch` listing stays clean. Asymmetric with `cleanup-ralph`'s
   `-d` choice on purpose: the orchestrator has full context (outcome,
   merge result, gate result) so `-D` is informed; `cleanup-ralph`
   doesn't, so `-d` stays the safe default there.

7. **`parallel-safe: true` in `docs/agents/ralph.md` becomes a
   *capability declaration*, not an instruction to run parallel.** The
   single skill ignores the flag. The parallel skill checks it as a
   prerequisite and halts if false ("this repo's tracker has no
   readable dependency relation — run `/orchestrate-ralph` instead").

## Consequences

- **The single skill's `ORCHESTRATOR.md` shrinks meaningfully.** Step 2's
  wave-fill spread becomes "pick one eligible issue." Step 6's
  merge-order rule and sibling-conflict handling vanish. Step 7's
  "merged set" plurals collapse to "the worker's branch." Step 9's A–F
  recovery collapses into a one-liner inside step 8: "gate red → reset
  to pre-worker tip → comment 'post-hoc gate fail on integration
  re-run' → leave at `ready-for-agent`." The harness-assumptions
  section trims its parallel-collision argument. Plurals throughout
  become singular. Empirically ~100–130 lines come out.

- **Single-mode runs no longer hit step-6 merge conflicts.** The worker
  resets to the integration tip before doing anything, so its branch
  is always a fast-forward of integration at merge time. The
  conflict-heavy projects that motivated this change get a strict win
  on per-issue throughput, at the cost of N× speedup for issues that
  *could* have run in parallel.

- **The parallel skill is unchanged from today's `ORCHESTRATOR.md`.**
  The step-6 merge-ordering rule and step-9 recovery flow already
  landed there. No live-verification work is re-litigated; only the
  file's location moves.

- **Maintenance cost: doctrine changes that aren't parallel-specific
  land twice.** Matcher catalog updates, hook self-test tweaks,
  prerequisite checks, session-setup placement-and-restart — all
  shared mechanics now live in two files. Drift is detectable by
  `diff`; the policy is "single skill is authoritative for shared
  mechanics; parallel skill's matching sections must track."

- **`PROMPT.md` symlink behaviour at install time.** The skill installer
  must resolve the relative symlink correctly. The existing pattern
  (symlink-from-worktree-to-`~/.claude/skills/`) handles this; no new
  install machinery needed.

- **`CONTEXT.md` "Wave vs. round" entry becomes parallel-skill-only.**
  The wave vocabulary survives only where it's load-bearing; the
  single skill's reader never encounters "wave."

- **`cleanup-ralph`'s scope shrinks to interrupted runs and
  `EnterWorktree` leakage.** With Decision #6, healthy orchestrator
  runs no longer leave branches or worktrees behind. What
  `cleanup-ralph` cleans up is the residue from runs that *didn't*
  reach end-of-round cleanly — claude crash, `/quit` mid-wave,
  permission-halt before step 8 — plus interactive `EnterWorktree`
  sessions the user never explicitly removed. Still worth having;
  smaller pile to clean.

## Considered alternatives

- **One skill with the existing `parallel-safe: false` default making
  serial the in-place default.** Rejected: leaves the multi-branch
  doctrine inline in `ORCHESTRATOR.md`, requires every reader to
  mentally collapse N→1. Doesn't deliver the "smoother and less
  complicated" property that motivated the change.

- **One skill with conditional sections (`<!-- parallel only -->`).**
  Rejected: conditionals are inline noise. The reader of the
  single-mode case still has to scan parallel-only blocks to know
  what to skip.

- **Drop parallel entirely.** Rejected: parallel is the right answer
  for some projects (clean dependency graphs, well-isolated features),
  and the option has real value at the cost of a second
  `ORCHESTRATOR.md`. Removing it would also discard the just-landed
  step-6 merge-ordering work and the tested step-9 recovery flow.

- **Shared core `ORCHESTRATOR.md` plus parallel addendum.** Considered.
  Rejected by the maintainer in favour of two self-contained files:
  clearer for each skill's reader, no jumping between files mid-run.
  Maintenance cost of duplication is accepted.

- **Parallel as a `/orchestrate-ralph parallel N` skill argument only,
  no separate skill.** Rejected: parallel is undiscoverable that way.
  A separate skill name surfaces it in `find-skills`, in skill
  listings, and in muscle memory. The argument form is also accepted
  (Decision #2) but is secondary.
