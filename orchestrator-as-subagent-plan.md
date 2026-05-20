# Move the orchestrator into an Agent subagent

A plan to fix the recurring class of orchestrator-misbehaviour bugs by
running the orchestrator under the same *enforced* permissions as workers,
rather than under the user's attended-session permissions.

## Problem

The doctrine in `ORCHESTRATOR.md` is prose-only for the orchestrator. Workers
run under enforced permissions (`.ralph/settings.json` →
`.claude/settings.local.json`: allowlist, `deny` block, `dontAsk`, path-guard
hook). The orchestrator runs in the user's interactive session on attended
base permissions — no `deny` block, no `dontAsk`, no path-guard. The doctrine
says "don't `cd`, don't `git push`, don't operate inside `agent-*/` worktrees,
run the gate literally"; the model still does, because nothing stops it.

Recent recurring symptom: the orchestrator runs env-bootstrap as
`cp /abs/agent-*/.env.example /abs/agent-*/.env` even after the doctrine fix
in `ba5b29f` explicitly forbade absolute paths and operating inside worker
worktrees. Fresh sessions still reproduce it. Each tightening of prose
surfaces a new variant the next run. The asymmetry between "enforced workers"
and "doctrine-only orchestrator" is the root cause.

## The fix

Spawn the orchestrator itself as an `Agent` subagent of the user's session.
It then runs under `.claude/settings.local.json` — the same enforced
permission environment as workers. Misbehaviour stops being prose-only:

- `Bash(cd:*)`, `Bash(git -C:*)`, `Bash(git push:*)` etc. become **hard
  enforcement** for the orchestrator, not just doctrine.
- Under `dontAsk`, an unallowlisted command **auto-denies** as a tool error
  the orchestrator can branch on — no more bubbling prompts to the user.
- The path-guard hook applies to the orchestrator's `Write` / `Edit` /
  `NotebookEdit` too. It can no longer write inside a worker worktree.
- Each orchestrator dispatch reads `ORCHESTRATOR.md` (and the inlined
  `PROMPT.md`) **fresh** — the "stale session has stale doctrine" failure
  mode disappears.

The architecture becomes uniform — three layers, one filesystem, one git
repo:

```
user session  →  orchestrator subagent  →  worker subsubagent(s)
(prereqs +       (no isolation; same       (isolation: "worktree";
 placement;       cwd as parent; same       its own branch + checkout;
 dispatch)        settings.local.json)      same settings.local.json)
```

## Key technical decisions

