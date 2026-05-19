# Ralph loop configuration

Project-specific configuration for the Ralph orchestrator (the
`orchestrate-ralph` skill). Written by `setup-ralph`; edit by hand any time.

The orchestrator and its workers read this file at the start of every run.

## Verification gate

The ordered list of commands every change must pass. A worker runs the gate
before committing; the orchestrator re-runs it on the integration branch after
each wave. Every command must exit zero. Order matters — cheap checks first.

```
<gate command 1, e.g. pnpm typecheck>
<gate command 2, e.g. pnpm lint>
<gate command 3, e.g. pnpm test>
<gate command 4, e.g. pnpm build>
```

## Integration base branch

`main`

## Env bootstrap

None.

<!-- If a fresh worktree needs a step before the gate will pass — e.g.
materialising a gitignored `.env` from a committed `.env.example` — describe
that one step here, and delete the "None." line above. The worker performs it
first thing; the orchestrator performs it before the gate. -->

## Parallelism

`parallel-safe: false`

Set `true` only if the issue tracker exposes a dependency relation the
orchestrator can read — see the "Ralph loop" section of
`docs/agents/issue-tracker.md`. When `false`, the orchestrator runs serially
(`MAX_PARALLEL = 1`) regardless of any other configuration: parallel waves are
unsafe without a dependency graph, because a worker dispatched against an
unmerged dependency has no base to build on.

## Protected paths

Never modified by a worker or the orchestrator:

- `.ralph/` — the orchestrator's worker settings.
- `docs/agents/ralph.md` — this file.
