## Ralph loop

The Ralph orchestrator (`orchestrate-ralph` skill) drives the issues in this
tracker. This section tells it how. All operations use the `gh` CLI.
**Reads are shared between the orchestrator and workers; writes are
orchestrator-only** — workers call only the read rows below, and the
**Transition** and **Comment** rows are the orchestrator's, written only
after a wave merges and its gate is green.

Read operations (worker reads its issue; orchestrator reads to pick the
wave):

- **Discover** — `gh issue list --label ready-for-agent --state open --json number,title,body,labels`.
  A wave candidate is any open issue carrying the `ready-for-agent` label.
- **Read** — `gh issue view <number> --json title,body,comments`. The issue
  is its body plus its comments — prior-attempt failure notes are comments.
- **Dependencies** — declared with GitHub's native issue dependencies
  ("blocked by"). An issue is *eligible* for a wave only when every issue
  blocking it is closed. This is a readable dependency relation, so this
  tracker is **`parallel-safe`**.
  <!-- If this repo does NOT use GitHub's native issue dependencies, replace
  the two lines above with the convention you do use — e.g. a
  `Blocked by: #12, #15` line in the issue body — and, if that convention is
  not reliably machine-readable, set `parallel-safe: false` in
  docs/agents/ralph.md. -->
- **Feature grouping** — the feature is the issue's `feature/*` label
  (or its milestone). Issues with no feature label are each their own
  group. The orchestrator prefers a wave spread across distinct features.

Write operations — **orchestrator only**, post-wave:

- **Transition** — to `done` when the issue is in the merged set and the
  gate is green:
  `gh issue edit <number> --remove-label ready-for-agent --add-label done`.
  To `needs-info` when the worker reported `needs-info` or the retry
  budget is exhausted:
  `--remove-label ready-for-agent --add-label needs-info`. Whether `done`
  also closes the issue is the user's call; the orchestrator only sets
  the label.
- **Comment** — `gh issue comment <number> --body "<note>"`. Comments
  arise from worker failure reasons, merge conflicts, per-branch verify
  failures during recovery, and retry-budget exhaustion.
