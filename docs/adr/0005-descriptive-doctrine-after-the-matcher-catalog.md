# Descriptive doctrine after the matcher catalog

Before the empirical catalog landed (`docs/permission-matcher-tests.md`),
worker and orchestrator doctrine was *prescriptive* and *defensive*: long
enumerations of forbidden shapes ("no `&&`, no pipes, no subshells, no full
paths, no `cd`, no `find /`, no `| tail`") inlined into every dispatch. The
doctrine was the primary defense against misbehaviour because the
orchestrator ran unenforced (pre-ADR-0004) and the matcher's actual
behaviour was inferred from incident logs rather than empirically
catalogued.

The 2026-05-20 catalog run falsified the central claim. Separator-joined
commands (`&&`, `||`, `;`, `|`, `&`) **decompose** in the matcher — each
segment is checked against allow + deny independently — so a pipe or `&&`
chain between two allowlisted commands runs. Only subshells (`$(...)`,
backticks) are a distinct unallowlisted shape. The prescriptive doctrine
was therefore *overstated*, and the cost showed up as worker
over-application: a worker reading "no `| tail`" reflexively avoided bare
`head` / `tail` for file slicing, fell back to `Read` or read whole files
into context, burning iterations on shapes that would have worked.

## Decision

1. **Doctrine becomes descriptive.** Worker and orchestrator prose
   describes how the matcher behaves — separators decompose; subshells
   deny; arg-locality gate denies paths outside cwd; first-token gate
   rejects `/`; `$VAR` references deny; explicit denies on `cd` /
   `git -C` / remote-git — and lets workers reason about novel shapes
   from that model. The format is "here is the mechanism" rather than
   "here is the list of things never to do."

2. **The optimisation target is worker efficiency, not prompt length.**
   A doctrine paragraph that is several lines longer but accurate is
   preferred over a vague paragraph that makes workers self-censor
   working shapes. The cost of doctrine bloat (tokens × dispatches) is
   small compared with the cost of a worker burning an iteration on a
   denial that doctrine could have predicted, or avoiding a shape that
   would have worked.

3. **`.ralph/settings.json` is the canonical source for the
   project-specific allow surface.** Doctrine points workers at it for
   exact gate-command shapes; doctrine itself does not enumerate them.
   The shape rules described in doctrine apply on top of whatever is in
   the file.

4. **The catalog is the canonical source for matcher behaviour.** When a
   Claude Code version bump changes matcher behaviour, the catalog gets
   re-run and doctrine is patched in the same change set. Doctrine that
   names mechanisms the catalog has not verified is dead-weight at best,
   misleading at worst.

## Consequences

- The descriptive doctrine drifts with the matcher. A future Claude Code
  version that changes matcher behaviour (e.g., starts treating `&&` as a
  distinct unallowlisted shape, or expands the safe list) invalidates the
  doctrine. The catalog procedure is designed to catch this drift;
  "Updating this doc" in the catalog points back here.
- Workers gain access to working shapes the old doctrine forbade — pipes
  between allowlisted commands, `&&` chains where both halves pass, bare
  `head` / `tail`, etc. This is the intended ergonomic win.
- Workers retain the workflow contract: "run the gate exactly as
  written," "one issue per run," "commit locally only," "no remote git."
  These are not matcher rules and stay as prose.
- `Bash(date +%s)` is dead weight in the settings template (the safe list
  runs `date` without a rule) and is removed.

## Considered alternatives

- **Conservative trim** — drop only the now-wrong bullets, keep
  prescriptive frame. Rejected: the prescriptive frame produced the
  over-application, and the doctrine would drift in the same direction
  next time the matcher changed.
- **Workflow-only doctrine** — strip command-shape doctrine entirely,
  rely on matcher errors. Rejected: workers do need a one-paragraph
  mental model so the first dispatch is productive. The wasted-iteration
  tax outweighs ~10 lines of prose.
- **Pointer-only doctrine** — replace inline doctrine with a pointer to
  the catalog. Rejected: workers see `PROMPT.md` inlined and don't have
  repo access to follow pointers usefully. The catalog stays for
  maintainers; doctrine self-contains the rules workers need.
