# Plan — split orchestrate-ralph into single + parallel skills

Implements [ADR 0007](../docs/adr/0007-single-worker-default-two-skill-split.md).

## Touch list

| File | Action |
|---|---|
| `orchestrate-ralph/ORCHESTRATOR.md` | Rewrite for single-worker; aggressive pruning |
| `orchestrate-ralph/SKILL.md` | Update description; point at `/orchestrate-ralph-parallel` |
| `orchestrate-ralph/PROMPT.md` | No change |
| `orchestrate-ralph-parallel/ORCHESTRATOR.md` | New: verbatim copy of *current* `orchestrate-ralph/ORCHESTRATOR.md` |
| `orchestrate-ralph-parallel/SKILL.md` | New: parallel-specific description + `parallel-safe` prerequisite + `N` argument |
| `orchestrate-ralph-parallel/PROMPT.md` | Relative symlink → `../orchestrate-ralph/PROMPT.md` |
| `setup-ralph/templates/ralph.md` | Reframe `## Parallelism` as a capability declaration; pointer to parallel skill |
| `setup-ralph/SKILL.md` | Light edit where `orchestrate-ralph` is referenced |
| `CONTEXT.md` | Replace "Wave vs. round" with "Wave (parallel skill only) vs. round"; add a "Single mode vs. parallel mode" section naming both skills and pointing at ADR 0007 |
| `README.md` | Update "Two skills" → "Three skills" (with cleanup-ralph from the separate plan); reframe parallel as opt-in |
| `docs/adr/0007-...md` | The ADR itself (already written) |

## Order

1. **ADR 0007** — already written; lands as its own commit.
2. **Create `orchestrate-ralph-parallel/`** as a verbatim copy of current `orchestrate-ralph/` (ORCHESTRATOR.md + SKILL.md). `PROMPT.md` becomes a relative symlink. Verify the parallel skill works as-is — at this point nothing else has changed and the existing `parallel-safe: true` flow goes through it.
   - Then apply **one surgical edit** to `orchestrate-ralph-parallel/ORCHESTRATOR.md` for ADR 0007 Decision #6: at end of step 10 (after the wave summary), add a paragraph that iterates the wave's workers and runs `git branch -D <branch>` per dispatched worker. One bare `Bash` call per branch (no `&&` chain — preserves per-step output). Place this *after* step 9's recovery has fully resolved, so survivor and boot branch refs were available throughout recovery.
3. **Rewrite `orchestrate-ralph/ORCHESTRATOR.md`** for single-worker. See "Pruning detail" below.
4. **Update `orchestrate-ralph/SKILL.md`:**
   - Description: "Run a Ralph loop as an interactive orchestrator that dispatches **one** worker sub-agent per round to grind a project's issue tracker to done. Use when asked to 'orchestrate ralph,' run the Ralph loop, or drive the issue tracker with sub-agents."
   - Add a one-line "For parallel mode (multi-worker waves), see `/orchestrate-ralph-parallel`."
   - Prerequisite checks and session-setup section are unchanged (those are shared mechanics).
5. **Tune `orchestrate-ralph-parallel/SKILL.md`:**
   - Description: "Run a Ralph loop in parallel-wave mode (multiple worker sub-agents per round). Use when the project has `parallel-safe: true` in `docs/agents/ralph.md` and you have judged this issue set to be parallel-safe. For the canonical (one worker per round) loop, see `/orchestrate-ralph`."
   - Add prerequisite #3: "**The repo declares itself parallel-safe.** `docs/agents/ralph.md` must contain `parallel-safe: true`. If absent or false, stop and tell the user that this repo's tracker doesn't expose a dependency relation suitable for parallel waves; run `/orchestrate-ralph` instead."
   - Accept optional `N` argument (default `5`). Pass it to the orchestrator doctrine as `MAX_PARALLEL`.
6. **Update `setup-ralph/templates/ralph.md` `## Parallelism` section:**
   - Keep `parallel-safe: false` as the template default.
   - Reframe the comment: "Set `true` only if the issue tracker exposes a dependency relation the orchestrator can read — see the 'Ralph loop' section of `docs/agents/issue-tracker.md`. This is a **capability declaration** required by `/orchestrate-ralph-parallel`; `/orchestrate-ralph` (single-worker, the canonical loop) ignores this flag."
7. **Light edit `setup-ralph/SKILL.md`:** references to `orchestrate-ralph` that talk about parallel waves should clarify the split. The repair-symptom catalog probably doesn't need changes.
8. **Update `CONTEXT.md`:**
   - "Wave vs. round" → "Wave (parallel skill only) vs. round." Wave vocabulary survives only in the parallel skill.
   - Add a one-paragraph "Single mode vs. parallel mode" section naming the two skills and pointing at ADR 0007.
9. **Update `README.md`:** "Two skills" → "Three skills" (including cleanup-ralph if its plan has shipped), reframe parallel as opt-in, point at ADR 0007.

## Pruning detail — `orchestrate-ralph/ORCHESTRATOR.md`

What to remove or collapse:

