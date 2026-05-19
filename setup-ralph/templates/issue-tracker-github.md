## Ralph loop

The Ralph orchestrator (`orchestrate-ralph` skill) drives the issues in this
tracker. This section tells it how. All operations use the `gh` CLI.

- **Discover** — `gh issue list --label ready-for-agent --state open --json number,title,body,labels`.
  A wave candidate is any open issue carrying the `ready-for-agent` label.
- **Read** — `gh issue view <number> --json title,body,comments`. The issue is
  its body plus its comments — prior-attempt failure notes are comments.
- **Dependencies** — declared with GitHub's native issue dependencies
  ("blocked by"). An issue is *eligible* for a wave only when every issue
  blocking it is closed. This is a readable dependency relation, so this
  tracker is **`parallel-safe`**.
  <!-- If this repo does NOT use GitHub's native issue dependencies, replace
  the two lines above with the convention you do use — e.g. a
  `Blocked by: #12, #15` line in the issue body — and, if that convention is
  not reliably machine-readable, set `parallel-safe: false` in
  docs/agents/ralph.md. -->
- **Feature grouping** — the feature is the issue's `feature/*` label (or its
  milestone). Issues with no feature label are each their own group. The
  orchestrator prefers a wave spread across distinct features.
- **Transition** — on success: `gh issue edit <number> --remove-label ready-for-agent --add-label done`.
  When wrong or infeasible: `--remove-label ready-for-agent --add-label needs-info`.
  Whether `done` also closes the issue is the user's call; the orchestrator
  only sets the label.
- **Comment** — `gh issue comment <number> --body "<note>"`.
