# orchestrate-ralph — domain language

The Ralph loop runs across **two** agent layers, sharing one filesystem and
one git repository.

## Two-layer architecture

- **Orchestrator** — the user's interactive claude session, launched in the
  integration worktree *after* `.claude/settings.local.json` was placed.
  Claude Code loads settings at session startup, so this session runs under
  the **enforced permission environment**: the allowlist, the remote-git
  `deny` block, `dontAsk` default mode, and the path-guard hook. The
  session reads `ORCHESTRATOR.md` and "becomes" the orchestrator,
  dispatching workers wave by wave until a stop condition fires.

- **Worker** — a foreground `Agent` subagent spawned by the orchestrator
  with `isolation: "worktree"`, one per issue per wave. Each worker runs
  in its own throwaway git worktree on its own branch and inherits the
  orchestrator's enforced permissions one nesting level deeper.

An earlier design considered a three-layer architecture (user session →
orchestrator subagent → worker subsubagent) to put the orchestrator under
the same enforced permissions as workers. Phase 1 probes empirically
falsified the propagation that design relied on — see ADR 0004 and
`orchestrator-as-subagent-plan.md`. The two-layer model with **restart after
placement** achieves the same enforcement without the architectural cost.

## Wave vs. round

`ORCHESTRATOR.md` uses **wave** (the set of workers dispatched together)
and **round** (one full step-1-to-step-8 pass) almost interchangeably.
A round contains exactly one wave; they share a clock. A round has a
sequence of phases (see "Round phases" below); the wave is the first
two phases (dispatch + collect).

## Round phases

A round runs in order: **dispatch** → **collect** → **merge** → **gate** →
**transition** → (**recover** if gate red). The orchestrator owns every
phase from merge onwards; workers only participate in dispatch and
collect.

- **Dispatch** — orchestrator discovers eligible issues per the tracker,
  spawns one worker per issue with `isolation: "worktree"`.
- **Collect** — orchestrator awaits worker outcomes:
  `{ outcome: done | failed | needs-info, reasonText?: string }`.
  Workers do not write to the tracker; their report is the only output.
- **Merge** — orchestrator attempts a git merge of each `done`-reporting
  worker's branch into the integration tip. Conflicts are per-issue
  failures (comment + leave at `ready-for-agent`), not round failures.
- **Gate** — orchestrator runs the project gate **once** on the
  post-merge integration tip. This is the only gate the orchestrator
  runs in the normal path.
- **Transition** — on gate green, the merged subset's issues are
  labelled `done`; per-issue `needs-info` and `failed` outcomes from
  collect get their respective writes (or no-op). Comments are written
  here too — failure-reason text from worker reports, conflict notes
  from merge, recovery breadcrumbs from recover.
- **Recover** — runs only when the merge-tip gate goes red. The
  orchestrator reverts to the pre-wave tip, re-gates each merged branch
  alone, **boots** any whose individual gate now fails, then re-tries
  the merge with **survivors** (the branches that passed the per-branch
  re-gate). If the survivor-merge still fails the gate, one pass of
  leave-one-out tries each (S-1)-subset; if none pass, a singleton
  fallback merges one survivor, gates that merge, and labels on green —
  typically making at least one issue's worth of progress per round
  (a flake or environment drift at the singleton gate can still
  produce a no-progress round). No subset sizes between 1 and S-1 are
  explored. Every label-writing step follows `merge → gate → label`.
  See ADR 0006 for the full algorithm.

## Write authority

- **Worker reads only.** Workers `Read` the issue (via `gh issue view`
  for out-of-band trackers, or `Read` on the file for in-band) and
  `Write` only repo files (not tracker files). Worker output is the
  outcome report returned to the orchestrator; by doctrine the worker
  never flips a label, posts a comment, or edits an issue file.
- **Orchestrator owns all tracker writes.** Labels, status fields,
  comments — every write that changes the tracker's state happens in
  the orchestrator's transition phase, post-merge and post-gate. The
  implementation surface differs per tracker (API calls for GitHub /
  GitLab; file edits + commits for local-markdown), but the authority
  is uniform.

The allowlist in `.claude/settings.local.json` is shared between worker
and orchestrator (per ADR 0004); the split above is prose discipline,
not permission enforcement. Both can technically call any verb the file
allows (e.g. `gh issue edit` for GitHub); doctrine constrains the
worker to read verbs only. See ADR 0006.

## Permission environments

- **Enforced** — the runtime state of a session that loaded
  `.claude/settings.local.json` (= `.ralph/settings.json`) at startup.
  Allowlist applies, `deny` block applies, `dontAsk` auto-denies
  unallowlisted calls as clean tool errors, path-guard hook blocks
  writes outside the worktree. The orchestrator session, and every
  worker spawned from it, runs in this state.
- **Unenforced** — the runtime state of a session that started without
  `.claude/settings.local.json` on disk (the user's normal interactive
  session, the `setup-ralph` session). Interactive defaults apply;
  unallowlisted calls prompt the operator. This is *fine* for setup
  workflows and dangerous for AFK runs — hence the restart-after-
  placement rule before `orchestrate-ralph` runs the loop.

The transition from unenforced (where setup happens) to enforced (where
the loop runs) is a claude **restart**: the user exits the unenforced
session, re-launches in the same worktree, and the new session loads
`.claude/settings.local.json` at startup.

## Matcher

The **Bash permission matcher** is the runtime gate that decides allow /
deny on each `Bash` call under enforcement. Its behaviour is undocumented
by Claude Code and is empirically catalogued in
[`docs/permission-matcher-tests.md`](docs/permission-matcher-tests.md);
doctrine is descriptive of that catalog (see
[ADR 0005](docs/adr/0005-descriptive-doctrine-after-the-matcher-catalog.md)).

## Path placement

- `.ralph/settings.json` — committed to the repo by `setup-ralph`. Source
  of truth for the enforcement template.
- `.claude/settings.local.json` — placed in a fresh git worktree at
  orchestration time by `orchestrate-ralph` (copied from
  `.ralph/settings.json`). Gitignored. The primary checkout's
  `.claude/settings.local.json` is *not* written by either skill — that
  file, if it exists, is the user's interactive allow/deny list and
  must never be touched.