- **Configuration §:** Drop the `MAX_PARALLEL` entry and the `parallel-safe` reference inside it. Keep `WORKER_TIMEOUT`, `RETRY_BUDGET`, `MAX_CONSECUTIVE_FAILS`.
- **Step 1 (Recover an interrupted wave first):** Reword as "Recover an interrupted round first." The mechanics (look for an unfinished dispatch, reset to pre-round tip, etc.) are unchanged, just singular.
- **Step 2 (Pick the wave):** Rename to "Pick the next issue." Drop the wave-fill loop and the "spread across distinct features" rule. Keep eligibility (every dependency `done`). Record the integration tip as **pre-round tip**, plus the round start time and the pre-round untracked-files baseline. If no issue is eligible but `ready-for-agent` remain, halt as today.
- **Step 3 (Dispatch the wave):** Rename to "Dispatch the worker (foreground, one call)." Drop "all of them in a single message." The background-dispatch warning stays (the harness still drops isolation on background, and the worker would then run on integration — still broken at N=1). The foreground-suspension paragraph simplifies to "the call suspends you until the worker returns."
- **Step 4 (While the wave runs):** Rename to "While the worker runs." Plurals → singular. `WORKER_TIMEOUT` advisory note stays as-is.
- **Step 5 (Escape checks, then collect outcomes):** Plurals → singular. Both escape checks (committed + untracked) stay. Outcome reading collapses to one outcome, not a list. Reclassification rules unchanged.
- **Step 6 (Merge `done`-reporting workers' branches):** Rename to "Merge the worker's branch if it reported done." **Delete** the merge-ordering paragraph (no siblings to order). **Delete** the sibling-conflict paragraph (the worker reset to the integration tip → merge is fast-forward by construction). The untracked-escape collision case stays (escape vector exists at N=1). Worktree reaping stays — `git worktree unlock` then `git worktree remove --force`.
- **Step 7 (Gate the merged tip):** "Merged tip" → "post-merge integration tip" (one branch on it). Gate runs **once**. Green → step 8. Red → step 8's recovery branch (folded in below).
- **Step 8 (Transition):** Per-outcome table simplifies: drop the `merge-conflict` row (impossible at N=1). Add a new row for the red-gate case (formerly handled in step 9): "`done`, in the merged set, step-7 gate **red** → `git reset --hard <pre-round-tip>`; comment 'post-hoc gate fail on integration re-run'; leave at `ready-for-agent`; counts toward retry budget."
- **Step 9 (Recover):** **Delete entirely.** Its content is one outcome-class row in step 8.
- **Step 10 (Wave summary):** Rename to "Round summary." "Per worker" → "the worker" (singular). Wall time, worker outcome, `<usage>` block. Escalation handling unchanged. **Add end-of-round branch cleanup:** after the summary is printed, run `git branch -D <branch>` for the worker dispatched this round. Single bare `Bash` call. The branch's commit (if any) is reachable via the integration merge commit on the green path; on the red path the commit is unreachable but lives in the reflog for 90 days. Per ADR 0007 Decision #6.
- **Stop conditions:** **Delete "Systemic wave failure"** (no wave to fail systemically; `MAX_CONSECUTIVE_FAILS` absorbs the signal). Keep the rest.
- **Harness assumptions §:** Trim the background-dispatch bullet's "parallel workers would collide on one branch" tail — leave only the matter-of-fact "background dispatch silently drops isolation; the worker would then run on the integration branch." Keep the foreground-suspension bullet but simplify "every worker in the dispatching message" → "the worker."
- **Dispatch template:** Plurals → singular wherever they appear ("each worker" → "the worker"). The template body otherwise unchanged.
- **Merge and gate procedures:** Unchanged.

## Validation

- **Diff** `orchestrate-ralph/ORCHESTRATOR.md` against `orchestrate-ralph-parallel/ORCHESTRATOR.md`. Every difference should be either an N=1 collapse or a removal of parallel-only content. No accidental drift in shared sections (harness assumptions, prerequisites, session setup, permission matcher, gate / merge procedures, stop conditions).
- **Grep** the single-skill ORCHESTRATOR.md cold and confirm none of these strings appear: `wave`, `parallel`, `MAX_PARALLEL`, `merged set`, `survivor`, `leave-one-out`, `singleton`.
- After a smoke run of `/orchestrate-ralph`, confirm `git branch | grep worktree-` is **empty** at end-of-round on the success path, and also empty on a deliberately-broken (red-gate) round. Confirm the failing round's worker commit is still recoverable via `git reflog`.
- After a smoke run of `/orchestrate-ralph-parallel 2`, confirm the same — both worker branches gone at end-of-round regardless of outcome (merged, conflict, failed, booted).
- Confirm `orchestrate-ralph-parallel/PROMPT.md` resolves to `orchestrate-ralph/PROMPT.md` from the install location (`~/.claude/skills/`) and from this worktree (where the install symlink points to the worktree copies).
- Smoke-run `/orchestrate-ralph` on a small issue set; confirm a successful round end-to-end with no wave vocabulary surfacing.
- Smoke-run `/orchestrate-ralph-parallel 2` on the same set with `parallel-safe: true` (set it temporarily). Confirm the prerequisite check passes and the existing wave loop runs.
- Smoke-run `/orchestrate-ralph-parallel` against a repo with `parallel-safe: false`. Confirm the prerequisite halt fires cleanly with the right pointer to `/orchestrate-ralph`.

## Open follow-ups not in this plan

- The handoff's pending live-verification items (step-6 merge ordering, step-9 recovery branches) continue to apply to the **parallel** skill specifically. They are not affected by this split; the parallel skill's `ORCHESTRATOR.md` is a verbatim copy.
- A `setup-ralph` round that prompts the user "this repo has `parallel-safe: false` — is that still right, or would you like to declare it parallel-safe?" could land later but is not blocked by this plan.
