# Plan — split orchestrate-ralph into single + parallel skills

Implements
[ADR 0007](../docs/adr/0007-single-worker-default-two-skill-split.md);
that ADR receives two amendments noted at the end. Supersedes the
earlier `plan-serial-split.md` (commit 2950c01). Should be deleted
when this plan ships.

`plans/cleanup-ralph-skill.md` is unaffected — it sits alongside this
one, on its own timeline.

## Spine

The mechanical bet:

- **Single-worker is the canonical Ralph loop.** Doctrine reads as a
  single-worker loop end-to-end; "wave," "MAX_PARALLEL," "merged set,"
  "survivor" do not appear in the single skill's ORCHESTRATOR.md.
- **Worker still runs in `isolation: "worktree"` at N=1.** This is an
  integrity property, not a maintenance choice. The worker's branch
  tip is the **only** channel through which work crosses to the
  orchestrator; the worker physically cannot leave edited-but-uncommitted
  or written-but-not-`git add`-ed files in the integration worktree to
  silently colour the orchestrator's re-gate. The committed tip is the
  truth. (See "Re-gate rationale" below.)
- **Worker resets to integration tip before working** → merge step
  survives as a trivial fast-forward; cannot conflict by construction.
- **End-of-round `git branch -D`** for every dispatched worker, in both
  skills. Reflog retains commits 90d. Asymmetric with `cleanup-ralph`'s
  `-d` on purpose (orchestrator has full outcome context; cleanup-ralph
  doesn't).
- **`PROMPT.md` is identical across both skills** (same reset, root-pin,
  hook self-test, report shape) — see "PROMPT.md sharing" below.

## Re-gate rationale (amendment to ADR 0007)

The orchestrator re-gates on the post-worker tip even though the worker
already gated locally. Four independent vectors motivate this:

1. **Working-tree residue.** A worker that edited a file but committed
   only a subset would leave the gate green against a dirty tree.
   Worktree isolation closes this vector at the boundary — but the
   re-gate is what *verifies* the boundary held.
2. **Allowlist gaps.** The worker may have had a permission the
   orchestrator's enforced settings revoke; the re-gate runs under the
   orchestrator's settings.
3. **A wrapper the worker silently dropped.** If gate doctrine
   prescribes `script/check` and the worker ran the bare tool, the
   re-gate (using the prescribed wrapper) catches it.
4. **Flake masked at worker stage.** A test that passed once for the
   worker is run again from a clean tip.

Recovery on red is `git reset --hard <pre-worker-tip>`; the round made
no progress and the issue stays at `ready-for-agent` (counts toward
retry budget).

ADR 0007 should absorb this rationale (currently the ADR folds red-gate
into the step-8 outcome row without explaining why re-gate exists at
all).

## PROMPT.md sharing — source symlink, install-time copy is fine

The source repo keeps `orchestrate-ralph-parallel/PROMPT.md` as a
relative symlink to `../orchestrate-ralph/PROMPT.md`. This is purely
dev-time DRY for the maintainer (edit once).

At install time, the relationship doesn't matter. Whether the installer
preserves the symlink (dev `~/.claude/skills/` symlink workflow) or
flattens it into two physical copies (zip extract, naive `cp`, Windows
target without symlink support), both skills resolve their PROMPT.md
locally and run. No partial-install hazard, no `cp -a` requirement, no
prerequisite-check workaround needed.

Doctrine is N-invariant, so the two installed copies (or the one
symlinked file) carry the same content for the same reason — there is
nothing to drift toward.

## Drift-detection — recurring maintenance procedure

Single-skill ORCHESTRATOR.md is **authoritative for shared mechanics**
(prerequisites, session setup, gate procedure, transition, stop
conditions, protected files, local-git-only, harness assumptions,
permission matcher). Parallel-skill ORCHESTRATOR.md's matching sections
must track.

Before any release, run:

1. `diff orchestrate-ralph/ORCHESTRATOR.md orchestrate-ralph-parallel/ORCHESTRATOR.md`.
   Every difference must be **either** an N>1-specific construct
   (wave, MAX_PARALLEL, step-9 recovery, merge ordering) **or** a
   knowing N-shape collapse. Anything else is drift in shared
   mechanics → reconcile by editing the parallel copy to track the
   single copy.
2. `diff orchestrate-ralph/SKILL.md orchestrate-ralph-parallel/SKILL.md`.
   Same rule — only differences should be the description, the
   `parallel-safe` prerequisite (parallel-only), and the `N` argument
   (parallel-only).
3. The existing handoff grep smoke test (`\.\./docs|docs/adr/|step [0-9]`)
   continues to run over both folders.

Document this procedure in the maintainer's resync section.

## parallel SKILL.md description

Neutral, not redirective. The user reached the parallel skill by
explicitly invoking it — leading with "default to the serial variant"
talks down to them.

> "Run a Ralph loop in parallel-wave mode (multiple worker sub-agents
> per round). Requires `parallel-safe: true` in `docs/agents/ralph.md`.
> For the single-worker (canonical) loop, see `/orchestrate-ralph`."

