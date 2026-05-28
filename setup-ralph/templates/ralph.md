# Ralph loop configuration

Project-specific configuration for the Ralph orchestrator (the
`orchestrate-ralph` skill). Written by `setup-ralph`; edit by hand any time.

The orchestrator and its workers read this file at the start of every run.

## Verification gate

The ordered list of commands every change must pass. A worker runs the gate
before committing; the orchestrator re-runs it on the integration branch after
each round. Every command must exit zero. Order matters — cheap checks first.

```
<gate command 1, e.g. pnpm typecheck>
<gate command 2, e.g. pnpm lint>
<gate command 3, e.g. pnpm test>
<gate command 4, e.g. pnpm build>
```

## Env bootstrap

None.

<!-- If a fresh worktree needs a step before the gate will pass — e.g.
materialising a gitignored `.env` from a committed `.env.example` — describe
that one step here, and delete the "None." line above. The worker performs it
first thing; the orchestrator performs it before the gate. -->

## Parallelism

`parallel-safe: false`

This is a **capability declaration**: set `true` only if the issue tracker
exposes a dependency relation that the orchestrator can read — see the
"Ralph loop" section of `docs/agents/issue-tracker.md`. Without that
relation, parallel waves are unsafe (a worker dispatched against an unmerged
dependency has no base to build on).

The single-worker `/orchestrate-ralph` skill (the canonical loop) ignores
this flag entirely — it dispatches one worker per round and is always
correct.

The `/orchestrate-ralph-parallel` skill requires this flag to be `true` and
halts otherwise; flip the flag only when you have judged the tracker's
dependency relation correct and want to opt into parallel-wave mode.

## Protected paths

Never modified by a worker or the orchestrator:

- `.ralph/` — the orchestrator's worker settings.
- `docs/agents/ralph.md` — this file.
