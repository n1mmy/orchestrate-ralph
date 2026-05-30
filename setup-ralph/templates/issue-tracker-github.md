## Ralph loop

How the Ralph orchestrator (`orchestrate-ralph` skill) does each of its
operations against this tracker. All operations use the `gh` CLI.

- **Discover** — `gh issue list --label ready-for-agent --state open --json number,title,body,labels`.
  A candidate is any open issue carrying the `ready-for-agent` label.
- **Read** — `gh issue view <number> --json title,body,comments`. The
  issue is its body plus its comments — prior-attempt failure notes are
  comments.
- **Dependencies** — declared with GitHub's native issue dependencies
  ("blocked by"). An issue is *eligible* only when every issue blocking
  it carries the `done` label (closing is the user's call; the label is
  the canonical completion marker the loop writes). This is a readable
  dependency relation, so this tracker is **`parallel-safe`**.
  <!-- If this repo does NOT use GitHub's native issue dependencies, replace
  the two lines above with the convention you do use — e.g. a
  `Blocked by: #12, #15` line in the issue body — and, if that convention is
  not reliably machine-readable, set `parallel-safe: false` in
  docs/agents/ralph.md. -->
- **Feature grouping** — the feature is the issue's `feature/*` label (or
  its milestone). Issues with no feature label are each their own group.
  Prefer a wave spread across distinct features.
- **Transition** — on success:
  `gh issue edit <number> --remove-label ready-for-agent --add-label done`.
  When wrong or infeasible:
  `--remove-label ready-for-agent --add-label needs-info`. Whether `done`
  also closes the issue is the user's call; only the label is set.
- **Comment** — write the note to a worktree-local tempfile first
  (e.g. `.ralph/comment-body.tmp`), then
  `gh issue comment <number> --body-file <path>`. Do not pass the note via
  `--body "<note>"`: worker `reasonText` may contain `"`, `$`, backticks,
  `*`, or `;` that either break the shell or trip the matcher's
  literal-`$` / unescaped-`*` denials.
