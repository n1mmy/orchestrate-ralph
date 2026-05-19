# Tracker-agnostic via a prose adapter; no headless driver

This package was extracted from a single project where the Ralph loop was
hardcoded — the issue tracker was local markdown under `.issues/`, the
verification gate was `pnpm`, the worker permission allowlist was JS/TS-shaped.
Two drivers existed: a headless `loop.py` (a Python `while` loop running
`claude --print` once per issue) and an interactive orchestrator that
dispatches worker sub-agents. Making the loop reusable across projects and
issue trackers forced three decisions.

## Decision

1. **Tracker-agnostic via a prose adapter.** The orchestrator and workers are
   agents; they adapt to a project's issue tracker by *reading prose* — a
   "Ralph loop" section appended to `docs/agents/issue-tracker.md` describing,
   for that tracker, how to discover / read / resolve dependencies of /
   transition / comment on issues. There are no code adapters and no `ralph`
   CLI.

2. **No headless driver.** `loop.py` is dropped. The package ships only the
   interactive orchestrator.

3. **Parallelism is gated on a tracker-readable dependency relation.** A
   worker branches off the integration tip; dispatching an issue whose
   dependency is still unmerged gives that worker no base to build on. So the
   orchestrator only runs parallel waves when the tracker exposes a dependency
   relation it can read (`parallel-safe: true` in `docs/agents/ralph.md`).
   Otherwise it runs serially.

## Alternatives considered

- **Code adapters / a `ralph` CLI** — a per-tracker module exposing
  discover/read/transition, used by both `loop.py` and the agents. Rejected:
  it implements each tracker's semantics twice (once in code, once in the
  prose the agents read anyway), and the entire engineering cost of it existed
  only to serve `loop.py`. Dropping `loop.py` removed the need.
- **Keep `loop.py` as a local-markdown-only headless path** — ship it
  un-genericised. Rejected: it leaves a permanent capability asymmetry
  (orchestrator: any tracker; `loop.py`: one) for an unattended mode that was
  not in use.

## Consequences

- Tracker-agnosticism costs no code — it is per-tracker prose. The package
  ships ready-made "Ralph loop" extensions for local-markdown, GitHub, and
  GitLab; any other tracker is described by the user during `setup-ralph`.
- Reliability of a tracker-specific operation rides on the precision of that
  prose. A vague extension section degrades quietly — there is no type system
  to catch it.
- There is no unattended mode. Running Ralph means an interactive Claude Code
  session. The OS-level guards `loop.py` had — a hard per-loop `SIGTERM`
  timeout, cross-hour rate accounting, crash-surviving disk state — are
  replaced by the orchestrator's softer, in-session equivalents (advisory
  timeout, worker self-policing, recovery-on-re-entry).
- The orchestrator leans on undocumented Claude Code harness behaviour
  (worktree isolation of every `Agent` call, `run_in_background` dropping that
  isolation). That coupling is consolidated into one "Harness assumptions"
  section of `ORCHESTRATOR.md` so a Claude Code version bump has a single place
  to check.