The prerequisite check + the `parallel-safe` halt message do the
discoverability work; the description doesn't need to.

## `parallel-safe` default — `false` (capability declaration)

`setup-ralph` writes `parallel-safe: false` by default; the template
comment explains it as a *capability declaration* the user affirmatively
claims when their tracker exposes a dependency relation the
orchestrator can read. The single skill ignores the flag entirely; the
parallel skill requires it true.

(Rejects the earlier `plan-serial-split.md` proposal of `true`-by-default
with a comment-to-flip-false — that framing is coherent only under a
"hard-veto" reading of the flag, which ADR 0007's capability framing
replaces.)

## Touch list

| File | Action |
|---|---|
| `orchestrate-ralph/ORCHESTRATOR.md` | Rewrite for single-worker; aggressive pruning |
| `orchestrate-ralph/SKILL.md` | Update description; one-line pointer at `/orchestrate-ralph-parallel` |
| `orchestrate-ralph/PROMPT.md` | No change (canonical worker body) |
| `orchestrate-ralph-parallel/ORCHESTRATOR.md` | New: verbatim copy of *current* `orchestrate-ralph/ORCHESTRATOR.md`, plus end-of-round `git branch -D` edit |
| `orchestrate-ralph-parallel/SKILL.md` | New: neutral description (above), `parallel-safe` prerequisite, optional `N` argument |
| `orchestrate-ralph-parallel/PROMPT.md` | Relative symlink → `../orchestrate-ralph/PROMPT.md` |
| `setup-ralph/templates/ralph.md` | `## Parallelism` reframed as capability declaration; default `false`; pointer to parallel skill |
| `setup-ralph/SKILL.md` | Light edit where `orchestrate-ralph` is referenced |
| `CONTEXT.md` | "Wave vs. round" → "Wave (parallel skill only) vs. round"; add "Single mode vs. parallel mode" section |
| `README.md` | "Two skills" → "Three skills" (with `cleanup-ralph`); reframe parallel as opt-in |
| `docs/adr/0007-...md` | Amend with re-gate rationale (above) and the "install-time copy is fine" clarification |

## Order

1. **Amend ADR 0007** with the re-gate rationale and PROMPT.md
   install-time clarification. Lands as its own commit.
2. **Create `orchestrate-ralph-parallel/`** as a verbatim copy of
   current `orchestrate-ralph/` (ORCHESTRATOR.md + SKILL.md). Source
   `PROMPT.md` becomes a relative symlink. Verify the parallel skill
   still works as-is via the existing `parallel-safe: true` flow.
   - Then apply **one surgical edit** to
     `orchestrate-ralph-parallel/ORCHESTRATOR.md` for Decision #6:
     at end of step 10 (after the wave summary), add a paragraph
     that iterates the wave's workers and runs `git branch -D <branch>`
     per dispatched worker. One bare `Bash` per branch (no `&&`
     chain — preserves per-step output). Place this *after* step 9's
     recovery so survivor/boot branch refs were available throughout
     recovery.
3. **Rewrite `orchestrate-ralph/ORCHESTRATOR.md`** for single-worker.
   See "Pruning detail" below — single-skill is authoritative for
   shared mechanics, so the rewrite is also the source of truth for
   the parallel skill's subsequent drift reconciliation.
4. **Update `orchestrate-ralph/SKILL.md`** — description per ADR 0007
   plus one-line pointer at the parallel sibling.
5. **Tune `orchestrate-ralph-parallel/SKILL.md`** — neutral description
   (above), `parallel-safe: true` prerequisite check, optional `N`
   argument (default 5).
