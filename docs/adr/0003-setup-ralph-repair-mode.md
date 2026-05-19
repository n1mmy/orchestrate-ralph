# setup-ralph repairs an existing config instead of re-scaffolding

`setup-ralph` was one-time, write-once scaffolding: a re-run re-rendered the
templates and clobbered the result, hand edits included. But a Ralph config
goes wrong in ordinary ways after setup — a gate command that prompts for
permissions because its allowlist entry has the wrong shape, a worker that
lacks a gitignored env file, a path-guard hook that denies a legitimate shared
directory — and a config can also fall behind a template fix. The user has no
config in their head; they have a *symptom* ("unit tests keep prompting for
permissions"). The fix-up they need is diagnosis and a surgical edit, not a
re-scaffold.

## Decision

1. **Two modes, chosen by config presence.** If `docs/agents/ralph.md` and
   `.ralph/settings.json` exist, `setup-ralph` enters **repair** mode and never
   re-scaffolds — hand edits to those files are expected and supported. If they
   are absent, it does a fresh scaffold as before. A free-text argument is a
   *complaint* that focuses repair-mode diagnosis; a bare repair re-run is a
   full re-audit against the current templates.

2. **Repair is evidence-driven and conversational.** The complaint only routes
   to a symptom; the actual defect is picked from concrete evidence — the exact
   permission-prompt string, a worker's `## Comments` failure note, the
   `orchestrate-ralph` stop message. A bundled `repair-symptoms.md` catalog
   maps symptom → candidate causes → distinguishing evidence → fix shape. The
   skill prompts the user often and does not act on a guess.

3. **Fixes are surgical.** Repair makes the minimal `Edit` to the existing
   file, shows a before/after, and applies on confirm — never re-renders a
   template. A divergence from the current template *outside* the diagnosed
   defect is raised as a question, not auto-resolved. There is no rollback
   mechanism: every edit lands in the working tree and the user commits or
   reverts.

4. **The path-guard hook gets a data knob.** `hook-path-guard.py` gains
   `EXTRA_ALLOWED_ROOTS`, a list of extra writable absolute paths, empty by
   default. Loosening the guard is now a one-line data edit routed through the
   same vetted boundary check — not a hand-edit of security-critical logic.

5. **`orchestrate-ralph` points at the repair.** On a config-shaped stop
   condition the orchestrator's summary recommends `/setup-ralph` and quotes
   the exact denied command string, so the repair run starts from ground truth.
   Code-shaped failures get no such recommendation.

## Alternatives considered

- **Three-way template reconcile.** Render what the current template would
  produce, diff against the file, classify every hunk as hand-edit or drift.
  Rejected: on a hand-tuned `ralph.md` it generates noisy "divergences" that
  are all intentional, and it is far heavier than the surgical-edit-plus-ask
  approach, which folds drift repair into the same conversation.
- **A separate `fix-ralph` skill.** Rejected: repair shares mode detection and
  the artifact knowledge with fresh setup, and the user's mental model is
  "`/setup-ralph <what's wrong>`". One skill, two modes.
- **Verbatim-only hook, hand-edit to loosen it.** Rejected: editing the guard
  *logic* risks reintroducing a prefix-match bug in fail-open security code,
  and turns every future hook template fix into a logic merge conflict. A
  data-only knob in the template keeps the logic byte-identical so fixes apply
  cleanly.
- **A probe worker to verify a fix.** Rejected: heavyweight, leans on the
  still-imperfect settings-propagation behaviour, and pulls `setup-ralph` into
  `orchestrate-ralph`'s job. Repair verifies statically (fix shape) and by
  running the real gate command — and tells the user the honest limit: it
  proves the config is correct, not that the next run passes.

## Consequences

- A re-run of `setup-ralph` no longer means "start over." Restarting from
  scratch now means deleting the config files first.
- Repair cannot reproduce a permission prompt — it runs in the user's session,
  not a worker's. It verifies the config is *correct*; only an
  `orchestrate-ralph` run proves the next loop passes.
- The symptom catalog is a living lookup table. New failure modes are added to
  `repair-symptoms.md`; diagnosis logic stays in `SKILL.md`.
- A customized `EXTRA_ALLOWED_ROOTS` widens the worker write boundary. It is
  matched with the same `+ os.sep` care as the worktree root, and reaches
  workers only once committed.
