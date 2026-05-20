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
A round contains exactly one wave; they share a clock.

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