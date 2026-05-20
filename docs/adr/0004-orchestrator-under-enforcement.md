# Orchestrator runs under enforced permissions, via claude restart after placement

The original model ran the orchestrator on the user's attended session — the
session that was alive when `orchestrate-ralph` was invoked, started *before*
`.claude/settings.local.json` was placed. Claude Code reads settings at
session startup only; a mid-session copy is not re-read. So the orchestrator
inherited the user's interactive defaults, not the placed allowlist /
`deny` block / `dontAsk` / path-guard hook. Workers got enforcement; the
orchestrator did not.

Five live-run commits (`b535e08`–`ba5b29f`) and the recurring "`cp`
`/abs/agent-*/.env`" / "`find /`" / "gate piped through `tail`" misbehaviours
all came from doctrine being the only thing restraining an orchestrator that
the permission matcher couldn't see. Each tightening of prose surfaced a new
variant.

A plan to fix this by spawning the orchestrator as an `Agent` subagent of
the user's session (`orchestrator-as-subagent-plan.md`) was empirically
falsified in Phase 1: subagents — under any `subagent_type` × `isolation`
combination — neither pick up the placed `.claude/settings.local.json` nor
have the `Agent` tool needed to dispatch workers. That architecture is
structurally impossible in this Claude Code version.

The actual lever is simpler: get the orchestrator's session itself enforced
by ensuring claude was launched *after* the placement.

## Decision

1. **The orchestrator runs under enforced permissions, achieved by
   restarting claude after placement.** `orchestrate-ralph` first ensures
   `.claude/settings.local.json` is on disk in the worktree (copying it
   from `.ralph/settings.json` if missing, fatal if a divergent
   pre-existing one is present), then **halts with restart instructions**:
   exit claude, re-launch from the worktree, re-run the skill. The fresh
   session loads the file at startup. From then on the orchestrator and
   workers run under the same allowlist, `deny` block, `dontAsk` default,
   and path-guard hook.

2. **`orchestrate-ralph`'s session setup is a probe-then-proceed gate, not
   a mid-session placement.** Three states: file absent → place + halt for
   restart; file present and divergent → fatal; file present and
   byte-identical → probe (one bare `cd .` `Bash` call; under enforcement
   the `Bash(cd:*)` deny catches it as a clean tool error, under an
   unenforced session `cd` is not on the user's interactive allowlist
   either so it prompts or runs depending on their settings) → proceed if
   denied cleanly, halt for restart otherwise. `cd` is chosen as the
   canary because it is the deny block's most load-bearing entry (it
   exists specifically to make `cd && git …` un-approvable), is a
   perfect no-op in Claude Code (cwd does not persist across `Bash`
   calls), and has no external dependencies.

3. **The `setup-ralph` settings template adds `Agent` to the allowlist.**
   Under `dontAsk`, an unallowlisted tool call auto-denies. The
   orchestrator must dispatch workers via the `Agent` tool, so `Agent`
   must be on the allow list or the first wave fails immediately.

4. **`ORCHESTRATOR.md` drops asymmetry hedges.** Prereq #2 collapses to
   "you and workers both run under enforcement." The "Local git only"
   section no longer says "for you it is doctrine only" — the `deny`
   block applies to the orchestrator now too. The smart-retry doctrine
   for permission-denied workers stays as-is; an orchestrator denial
   produces the same clean tool error and the same config-shaped halt
   summary.

5. **The `ORCHESTRATOR.md` "Harness assumptions" line on universal
   foreground-`Agent` isolation is corrected.** Phase 1 V1 showed
   `general-purpose` subagents without explicit `isolation` share the
   parent's cwd; `claude` and `Explore` auto-isolate. The worker dispatch
   template always sets `isolation: "worktree"` explicitly, so the loop is
   unaffected, but the assumption itself is no longer reliable to lean on.

## Alternatives considered

- **Orchestrator as an `Agent` subagent** — the original plan
  (`orchestrator-as-subagent-plan.md`). Phase 1 ran four probe variants
  (`general-purpose` × no/with isolation, `claude` × no/with isolation)
  with a fresh `.claude/settings.local.json` in place. Result: none picked
  up the deny block, `dontAsk`, or the path-guard hook, and none had
  `Agent` in their toolset. Plan rejected as structurally impossible.
- **Stronger prose doctrine alone.** Tried across multiple sessions; the
  misbehaviour class keeps re-opening with new variants. Five live-run
  commits in this branch are the evidence. Doctrine is necessary but not
  sufficient.
- **Per-tool `PreToolUse` hooks for the orchestrator.** Duplicates the
  permission system at the hook layer; the permission system already
  exists, use it.
- **Restart claude on every wave** (a finer-grained version of this ADR).
  Doesn't add enforcement beyond the once-per-run restart, but adds
  significant UX cost and a state-serialisation burden for the cross-wave
  state the orchestrator carries in-memory (consecutive-fails counter,
  recovery-on-re-entry triggers). Rejected.
- **Probe-only at SKILL entry, no restart.** Settings are loaded at
  startup; a probe cannot cause a mid-session load. Without restart, no
  enforcement.
- **Launch claude with `--permission-mode dontAsk` from the CLI.** Forces
  the user's *every* interactive session into `dontAsk`, a much worse
  general UX. The placement-and-restart pattern keeps the mode change
  scoped to the worktree.

## Consequences

- **AFK runs are meaningfully safer.** The orchestrator can no longer
  silently issue a misbehaving `Bash` call: it auto-denies as a tool
  error, the loop catches it, the run halts with a config-shaped summary
  that quotes the denied command and recommends `/setup-ralph` repair
  mode.
- **One restart of claude is required between `setup-ralph` and the first
  `orchestrate-ralph` invocation that actually runs the loop.** Small UX
  cost; the SKILL's three-state gate makes it unambiguous. Subsequent
  `setup-ralph` repair runs that change `.claude/settings.local.json`
  also require a restart for the same reason; the repair-mode prose
  carries this forward.
- **The handoff's previously-resolved "hook propagation to worker
  subagents" claim is now partially re-opened.** Phase 1 from *unenforced*
  parents could not reproduce it; the claim was for *enforced* parents
  (the model this ADR now codifies). Re-verification under the new
  configuration is owed — the strongest current evidence is the
  empirical AFK runs that motivated this ADR.
- **`ADR 0003`'s "the orchestrator runs in the user's session" framing in
  its permissions paragraph is still accurate**, just less load-bearing
  now: the orchestrator's session is *also* enforced.
- **Setup-ralph's "never write `.claude/settings.local.json`" rule
  remains.** That rule is about not polluting the user's primary
  checkout; `orchestrate-ralph` places the file in a fresh worktree, not
  the primary checkout, so it is consistent.