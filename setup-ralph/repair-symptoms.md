# Repair symptom catalog

Reference for `setup-ralph` [Repair](./SKILL.md#repair) mode. Each entry maps a
symptom to its candidate causes, the evidence that tells them apart, and the
fix shape. The complaint only points you at an entry — the evidence picks the
cause. When evidence is missing, ask the user; do not guess down the list.

The four config artifacts a repair may touch: `docs/agents/ralph.md`,
`.ralph/settings.json`, `.ralph/hook-path-guard.py`, and the `## Ralph loop`
section of `docs/agents/issue-tracker.md`.

---

## A worker or the orchestrator is denied on a command

*"unit tests keep prompting for permissions", "the worker stalled on a gate
command", "the worker fails on a command I think should run", "the
orchestrator can't transition the issue", "the orchestrator was denied on
`gh issue edit`"*

The whole class is a **shape mismatch** between an allow entry in
`.ralph/settings.json` (= the placed `.claude/settings.local.json`) and the
command actually called. Both the worker and the orchestrator run under that
same file, so either side can hit the denial; under
`permissions.defaultMode: dontAsk` (the default) the denial is a clean tool
error, under `default` it prompts the session running. Either way the
underlying fix is the same — get the exact denied command string first,
from the prompt, the worker's failure-class comment, or the
`orchestrate-ralph` stop message.

Candidate causes, distinguished by comparing that string to `settings.json`:

| Cause | Evidence | Fix |
|---|---|---|
| Command not allowlisted at all | no `allow` entry matches the command's first token | Add `Bash(<whole command>:*)`. |
| Allowlisted with the wrong shape | entry is a first-token grant (`Bash(pnpm:*)`) but policy wants the whole command, or vice versa | Rewrite the entry as the **whole gate command** as a `:*` prefix. |
| Worker command ≠ gate command | the worker ran `pnpm test --filter x`; `ralph.md` / the entry say `pnpm test` | Reconcile: fix `ralph.md`'s gate line, or broaden the entry to the shape actually run. |
| Subshell or path-locality denial | the string has `$(...)` / backticks, or contains an absolute path outside the worktree, or an unexpanded shell metachar (`$VAR`, unescaped `*` — even `\$` denies because the matcher reads raw text), or a first token containing `/` | These are matcher-level shape denials no allow entry can rescue; rewrite the command in `ralph.md` to avoid the shape. |
| Separator chain with an unallowlisted segment | the string has `&&` / `\|` / `;` / `\|\|` chaining commands, and at least one segment is unallowlisted | The matcher decomposes separators and checks each segment, so the denial is on the segment, not on the chain itself. Allowlist the segment, or rewrite the gate command to use only allowlisted ones. |
| Test runner shells out | the gate command passes, but it spawns a second binary (`node`, `docker`, `tsx`) that is what got denied | Allowlist the spawned binary too. Running the gate command yourself surfaces this. |
| **Tracker-write verb not allowlisted** | the *orchestrator* is denied on `gh issue edit` / `glab issue update` / `gh issue comment` / `glab issue note` — the verbs it uses to transition issues and write recovery comments | Add the matching tracker verb to `allow` as a whole-command `:*` prefix. See `setup-ralph` [SKILL.md](./SKILL.md#3-write)'s "Tracker verbs" group for the per-tracker list. A re-run of `setup-ralph` does this automatically. |
| **Tracker-read verb not allowlisted** | the *worker* is denied on `gh issue view` / `glab issue view` reading its issue at dispatch time | Same fix — add the read verb to `allow`. The verb is part of the per-tracker group in `setup-ralph`'s template; if it is missing, the settings file predates that template. |

Verify: the new entry is a whole-command `:*` prefix, not a first-token grant,
and matches the gate / tracker string exactly. If the gate string itself
contains a subshell / outside-cwd path / shell metachar (`$VAR`, `*`,
even `\$`) / full path, no allow entry will rescue it — the gate must
be rewritten.

---

## Workers don't have the right environment

*"workers don't have the right environment", "the gate fails on a fresh
worktree but passes for me"*

A worker runs in an isolated worktree that checks out **committed files only** —
anything gitignored (a `.env`, a built artifact, a local cache) is absent
unless the worker recreates it.

| Cause | Evidence | Fix |
|---|---|---|
| No env-bootstrap step recorded | `ralph.md` has no bootstrap step; the gate needs gitignored files | Add the bootstrap step to `ralph.md` (e.g. `cp .env.example .env`). |
| Bootstrap step incomplete | a step exists but the gate still fails for a missing file | Extend the step to materialise everything the gate needs. |
| Env files exist but were never committed | the template (`.env.example`) is itself gitignored, so there is nothing for the worker to copy *from* | The source template must be committed; tell the user. A worktree cannot bootstrap from a file it cannot see. |
| Bootstrap step needs an unallowlisted command | the bootstrap command itself is denied | Allowlist it in `settings.json` (see the shape-mismatch entry above). |

---

## A worker is denied writing a path it legitimately needs

*"the worker can't write to our shared data directory"*

The path-guard hook denies any `Write`/`Edit`/`NotebookEdit` resolving outside
the worker's worktree. A legitimate write outside it — a shared data directory
the app uses — needs the path explicitly allowed.

- **Fix:** add the absolute path to `EXTRA_ALLOWED_ROOTS` near the top of
  `.ralph/hook-path-guard.py`. Edit only that list; never the guard logic.
- The change reaches workers only once **committed** — a fresh worktree checks
  out committed state.
- If the user instead wants the guard fully off (a throwaway container, "don't
  care"), the right move is removing the `hooks` block from `settings.json`,
  not editing the script. Confirm that is really what they want — it disables
  worktree-escape protection for every worker.

---

## The run halts with "write-guard hook inactive"

The per-worker self-test found the path-guard hook is not enforcing. This is a
*propagation* failure, not a config-value defect.

| Cause | Evidence | Fix |
|---|---|---|
| Hook script not committed | `.ralph/hook-path-guard.py` is untracked or uncommitted | Commit it — a worker worktree only sees committed files. |
| `settings.json` does not wire the hook | no `hooks.PreToolUse` block, or it points at the wrong path | Restore the `hooks` block from the template, pointing at `$CLAUDE_PROJECT_DIR/.ralph/hook-path-guard.py`. |
| Settings not reaching the worker subagent | hook and wiring are both correct | This is harness behaviour, not a config defect — surface it to the user; `setup-ralph` cannot fix it. |

---

## Parallel waves conflict / the loop is slower than expected

| Cause | Evidence | Fix |
|---|---|---|
| `parallel-safe: true` but no real dependency relation | workers collide because issues that depend on each other ran in one wave | Set `parallel-safe: false` in `ralph.md` — the loop runs serially, which is always correct. |
| `parallel-safe: false` but the tracker *does* expose dependencies | the loop runs serially and slowly though `Blocked by` is available | Set `parallel-safe: true` after confirming the tracker's dependency relation is readable. |

---

## Switch the worker permission mode

*"workers keep interrupting me to approve commands", "workers fail silently
and I'd rather they ask"*

A user preference, not a defect. `.ralph/settings.json`'s
`permissions.defaultMode` controls what a worker does on a command not in the
allow list: `dontAsk` (the default) auto-denies as a tool error the worker
can branch on — best for AFK and parallel-wave runs; `default` prompts the
operator's session — better when actively babysitting a single-issue run.

| Symptom | Fix |
|---|---|
| Operator wants fewer interruptions | Set `permissions.defaultMode` to `"dontAsk"`. |
| Operator wants to approve ad-hoc commands on the fly | Set `permissions.defaultMode` to `"default"`. |

Either way, the gate and env-bootstrap commands still need explicit allow
entries — `defaultMode` only changes the *fallback* behaviour.

---

## Adding a new symptom

When a repair turns up a failure mode not listed here, add an entry: symptom in
the user's likely words, candidate causes, the evidence that separates them,
and the fix shape. Keep it a lookup table — diagnosis logic stays in
`SKILL.md`.
