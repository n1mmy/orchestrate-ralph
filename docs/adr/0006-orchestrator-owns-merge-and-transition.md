# Orchestrator owns merge, gate, and tracker writes

Before this change, each worker drove its own issue through the tracker: on
success, the worker flipped the issue's label to `done` (or edited the
issue file's `Status:` line) as part of the same commit that landed its
code; on infeasible, the worker flipped to `needs-info`; on transient
failure, the worker commented on the issue and left it at
`ready-for-agent`. The orchestrator merged the worker's branch into the
integration tip after the worker reported `done`.

That sequencing has the worker write the *transition* before the
orchestrator does the *merge*. If the merge then fails (sibling-conflict,
post-merge gate red, anything), the issue reads `done` while the work is
not on integration. The next round's discovery — gated on
`ready-for-agent` / `Status: ready-for-agent` — silently skips the issue.
The tracker and the repo diverge with no signal. Workers also need
tracker-write permissions (for GitHub: `Bash(gh issue edit:*)` plus
`Bash(gh issue comment:*)`); for in-band trackers like local-markdown,
the worker's comment commit lives on a branch that is then thrown away on
round-fail, so the comment never reaches integration without orchestrator
help anyway.

## Decision

1. **Worker writes nothing to the tracker.** Worker reads the issue,
   implements, runs the gate on its own branch, commits the code (on
   success only — failure paths do not commit), and reports an outcome
   `{ outcome: done | failed | needs-info, reasonText?: string }` back to
   the orchestrator. By doctrine, the worker calls only read verbs
   (`gh issue view` for GitHub; `Read` on the file for local-markdown).
   The allowlist itself is shared between worker and orchestrator
   (per ADR 0004) — the worker/orchestrator split is prose discipline,
   not permission enforcement. A misbehaving worker that calls
   `gh issue edit` would succeed, but it would also visibly violate
   explicit doctrine and surface in the issue's comment thread.

2. **The orchestrator owns every tracker write.** Labels, status fields,
   comments — all written by the orchestrator post-wave, regardless of
   tracker type. For out-of-band trackers (GitHub, GitLab) this is API
   calls; for in-band (local-markdown) this is file edits + commits on
   integration. The doctrine is uniform; the implementation surface
   varies per tracker.

3. **`needs-info` and merge-conflict are handled per-issue, independent
   of round outcome.** A worker reporting `needs-info` causes the
   orchestrator to flip that one issue to `needs-info` regardless of any
   later gate result — the verdict is purely about issue shape, not
   about integration. A worker reporting `done` whose branch then
   conflicts with a sibling causes the orchestrator to comment on that
   issue and leave it at `ready-for-agent`, again regardless of round
   outcome. Only the merged-tip gate is round-level.

4. **The orchestrator runs the gate once per round, on the merged tip.**
   After all `done`-reporting workers' branches have been merged in (with
   per-issue conflict-skip from #3), the orchestrator runs the project
   gate exactly once. The merged subset that passes is what counts as
   the "round-pass" cohort.

5. **`done` is written iff the merged-tip gate is green for a merged
   subset containing the issue.** Per-issue ordering: `merge → gate →
   label`. The label is a true signal of "this work is integrated and
   the result gates green," not an optimistic worker self-report.

6. **On merged-tip gate failure, the orchestrator attempts recovery
   before re-dispatching.** A failing round converts into bounded
   progress rather than total loss. The recovery flow:

   ```
   A. Merged tip gate red. Note pre-wave tip; git reset --hard <pre-wave-tip>.
   B. For each merged-set branch B_i: gate B_i alone in a temp worktree.
      - Green: B_i is a survivor.
      - Red:   "post-hoc gate fail on isolation re-run" — comment on
               B_i's issue, boot from this round, leave at ready-for-agent.
   C. If survivors is empty: round-fail-no-progress. Booted-issue
      comments are the record; no further action this round.
   D. Survivors is non-empty AND any branch was booted at B: re-merge
      survivors, gate.
      - Green: label all survivors `done`. Round passes.
      - Red:   proceed to E.
      (If nothing was booted at B, skip D — the merged state would be
      identical to A's failing state.)
   E. Leave-one-out across survivors. For each B_i in survivors:
      - Merge the (|survivors|-1)-subset excluding B_i. Gate.
      - If green: label that subset `done`. Comment on B_i's issue
        ("passed alone but breaks the wave; retry next round").
        Round passes.
   F. If no (|survivors|-1)-subset passed: singleton fallback. Pick one
      survivor (lowest issue number is fine), merge it alone, **gate
      it**, label `done` if green. Comment on every other survivor's
      issue ("passed alone but breaks the wave with siblings X"). Round
      passes with 1 issue done.
   ```

   Every step that labels follows the same `merge → gate → label`
   ordering (Decision #5). F repeats the gate even though step B
   already verified the singleton alone — a final sanity check on the
   exact integration-tip state being labelled, and consistency with
   the rest of the algorithm. If F's gate goes red (a flake, or
   environment drift between B and F), the round makes no progress;
   no label is written.

   Recovery does **not** explore subset sizes between 1 and S-1. If
   leave-one-out fails to find a green (S-1)-subset, the orchestrator
   jumps straight to a singleton; it does not try (S-2)-subsets,
   (S-3)-subsets, etc.

