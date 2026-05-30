## Ralph loop

How the Ralph orchestrator (`orchestrate-ralph` skill) does each of its
operations against this tracker:

- **Discover** — issues are files at `<feature-dir>/<NN>-<slug>.md`. A
  candidate is any file whose `Status:` line reads `ready-for-agent`. Find
  them with the `Glob` / `Grep` tools, or — if your harness lacks them —
  `rg` / `find` as single bare `Bash` commands. Not a `cat`/`find` loop.
- **Read** — the issue is the whole file, including any notes under a
  `## Comments` heading from prior attempts.
- **Dependencies** — an optional `Blocked by:` line near the top of the
  file names the issues this one depends on. An issue is *eligible* only
  when every issue it is blocked by has `Status: done`. This is a readable
  dependency relation, so this tracker is **`parallel-safe`**.
  <!-- If your issues do NOT use a machine-readable `Blocked by:` line —
  dependencies are only described in prose, or not tracked — set
  `parallel-safe: false` in docs/agents/ralph.md so the loop runs serially. -->

- **Feature grouping** — the parent directory `<feature-dir>` is the
  feature. When more issues are eligible than a wave can hold, prefer a
  spread across distinct features.
- **Transition** — `Edit` the `Status:` line in place: `ready-for-agent`
  → `done` on success, → `needs-info` when the issue is wrong or
  infeasible.
- **Comment** — append a one-to-three-line note under a `## Comments`
  heading at the end of the file. Cluster every transition `Edit` and
  every comment for a wave into **one `git commit` per round** on the
  integration branch.
