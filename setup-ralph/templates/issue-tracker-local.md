## Ralph loop

The Ralph orchestrator (`orchestrate-ralph` skill) drives the issues in this
tracker. This section tells it how. **Reads are shared between the
orchestrator and workers; writes are orchestrator-only** — workers call
only the read rows below, and the **Transition** and **Comment** rows are
the orchestrator's, written only after a wave merges and its gate is green.

Read operations (worker reads its issue; orchestrator reads to pick the
wave):

- **Discover** — issues are files at `<feature-dir>/<NN>-<slug>.md`. A wave
  candidate is any file whose `Status:` line reads `ready-for-agent`. Find
  them with the `Glob` / `Grep` tools, or — if your harness lacks them —
  `rg` / `find` as single bare `Bash` commands. Not a `cat`/`find` loop.
- **Read** — the issue is the whole file, including any notes under a
  `## Comments` heading from prior attempts.
- **Dependencies** — an optional `Blocked by:` line near the top of the
  file names the issues this one depends on. An issue is *eligible* for a
  wave only when every issue it is blocked by has `Status: done`. This is
  a readable dependency relation, so this tracker is **`parallel-safe`**.
- **Feature grouping** — the parent directory `<feature-dir>` is the
  feature. When more issues are eligible than a wave can hold, the
  orchestrator prefers a spread across distinct features.

Write operations — **orchestrator only**, post-wave:

- **Transition** — `Edit` the `Status:` line in place: `ready-for-agent` →
  `done` when the issue is in the merged set and the gate is green, →
  `needs-info` when the worker reported `needs-info` or the retry budget
  is exhausted.
- **Comment** — append a one-to-three-line note under a `## Comments`
  heading at the end of the file. Comments arise from worker failure
  reasons, merge conflicts, per-branch verify failures during recovery,
  and retry-budget exhaustion.

Cluster every transition `Edit` and the matching `git add` into **one
`git commit` per round** on the integration branch — that keeps the
history readable.