6. **Update `setup-ralph/templates/ralph.md` `## Parallelism`** — keep
   `parallel-safe: false` as default; reframe comment as capability
   declaration; point at parallel skill.
7. **Light edit `setup-ralph/SKILL.md`** where parallel waves are
   referenced.
8. **Update `CONTEXT.md`** per touch list.
9. **Update `README.md`** per touch list.
10. **Run drift-detection diff smoke tests** end-to-end; reconcile
    anything that isn't a knowing N-shape difference.

## Pruning detail

`orchestrate-ralph/ORCHESTRATOR.md`, edit by edit:

- **Configuration §:** Drop `MAX_PARALLEL` and `parallel-safe` references; keep `WORKER_TIMEOUT`, `RETRY_BUDGET`, `MAX_CONSECUTIVE_FAILS`.
- **Step 1:** "wave" → "round."
- **Step 2 (Pick the next issue):** drop wave-fill loop and "spread across distinct features"; keep eligibility; record pre-round tip, start time, untracked baseline.
- **Step 3 (Dispatch the worker, foreground, one call):** drop "all in a single message"; background-dispatch warning stays; foreground-suspension simplifies.
- **Step 4 (While the worker runs):** plurals → singular.
- **Step 5 (Escape checks, then collect outcome):** plurals → singular; both escape checks stay; reclassification rules unchanged.
- **Step 6 (Merge the worker's branch if it reported done):** delete merge-ordering paragraph; delete sibling-conflict paragraph (worker reset to integration tip → FF by construction); untracked-escape collision case stays; worktree reaping stays.
- **Step 7 (Gate the post-merge tip):** gate runs once; green → step 8; red → step 8's recovery row.
- **Step 8 (Transition):** drop `merge-conflict` outcome row; add red-gate row (`git reset --hard <pre-round-tip>`; comment 'post-hoc gate fail on integration re-run'; leave at `ready-for-agent`; counts toward retry budget).
- **Step 9:** delete entirely (folded into step 8).
- **Step 10 (Round summary):** singular throughout; **add end-of-round `git branch -D <branch>`** for the dispatched worker, one bare `Bash` call.
- **Stop conditions:** delete "Systemic wave failure"; keep the rest.
- **Harness assumptions §:** trim background-dispatch bullet's parallel tail; simplify foreground-suspension bullet.
- **Dispatch template:** plurals → singular.
- **Merge and gate procedures:** unchanged.

## Validation

- **Drift-detection diffs** per the procedure above. No accidental drift in shared sections.
- **Grep cold** single-skill ORCHESTRATOR.md for `wave`, `parallel`, `MAX_PARALLEL`, `merged set`, `survivor`, `leave-one-out`, `singleton` — all must be absent.
- **Smoke-run `/orchestrate-ralph`** on a small fresh-from-zero app's backlog (same conditions that motivated the redesign — conflict-heavy issue set). Confirm: worker dispatch, re-gate (red and green paths), transition, retry, `needs-info` escalation, stop conditions all behave; `git branch | grep worktree-` is **empty** at end-of-round on success **and** on a deliberately-broken red-gate round; the failing round's worker commit is still recoverable via `git reflog`.
- **Smoke-run `/orchestrate-ralph-parallel 2`** on the same set with `parallel-safe: true` temporarily set. Confirm the existing wave loop runs and both worker branches are gone at end-of-round regardless of outcome.
- **Smoke-run `/orchestrate-ralph-parallel`** against a repo with `parallel-safe: false`. Confirm the prerequisite halt fires cleanly with the right pointer to `/orchestrate-ralph`.
- **Install-shape check:** verify the parallel skill works both (a) when installed via the dev symlink workflow (symlink preserved) and (b) when installed as two physical copies (e.g., `cp -L` or fresh `cp` of both directories). Both should resolve PROMPT.md and run.

## Open follow-ups not in this plan

- The handoff's pending live-verification items (step-6 merge ordering, step-9 recovery branches) continue to apply to the **parallel** skill specifically. They are not affected by this split.
- A `setup-ralph` round that prompts the user "this repo has `parallel-safe: false` — is that still right?" could land later.
- `plans/cleanup-ralph-skill.md` ships on its own timeline; this plan does not block it and is not blocked by it.
