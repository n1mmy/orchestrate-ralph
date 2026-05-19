## Ralph loop

The Ralph orchestrator (`orchestrate-ralph` skill) drives the issues in this
tracker. This section tells it how. All operations use the `glab` CLI.

- **Discover** — `glab issue list --label ready-for-agent --output json`. A
  wave candidate is any open issue carrying the `ready-for-agent` label.
- **Read** — `glab issue view <id> --output json` (and its notes). The issue
  is its description plus its notes — prior-attempt failure notes are notes.
- **Dependencies** — declared with GitLab linked issues, relationship "is
  blocked by". An issue is *eligible* for a wave only when every issue
  blocking it is closed. This is a readable dependency relation, so this
  tracker is **`parallel-safe`**.
  <!-- If this repo does NOT use GitLab linked-issue blocking, replace the two
  lines above with the convention you do use — e.g. a `Blocked by: #12` line
  in the description — and, if it is not reliably machine-readable, set
  `parallel-safe: false` in docs/agents/ralph.md. -->
- **Feature grouping** — the feature is the issue's `feature::*` scoped label
  (or its milestone). Issues with no feature label are each their own group.
  The orchestrator prefers a wave spread across distinct features.
- **Transition** — on success:
  `glab issue update <id> --unlabel ready-for-agent --label done`. When wrong
  or infeasible: `--unlabel ready-for-agent --label needs-info`. Whether `done`
  also closes the issue is the user's call.
- **Comment** — `glab issue note <id> --message "<note>"`.
