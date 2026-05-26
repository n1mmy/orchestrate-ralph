# CLAUDE.md — orchestrate-ralph

Guidance for any agent working *on* this repo (the skills package
itself). For the domain language of what the package *does*, read
`CONTEXT.md`.

## Package layout

Four sibling skill folders, each a self-contained skill installed via
symlink into `~/.claude/skills/`:

- `setup-ralph/` — scaffolds `.ralph/`, `docs/agents/`, etc. into a
  user repo. `setup-ralph/templates/*` is appended verbatim into the
  user's tree.
- `orchestrate-ralph/` — canonical single-worker loop. One worker per
  round; merge is fast-forward by construction.
- `orchestrate-ralph-parallel/` — opt-in N>1 wave dispatch with
  merge-ordering and a leave-one-out recovery flow.
- `cleanup-ralph/` — reaps stale `.claude/worktrees/*`.

Supporting trees:

- `docs/adr/` — architectural decisions (numbered 0001+). Read these
  before reopening a settled question.
- `docs/permission-matcher-tests.md` — empirical Bash permission-matcher
  catalog.
- `docs/subagent-permission-tests.md` — permission-propagation
  methodology under different parent enforcement states.
- `plans/` — active implementation plans. `plans/old/` is where landed
  plans go.

## Stay in your assigned worktree

When invoked inside a `.claude/worktrees/<id>` checkout, do all work
— `git` commands included — from within it. Two reasons:

- **Permissions.** The worktree's allowlist covers paths inside the
  worktree. `cd`-ing out to the primary checkout (or any sibling
  worktree) trips permission prompts that slow interactive workflow.
- **Blast radius.** Other checkouts may have uncommitted work or be
  driven by other live sessions. Writes or commits made from this
  agent into another checkout corrupt that work; the worktree you
  were given is the only tree you own.

The worktree has full `git` access on its own branch — there is no
`git` operation you need to leave it for.

## Files see only their own landing folder

Three landings, one rule: a file may only cross-reference paths that
will exist at its destination.

- `setup-ralph/templates/*` lands in the *user's* repo. Anything inside
  must read as the user's own documentation — no references to this
  package's `docs/adr/`, `docs/permission-matcher-tests.md`, etc.
- `setup-ralph/*` and `orchestrate-ralph*/*` ship into
  `~/.claude/skills/<skill>/`. The skill folder only; the repo's
  `docs/` tree does *not* ship.
- `PROMPT.md` is inlined verbatim into the worker's dispatch prompt;
  the reader sees neither the skill folder nor this repo.

Practical consequences:

- No relative paths into `docs/adr/`, `docs/permission-matcher-tests.md`,
  or other repo-root docs from any of the three landings.
- No cross-file step numbers — `step 8 (transition)` from one file
  pointing at an ORCHESTRATOR.md section is a dead reference across
  the skill boundary.
- Same-folder links (`./templates/ralph.md`, `./SKILL.md#3-write`) are
  fine.

Smoke test before committing template/skill changes:
`grep -rE '\.\./docs|docs/adr/|step [0-9]'` over `setup-ralph/`,
`orchestrate-ralph/`, `orchestrate-ralph-parallel/`, and
`setup-ralph/templates/`. The only legitimate matches are inside the
rule itself naming the forbidden patterns.

## No autopsies in doctrine

When tightening doctrine to fix a worker misbehaviour or a template
bug, the **fix** belongs in the doctrine, but the **autopsy** does
not. A reader who didn't make the mistake doesn't need the example;
the rule plus *type* of violation is enough. Autopsies belong in
commit messages and ADRs — runtime doctrine should read
as if it had always been that way.

Signals of an autopsy creeping in: bullets starting "No X" followed by
the specific X that broke, or parentheticals citing the ADR / commit /
past incident that motivated the rule.

## Doctrine optimises for worker efficiency, not prompt length

Prompt tokens are cheap compared with the tokens and wall-time a
worker burns flailing against rules it didn't know about.
Longer-but-accurate beats terse-but-misleading. Do not trim doctrine
purely to shrink the prompt.

## Doctrine is descriptive of the matcher, not prescriptive

Bash permission-matcher behaviour is undocumented and shifts with
Claude Code versions. `docs/permission-matcher-tests.md` is the
empirical source of truth; ADR 0005 is the descriptive-vs-prescriptive
frame shift. When changing permission doctrine, anchor in observed
matcher behaviour, and re-run the catalog after Claude Code version
bumps.

## `settings.local.json` is the user's, not stale scaffolding

`.claude/settings.local.json` in a user repo is their valuable
allow/deny list. The loop never touches it automatically. On a
differing pre-existing file the loop either errors out (substantial
file → run in a fresh worktree) or halts with a *suggestion* the user
can take or leave (small auto-scaffolded file). Never call it stale;
never offer to remove it.

## The integration branch is a runtime property

It is the branch of whatever worktree the orchestrator is launched
in. It is *not* setup config; it must not be recorded in
`docs/agents/ralph.md` or any other persisted config.



- `CONTEXT.md` — domain language (orchestrator/worker, round/wave,
  enforced/unenforced, write authority, path placement).
- `docs/adr/` — settled architectural questions.
- `docs/permission-matcher-tests.md` — empirical matcher catalog.
- `README.md` — user-facing intro to the package.
