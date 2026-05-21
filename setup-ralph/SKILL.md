---
name: setup-ralph
description: Scaffold or repair the per-repo configuration the Ralph orchestrator needs. A fresh run autodetects the verification gate and loop config and writes docs/agents/ralph.md plus .ralph/settings.json; a re-run diagnoses and surgically fixes an existing config from a complaint — e.g. workers prompting for permissions, or the wrong worker environment.
disable-model-invocation: true
---

# Setup Ralph

Per-repo configuration for the `orchestrate-ralph` skill. Prompt-driven, not a
deterministic script: explore, present what you found, confirm with the user,
then write.

The skill has two modes, chosen automatically by whether the config exists:

- **Fresh setup** — `docs/agents/ralph.md` and `.ralph/settings.json` do not
  yet exist. Scaffold them. Follow [Fresh setup](#fresh-setup).
- **Repair** — both already exist. Do **not** re-scaffold; that would clobber
  hand edits, which on these files are expected and supported. Diagnose and
  surgically fix what is wrong. Follow [Repair](#repair).

Any free-text argument is treated as a **complaint** — a symptom in the user's
own words ("unit tests keep prompting for permissions", "workers don't have
the right environment"). In repair mode it focuses the diagnosis; in fresh
mode there is nothing to repair yet, so acknowledge it and do a fresh setup.

## Prerequisite

Ralph reads its issue queue through the issue-tracker configuration that
`setup-matt-pocock-skills` writes. Check that `docs/agents/issue-tracker.md`
and `docs/agents/triage-labels.md` exist. If they do not, tell the user to run
`setup-matt-pocock-skills` first, and stop — do not guess the tracker.

## Fresh setup

### 1. Explore

Read the repo; don't assume.

- **The gate** — the project's verification commands. Look at `package.json`
  `scripts` (`typecheck`, `lint`, `test`, `build`), `Makefile` targets,
  `Cargo.toml`, `pyproject.toml` / `tox.ini`, and any CI workflow files.
  Assemble a candidate ordered list, cheap checks first.
- **Env bootstrap** — is there a committed env template (`.env.example`,
  `.env.sample`, a `.env.*` checked into git) that a fresh worktree must
  materialise before the gate will pass?
- **The tracker** — read `docs/agents/issue-tracker.md`. Is it local-markdown,
  GitHub, GitLab, or something else? Does it expose a dependency relation
  between issues?

### 2. Present and confirm

Walk the user through these one at a time — present, get an answer, move on:

- **Gate** — show the autodetected command list; let the user correct it.
  Order matters: a change must pass each command in turn.
- **Env bootstrap** — confirm the step in one line, or record "None".
- **Parallelism** — `parallel-safe` is true only if the tracker exposes a
  dependency relation the orchestrator can read (an issue's `Blocked by`, or
  the equivalent). Confirm from the tracker type; when unsure, default false —
  the orchestrator then runs serially, which is always correct.
- **Worker permission mode** — how a worker handles an unallowlisted command.
  Default **`dontAsk`** (recommended for AFK / parallel-wave runs): the
  command auto-denies as a tool error the worker can branch on — a missing
  allowlist entry becomes a clean failure the loop handles instead of a
  stalled prompt. The alternative **`default`** prompts your interactive
  session — better when you are actively watching a single-issue run and want
  to approve ad-hoc commands on the fly. Either way, the gate, env-bootstrap,
  and tracker commands still need allow entries (above and below); mode only
  changes what happens for everything *else*. Present both, default `dontAsk`.
- **Tracker writes** — note (no user choice here, just an FYI) that the
  orchestrator handles every tracker write itself since ADR 0006, so
  `.ralph/settings.json` will gain the tracker's read **and** write verbs
  (e.g. `gh issue edit`, `gh issue comment` for GitHub). The exact set is
  derived from the tracker detected in step 1 and shown in the
  `.ralph/settings.json` preview before writing. Workers under doctrine
  call only the read verbs; the shared allow list grants both because the
  file is shared (ADR 0004).

### 3. Write

- **`docs/agents/ralph.md`** — from [templates/ralph.md](./templates/ralph.md),
  filled in with the answers from step 2.
- **`.ralph/settings.json`** — from
  [templates/settings.template.json](./templates/settings.template.json), with
  three groups of additions:

  1. **One allow entry per distinct gate command**. Each as the **whole
     command** as a `:*` prefix — `Bash(pnpm typecheck:*)`,
     `Bash(bash check.sh:*)`, `Bash(cp .env.example .env:*)` — never just
     its first token. `Bash(bash *)` or `Bash(pnpm *)` would let a worker
     run `bash -c '<anything>'` or `pnpm dlx <anything>`: arbitrary code,
     not the gate.
  2. **One entry for the env-bootstrap command** (step 2), if there is one —
     every worker runs that bootstrap in its own worktree under this
     allowlist, so it needs an entry just like a gate command. The
     orchestrator also runs the bootstrap; one shared `.ralph/settings.json`
     applies to both since ADR 0004.
  3. **Tracker verbs** — per ADR 0006, the orchestrator handles every
     tracker write itself, so `.ralph/settings.json` needs the verbs for
     **both** worker-side reads and orchestrator-side writes. Pick the
     block matching the tracker chosen in step 2:

     - **local-markdown** — no extra entries. Reads use `Read`; writes use
       `Edit` + `Bash(git:*)` (committing the transition commit on the
       integration branch). All four are already in the template.
     - **GitHub** — add `Bash(gh issue list:*)` (orchestrator discover),
       `Bash(gh issue view:*)` (worker + orchestrator read),
       `Bash(gh issue edit:*)` (orchestrator transition),
       `Bash(gh issue comment:*)` (orchestrator comment).
     - **GitLab** — add `Bash(glab issue list:*)`,
       `Bash(glab issue view:*)`, `Bash(glab issue update:*)`,
       `Bash(glab issue note:*)`.
     - **Other** — write the four verbs (discover, read, transition,
       comment) the tracker's CLI uses, each as a whole-command `:*`
       prefix. The split between worker-read and orchestrator-write
       still applies as doctrine; the allow list grants both because the
       file is shared.

  Set `permissions.defaultMode` to the choice from step 2 (default
  `dontAsk`). Show the user the final file before writing.
- **`.ralph/hook-path-guard.py`** — copy
  [templates/hook-path-guard.py](./templates/hook-path-guard.py) verbatim. It
  is the `PreToolUse` path-guard hook that `.ralph/settings.json` references —
  it denies a worker writing outside its worktree. It has one knob,
  `EXTRA_ALLOWED_ROOTS` (a list of extra writable paths, empty by default);
  leave it empty at fresh setup — widening it is a repair-time concern. The
  file must be committed, so it is present in every worker's worktree checkout.
- **`docs/agents/issue-tracker.md`** — append a `## Ralph loop` section using
  the matching fragment: [local-markdown](./templates/issue-tracker-local.md),
  [GitHub](./templates/issue-tracker-github.md), or
  [GitLab](./templates/issue-tracker-gitlab.md). For any other tracker, write
  the section from scratch with the user, covering all six operations:
  discover, read, dependencies, feature grouping, transition, comment.
- **The `## Agent skills` block** in `CLAUDE.md` / `AGENTS.md` (whichever
  `setup-matt-pocock-skills` already edited) — add a `### Ralph loop` line:
  "Loop config and worker permissions. See `docs/agents/ralph.md`."

**Never write `.claude/settings.local.json`.** That is the user's own file;
its broad worker allowlist would leak into their everyday sessions. The
`orchestrate-ralph` skill places `.ralph/settings.json` there at run time in a
fresh worktree — and treats a pre-existing, differing `settings.local.json` as
a fatal "checkout not clean enough" error.

**Templates are user-repo content.** Every file under
`setup-ralph/templates/` lands in the user's repo, verbatim or with the
per-tracker tailoring above — the tracker fragments append to
`docs/agents/issue-tracker.md`, `hook-path-guard.py` becomes
`.ralph/hook-path-guard.py`, `ralph.md` becomes `docs/agents/ralph.md`,
`settings.template.json` becomes `.ralph/settings.json`. Treat any template
edit like a customer-facing doc edit:

- **No relative cross-references into the orchestrate-ralph package.** A
  `[ADR 0006](../adr/...)` link in a template resolves to a path the
  user's repo does not have. The same goes for any `./` or `../` path
  into `setup-ralph/` or `orchestrate-ralph/`.
- **No skill-internal step numbers** (`step 8`, `step 9 E/F`). They
  point at `ORCHESTRATOR.md` sections the user cannot see from their
  copy. Use phase names instead (*"after the wave is merged and the
  gate is green"*) — those carry meaning without a cross-reference.
- **No worker/orchestrator role split in operation-level templates.**
  The tracker fragment describes *operations*; who calls each is package
  doctrine and lives in `PROMPT.md` / `ORCHESTRATOR.md`.

The dividing line is whether the file gets copied at setup time. Files
that stay in the `setup-ralph/` package — `SKILL.md`,
`repair-symptoms.md`, this paragraph itself — may cite ADRs and step
numbers freely. A grep for `step [0-9]` or `adr/` over `templates/` is
a quick smoke test before committing template changes.

### 4. Done

Tell the user setup is complete, and suggest they **commit the scaffolded
files** — `docs/agents/ralph.md`, `.ralph/settings.json`,
`.ralph/hook-path-guard.py`, and the edits to `docs/agents/issue-tracker.md`
and `CLAUDE.md` / `AGENTS.md`. `orchestrate-ralph` runs in a fresh git
worktree, which only sees committed files; uncommitted scaffolding would be
absent there and the run would fail its prerequisite check.

They can edit `docs/agents/ralph.md` and the other scaffolded files by hand
later; a re-run of this skill does not start over — it enters [Repair](#repair)
and fixes the config in place.

## Repair

`docs/agents/ralph.md` and `.ralph/settings.json` already exist. The config is
in place but something is wrong with it — or it predates a template fix.
**Never re-scaffold:** hand edits to these files are expected and supported.
Work surgically, and **prompt the user often** — repair is fiddly, and the
user usually holds details that pin the diagnosis.

### 1. Gather evidence

A complaint ("tests keep prompting for permissions") is only a *router* — it
rarely names the actual defect, which usually has several distinct candidate
causes. Pull concrete evidence before changing anything:

- the exact permission-prompt or error string, quoted;
- the failing worker's `## Comments` note in its issue;
- the `orchestrate-ralph` stop message — on a config-shaped halt it quotes the
  denied command string verbatim.

Ask the user for whatever you cannot find yourself. Do not proceed on a guess;
if the evidence is thin, keep asking.

### 2. Diagnose

Map the evidence to a specific config defect using
[repair-symptoms.md](./repair-symptoms.md) — it lists, per symptom, the likely
causes, the evidence that distinguishes them, and the fix shape. A re-run with
**no complaint** is a full re-audit: walk every artifact against the current
templates and surface each divergence.

### 3. Fix — surgically

- Make the **minimal `Edit`** to the existing file. Never re-render a template
  over it.
- Show the user a before/after for every change; apply only on confirm.
- If a file diverges from the current template **outside** the defect you are
  fixing, do not assume — surface it ("this differs from the current scaffold;
  deliberate, or stale?") and let the user decide.
- `.ralph/hook-path-guard.py` — be cautious here, and ask the user before any
  change. Its one knob is `EXTRA_ALLOWED_ROOTS`: edit that list to widen what
  a worker may write to (e.g. a shared data directory). Do **not** edit the
  guard logic below it.
- There is no rollback to build: every edit lands in the working tree, the
  user reviews the diff, and commits or reverts. Remind them that a change to
  `.ralph/hook-path-guard.py` reaches workers only once committed — a fresh
  worktree checks out committed state.

### 4. Verify

You cannot dispatch a worker, so you cannot reproduce a permission prompt.
Verify what you can:

- **Static shape check** — confirm an allowlist fix is the whole-command `:*`
  prefix (not a first-token grant), and that it matches the exact gate
  command string in `docs/agents/ralph.md`. If the gate string itself contains
  a subshell, an absolute path outside the worktree, an unexpanded `$VAR`, or
  a full-path invocation, no allow entry will rescue it — the gate must be
  rewritten.
- **Run the real command** — run the gate command yourself in the checkout to
  capture its exact invocation, and to catch a test runner that shells out to
  a second, unallowlisted binary.

Tell the user the honest limit: this proves the config is now correct, **not**
that the next run will pass — only an `orchestrate-ralph` run proves that.