1. **No `isolation: "worktree"` for the orchestrator subagent.** Workers use
   isolation — they need their own branch and checkout. The orchestrator
   needs to operate on the integration branch *in the user's worktree*
   (that's where merges land, where the gate runs). Spawn with no isolation:
   same cwd as parent, separate permission context.

2. **One `settings.local.json` for both inner layers.** No per-layer
   permission tuning required. The current allowlist is already a superset
   (workers also use git; orchestrator also uses git/merge/worktree/gate).
   The `deny` block, `dontAsk`, and the path-guard hook apply correctly to
   both.

3. **`ORCHESTRATOR.md` logic is mostly unchanged.** The loop — discover,
   wave, dispatch, collect, merge, gate, retry, escalate, stop conditions —
   is independent of who runs it. What changes is *who reads it*: a
   subagent spawned per run, not the user's session.

4. **The user's session does only setup.** Verify prereqs, place
   settings.local.json, dispatch the orchestrator Agent, wait, print
   summary. Minimal logic in the user's session means minimal exposure to
   stale-context bugs.

## Phases

### Phase 1 — Verify the assumption (cheap, blocking)

Before touching the skill, confirm empirically that a **non-isolated**
subagent launched from the user's session *does* pick up
`.claude/settings.local.json`'s `defaultMode: "dontAsk"`, the `deny` block,
and the path-guard hook. The handoff confirms isolated subagents do; the
question is whether the non-isolated variant also does.

Tactic: a one-off `Agent` dispatch with no isolation that tries:
- a `deny`-block command (e.g. `git push` to a non-existent remote) — expect deny;
- a `Write` outside cwd (e.g. `/tmp/probe`) — expect the path-guard hook to deny;
- an unallowlisted command (e.g. `whoami`) — expect auto-deny under `dontAsk`.

If any of these doesn't enforce, the entire architecture doesn't work and
the plan dies — fall back to investigating other propagation mechanisms.

### Phase 2 — Skill restructure

`orchestrate-ralph/SKILL.md` switches from "read ORCHESTRATOR.md and *become*
the orchestrator" to dispatching the orchestrator as an Agent.

User-session `SKILL.md` responsibilities (post-change):

- Prereq checks (same as today).
- Place `.claude/settings.local.json` (same as today).
- **Dispatch a single `Agent` call** with: no isolation; a prompt that points
  the subagent at `ORCHESTRATOR.md`, inlines the integration tip / config,
  and gives it the worker dispatch template (or a pointer to `PROMPT.md`).
- Wait for return; print the summary the subagent emits.

`ORCHESTRATOR.md` changes (subset — the loop logic stays):

- Drop the "you are the user's session" framing where present.
- Drop the orchestrator-permission-model caveat — the orchestrator is now
  under enforced permissions, same as workers. Prereq #2 collapses to "you
  and workers both run under `.claude/settings.local.json`."
- Drop the "Local git only" / `deny` block "for you it is doctrine only"
  sentence — it's enforcement for the orchestrator now.
- The "permission-denied worker does not halt the loop" passage can stop
  enumerating prompt-mode vs `dontAsk` artifacts: a denial is a failure,
  full stop.

`PROMPT.md` mostly unchanged. The dispatch template the orchestrator inlines
stays the same (it still calls `Agent` + `isolation: "worktree"` for workers).

### Phase 3 — Doctrine simplification

Once Phase 2 lands, drop or rewrite the prose that existed only because the
orchestrator wasn't enforced:

- "Local git only" loses the "for you it is doctrine only" hedge.
- The "orchestrator permission model" learning in `handoff.md` becomes
  historical (a note that the asymmetry existed and was closed).
- The corrected-permission-model and Resolved-hook-propagation sections
  collapse to a single short "permissions and hooks propagate to both
  inner layers via the placed `settings.local.json`" note.
- ADR 0003's "the orchestrator runs in the user's session" framing in the
  permission section needs a small revision.

### Phase 4 — End-to-end verification

Live run against the test repo (`~/data/local/orchestrate-ralph-run-2`):

- Verify the orchestrator subagent dispatches workers correctly.
- Verify it **cannot** do the misbehaviours we keep seeing — provoke them
  via contrived inputs if needed: `cp` into `agent-*`, `find /`, env-bootstrap
  with absolute paths, gate piped through `tail`. All should hit the matcher
  or the hook and fail cleanly without reaching the user as prompts.
- Verify `watch-steps.py` still reads worker transcripts (worker is now
  nested one level deeper).
- Verify interrupt (Esc) cleanly stops the orchestrator subagent and any
  workers it has in-flight.

## Open questions to resolve during implementation

1. **Operator approval tradeoff.** Under `dontAsk` for the orchestrator,
   ad-hoc operator approval mid-run is impossible. Acceptable, or do we want
   the orchestrator subagent in `default` mode (prompts) while workers stay
   in `dontAsk`? That would require per-subagent mode selection — see if
   Claude Code's `Agent` tool supports it, else accept `dontAsk` for both.

2. **Long-lived `Agent` call.** The orchestrator may run hours across many
   waves. Verify there's no implicit `Agent` timeout that would kill it
   mid-loop.

3. **Interrupt propagation.** Confirm Esc in the user's session interrupts
   the orchestrator subagent (and through it any in-flight worker dispatch).

4. **Output observability.** `watch-steps.py` reads worker transcript paths.
   Under the new architecture worker transcripts live one `Agent` level
   deeper. Probably a minor path-resolution change.

5. **Restart story.** If the orchestrator subagent crashes mid-run, the
   user's session is still alive and can re-dispatch. Confirm that
   re-dispatch on a partially-merged integration branch is safe (the
   orchestrator already handles "recovery on re-entry" — step 1).

## Files touched

- `orchestrate-ralph/SKILL.md` — restructured (dispatch instead of *become*).
- `orchestrate-ralph/ORCHESTRATOR.md` — small revisions; drop asymmetry
  caveats.
- `orchestrate-ralph/watch-steps.py` — likely a path adjustment.
- `docs/adr/0004-orchestrator-as-subagent.md` (new) — record the
  architectural change and the rejected alternatives.
- `handoff.md` — note the change, simplify the asymmetry sections.

## Done criteria

- A fresh orchestrator run no longer exhibits the misbehaviour class
  observed in the live runs: no `cp /abs/agent-*/.env`, no `find /`, no
  `2>&1 | tail` gate, no operating inside `.../agent-*/`.
- These misbehaviours now fail at the permission matcher / path-guard hook
  rather than via prompts to the operator.
- The doctrine in `ORCHESTRATOR.md` no longer has to caveat itself with
  "for you it is doctrine only."
- A live wave-of-workers run completes successfully end-to-end on the test
  repo.

## Risks

- **Phase 1 verification fails.** If non-isolated subagents don't actually
  read `settings.local.json` (or don't apply `dontAsk` to it), this plan
  dies. Fallback: investigate `isolation: "worktree"` with a same-branch
  worktree (probably impossible — git refuses), or invest in a stronger
  doctrine-loading mechanism (e.g. always re-Read `ORCHESTRATOR.md` at
  start of each wave so stale-context is at most one wave behind).

- **Subagent-spawns-subagent capability differs from documented.** Some
  contexts (custom plugin subagents) have known restrictions on the tools
  they receive. `Agent`-tool-launched subagents should be fine but worth
  double-checking in Phase 1.

- **Long-running `Agent` semantics.** If the harness kills long `Agent`
  calls, the loop is dead. Phase 1 should include a "dispatch an Agent
  that runs for several minutes" sanity check.

- **Loss of operator agility.** Currently the operator can approve ad-hoc
  commands during a run. Under this architecture, every command the
  orchestrator might want must be allowlisted in advance. Mitigation:
  `/setup-ralph` repair mode is the path to add new entries between runs.

## Rejected alternatives (pre-decision)

- **Stronger prose doctrine.** Tried, kept failing. Five live-run commits in
  the current branch are evidence: prose is necessary but not sufficient.
- **Per-tool `PreToolUse` hooks for the orchestrator.** Would duplicate the
  permission system at the hook layer. The permission system already exists;
  use it.
- **Restart the orchestrator session before each wave.** Closes the
  stale-context window but doesn't add the deny-block enforcement. Doesn't
  fix the architectural asymmetry.
- **Run the orchestrator with `--permission-mode dontAsk` from the CLI.**
  Forces the *user's* session into `dontAsk` for the whole interactive
  experience — a much worse UX. Subagent dispatch isolates the mode to the
  orchestrator without affecting the user's session.