7. **Recovery is bounded at O(N) gate runs per failing round.** The
   orchestrator does not bisect; it does per-branch verify, one pass of
   leave-one-out, then singleton fallback. Upper bound per recovery:
   2N + 3 gate runs (initial + per-branch verify + re-merge after boots
   + leave-one-out + singleton). Deeper subset search is rejected on
   wall-time grounds.

## Consequences

- **Worker behavioural surface shrinks; allowlist is unchanged.** The
  allow set in `.ralph/settings.json` is shared between worker and
  orchestrator (per ADR 0004), so the split is enforced by doctrine,
  not by permission grants. A worker that violates the doctrine and
  calls `gh issue edit` would succeed — and would also show up as a
  visible misbehaviour in the issue's tracker state. The protection is
  "loud-if-broken," not "denied-by-default."

- **`done` becomes a high-trust signal.** Operators reading the tracker
  can rely on `done` meaning "this work is on the integration tip and
  the gate was green when the label was written" — not "a worker
  thought it succeeded." The repo and tracker state stay in sync.

- **The orchestrator gains a substantial post-wave phase.** `ORCHESTRATOR.md`
  needs a new section covering: per-outcome dispatch handling, the
  merge step, the round-level gate, the transition phase, and the
  recovery flow.

- **`setup-ralph` must add tracker-specific allow entries to
  `.ralph/settings.json`.** Today's flow only handles gate + env-bootstrap
  commands. With the orchestrator now calling `gh issue list/view/edit/
  comment` (or the local-markdown equivalents) and the file being shared
  between worker and orchestrator, `setup-ralph` reads the chosen tracker
  and merges the matching allow fragment into the settings file. This is
  a separate pending change; see "Considered alternatives" #5.

- **Round wall-time on the success path is unchanged.** The orchestrator
  already gated post-merge under the previous model; the round-level gate
  is the same single run, just newly authoritative. On the recovery path,
  up to 2N additional gate runs for a wave of size N. Per-merge gating
  (which would multiply this) is rejected in the alternatives.

- **Worker reports become the orchestrator's source of truth for what
  happened in the wave.** Comments and labels are derived from those
  reports. If the orchestrator crashes between report-collection and
  tracker-write, the worker's report is lost; next round redispatches the
  same worker who regenerates an equivalent report. Comment text may
  vary slightly between attempts (different model sampling), but the
  outcome class converges. No persistent state is added to track
  in-flight reports — the recovery is automatic via re-dispatch.

- **For in-band trackers, issue-file edits cluster onto integration as
  separate commits.** The orchestrator's post-wave phase writes one
  commit per `needs-info` transition and one per merge-success. Could be
  batched into one commit per round to reduce history noise; left as a
  separate decision.

- **Workers can no longer cheat the label by self-reporting success.**
  Their `done` report is advisory; the orchestrator's merge-and-gate is
  what produces the label. A worker that lies about gate success gets
  caught at the merged-tip gate or the per-branch verify step.

## Considered alternatives

- **Worker-side label writes (the pre-existing model).** Rejected: causes
  the `done`-but-not-merged divergence described in the preamble. The
  worker has no view of the orchestrator's merge step; writing the label
  before the merge is verified is a false signal that the tracker then
  keeps as canonical state.

- **Asymmetric writes — worker writes failure comments for out-of-band
  trackers, orchestrator writes for in-band.** Rejected: splits doctrine
  into per-tracker branches in PROMPT.md (the worker would behave
  differently per tracker type, despite the allowlist being shared
  either way), and the only win — comment durability across orchestrator
  crashes — is small because comments are regenerated on next round's
  re-dispatch.

- **Per-merge gate (gate after every individual branch merge).**
  Rejected: gating after every merge is `N × gate-runtime` per wave; for
  a non-trivial gate this dominates wall-time. The round-level gate
  amortises the cost, and recovery localises blame only when the merged
  state actually fails — which is the rare path.

- **Halt-after-N-consecutive-round-fails.** Rejected: throws away
  progress instead of converting partial-success into completed work.
  The recovery flow makes at least 1 issue's worth of progress per round
  if any worker survived per-branch verify, which dominates the
  bounded-loss model in expected throughput.

- **`setup-ralph` writes tracker-specific allow entries inline at fresh
  setup, no fragments.** Considered but not finalised here — left as a
  follow-up to this ADR. The current `setup-ralph` flow asks about
  gate + env-bootstrap commands but does not add tracker verbs to the
  allow list, so the GitHub path silently misses `Bash(gh issue ...:*)`
  entries today. Either a per-tracker fragment file or an inline
  set-of-rules at template-write time is needed; the choice is downstream
  of this decision and does not change it.

- **Recursive subset bisection in recovery.** Rejected: 2^N gate runs in
  the worst case is incompatible with any reasonable per-round
  wall-time budget. Leave-one-out + singleton fallback is the bounded
  approximation: it finds either "everyone except one" or "the best
  single survivor" in O(N) gate runs.
