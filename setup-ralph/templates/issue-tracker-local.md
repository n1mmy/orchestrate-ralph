## Ralph loop

The Ralph orchestrator (`orchestrate-ralph` skill) drives the issues in this
tracker. This section tells it how. Per [ADR 0006](../adr/0006-orchestrator-owns-merge-and-transition.md),
**reads are shared between the orchestrator and workers; writes are
orchestrator-only.** Workers call only the read rows; the **Transition** and
**Comment** rows below are the orchestrator's transition phase (step 8).

Read operations:

- **Discover** *(orchestrator, step 2)* — issues are files at
  `<feature-dir>/<NN>-<slug>.md`. A wave candidate is any file whose
  `Status:` line reads `ready-for-agent`. Find them with the `Glob` / `Grep`
  tools, or — if your harness lacks them — `rg` / `find` as single bare
  `Bash` commands. Not a `cat`/`find` loop.
- **Read** *(worker, dispatch-time; orchestrator, step 1 reload)* — the
  issue is the whole file, including any notes under a `## Comments` heading
  from prior attempts.
- **Dependencies** *(orchestrator, step 2)* — an optional `Blocked by:` line
  near the top of the file names the issues this one depends on. An issue is
  *eligible* for a wave only when every issue it is blocked by has
  `Status: done`. This is a readable dependency relation, so this tracker is
  **`parallel-safe`**.
- **Feature grouping** *(orchestrator, step 2)* — the parent directory
  `<feature-dir>` is the feature. When more issues are eligible than a wave
  can hold, the orchestrator prefers a spread across distinct features.

Write operations — **orchestrator only**, in step 8 (transition):

- **Transition** — `Edit` the `Status:` line in place: `ready-for-agent` →
  `done` when the issue is in the merged set and the step-7 (or step-9
  recovery) gate is green, → `needs-info` when the worker reported
  `needs-info` or the retry budget is exhausted.
- **Comment** — append a one-to-three-line note under a `## Comments`
  heading at the end of the file. Comments arise from worker `reasonText`
  (failure), merge conflicts (step 6), per-branch verify failures (step 9
  B), leave-one-out / singleton fallback (step 9 E/F), and retry-budget
  exhaustion.

Cluster every transition-phase `Edit` and the matching `git add` into
**one `git commit` per round** on the integration branch — that keeps the
history readable and matches step 8's "one commit per round" guidance.
