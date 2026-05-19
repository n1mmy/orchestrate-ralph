## Ralph loop

The Ralph orchestrator (`orchestrate-ralph` skill) drives the issues in this
tracker. This section tells it how.

- **Discover** — issues are files at `<feature-dir>/<NN>-<slug>.md`. A wave
  candidate is any file whose `Status:` line reads `ready-for-agent`. Find
  them with `Glob` / `Grep`, not a shell `cat`/`find` loop.
- **Read** — the issue is the whole file, including any notes under a
  `## Comments` heading from prior attempts.
- **Dependencies** — an optional `Blocked by:` line near the top of the file
  names the issues this one depends on. An issue is *eligible* for a wave only
  when every issue it is blocked by has `Status: done`. This is a readable
  dependency relation, so this tracker is **`parallel-safe`**.
- **Feature grouping** — the parent directory `<feature-dir>` is the feature.
  When more issues are eligible than a wave can hold, the orchestrator prefers
  a spread across distinct features.
- **Transition** — edit the `Status:` line in place: `ready-for-agent` →
  `done` on success, → `needs-info` when the issue is wrong or infeasible.
- **Comment** — append a one-to-three-line note under a `## Comments` heading
  at the end of the file.
