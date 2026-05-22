# Subagent permission propagation — test methodology

How to verify, from any orchestrate-ralph session, which permission
restrictions a Claude Code subagent actually inherits from a placed
`.claude/settings.local.json`. The answer drives the orchestrate-ralph
architecture: an unenforced orchestrator + enforced workers means doctrine
alone restrains the orchestrator, which has failed repeatedly; an enforced
orchestrator (ADR 0004) means the permission matcher does.

These tests have been *load-bearing* — running them in a previous session
falsified the orchestrator-as-subagent plan (see "Rejected variants"
below). Re-run them when:

- A Claude Code version bump changes harness behaviour and you want to
  catch propagation regressions.
- A new architecture variant ("what if the orchestrator runs as X") is
  being weighed and you need empirical evidence before committing.

ADR 0004's previously-open item ("worker hook propagation under
enforced parents has not been re-verified end-to-end") is closed as
of 2026-05-22 — see "Resolved 2026-05-22" further down.

## Setup — scaffolding the probe environment

Each test runs in a directory with two files:

- `.claude/settings.local.json` — copied from
  `setup-ralph/templates/settings.template.json`. Contains the allowlist,
  the `deny` block, `defaultMode: "dontAsk"`, and a `PreToolUse` hook on
  `Write|Edit|NotebookEdit` that points to `.ralph/hook-path-guard.py`.
- `.ralph/hook-path-guard.py` — copied from
  `setup-ralph/templates/hook-path-guard.py`. Denies any `Write`/`Edit`/
  `NotebookEdit` whose target resolves outside the worktree root, with a
  branded `"Path-guard: …"` message.

```bash
mkdir -p .claude .ralph
cp setup-ralph/templates/settings.template.json .claude/settings.local.json
cp setup-ralph/templates/hook-path-guard.py    .ralph/hook-path-guard.py
```

Clean up afterwards: `rm -rf .claude .ralph`.

## The five standard probes

Every scenario runs the same five probes inside the layer being tested.
Each probe has a single expected outcome under enforcement, and a single
fallback under non-enforcement.

| Probe | Call | Under enforcement | Under non-enforcement |
|---|---|---|---|
| **P1** — `deny` block | `Bash` `git remote -v` (or `cd .`) | clean tool error ("Denied by permissions"), **no prompt** | command runs and returns data |
| **P2** — path-guard hook | `Write` `/tmp/probe-<sha>.txt` content `probe` | clean tool error with `"Path-guard: …"` branded message | succeeds silently, or prompts the user (if `/tmp` writes aren't in user's interactive allowlist) |
| **P3** — `dontAsk` auto-deny | `Bash` `whoami` (or any unallowlisted command) | clean tool error, **no prompt** | succeeds silently, or prompts the user |
| **P4** — `Agent` tool availability | invoke `Agent` with any `subagent_type` and a trivial prompt | call succeeds | call succeeds (parent's tool inventory) |
| **P5** — tool inventory + cwd | report which tools are available; report `cwd` via `Bash pwd` | reports inventory + isolation cwd | reports inventory + parent's cwd (or isolation cwd, depending on type) |

**Distinguishing a tool error from a user-denied prompt is critical.**
A prompt that the user denies looks superficially like an enforced deny,
but means the *opposite* — enforcement is not in effect, the system fell
back to asking the operator. The probe must record the path: clean
tool-error → enforced; prompt-then-denied → not enforced. The
`"Path-guard: …"` branded message in P2 is the strongest single signal
that the hook actually fired.

## Scenarios

### 1. Happy path — user session under enforcement (ADR 0004, current model)

The architecture the loop ships with. Set up:

1. In a fresh git worktree (no pre-existing `.claude/settings.local.json`):
   - Place `.claude/settings.local.json` from `.ralph/settings.json`
     (`orchestrate-ralph` does this).
   - Place `.ralph/hook-path-guard.py` (committed by `setup-ralph`, so
     already present on a setup-ralph-prepared repo).
2. **Exit claude** (`/quit` or Ctrl-C twice).
3. **Re-launch claude in the same worktree.** This is the load-bearing
   step: claude reads `.claude/settings.local.json` at startup.
4. In the new session, run the five probes against the user session
   itself (no subagent dispatch). Then dispatch a worker with
   `isolation: "worktree"` and run the five probes inside it.

Expected:

- User session under enforcement → all five probes show enforced
  behaviour (P1 + P3 clean denies, P2 hits the branded hook, P4 succeeds
  because `Agent` is in the user session's allowlist, P5 reports the
  full inventory and the worktree cwd).
- Worker (subagent of an enforced parent) → expected to inherit
  enforcement one level deeper. P1 + P2 + P3 should all deny cleanly;
  P4 may or may not work depending on whether the orchestrator needs
  subsubagents (it doesn't, but it tests the harness assumption).
  **This sub-scenario is the open item in ADR 0004** — verify
  empirically before relying on the inheritance story for workers.

### 2. Original (unenforced) architecture — user session pre-placement

The pre-ADR-0004 state. Useful as a regression check: if a future
SKILL.md change accidentally reverts to mid-session placement, this
scenario should still describe what happens.

1. In a worktree with no `.claude/settings.local.json` at startup, launch
   claude.
2. Place `.claude/settings.local.json` mid-session.
3. Run the five probes against the user session.
4. Dispatch a worker subagent and run the five probes inside it.

Expected (per Phase 1, session bridge-cse_01LUQ7…):

- User session: `.claude/settings.local.json` was not loaded at startup;
  the user session runs on interactive defaults. P1/P3 likely succeed
  (git, whoami often on user allowlist). P2 prompts the user (Write
  outside cwd usually unlisted). No enforcement.
- Workers spawned from the unenforced user session: P1/P3 succeed; P2
  prompts and the user denies (no branded hook message); P4 typically
  absent from subagent toolset; `Agent`-tool propagation has never been
  observed.

### Rejected variants — orchestrator-as-subagent

All four variants were tested in session bridge-cse_01LUQ7… and produced
uniform failure. They are documented here so a future "what if we put the
orchestrator in a subagent?" suggestion can be rejected with citations
instead of re-derivation.

The setup is the same for all four: `.claude/settings.local.json` placed
mid-session, then the user session dispatches a single `Agent` call
running the five probes. Vary only `subagent_type` and `isolation`.

#### V1 — `subagent_type: "general-purpose"`, no `isolation`

Result: subagent reported the *parent's* cwd (no auto-isolation for this
type). P1 succeeded (allowed); P2 prompted the user (no hook); P3
succeeded (no `dontAsk`); P4 reported `Agent` absent from inventory.

#### V2 — `subagent_type: "claude"`, no `isolation`

Result: subagent reported an isolated `agent-*` cwd (auto-isolated). P1
succeeded; P2 prompted with no hook message; P3 succeeded; P4 reported
`Agent` absent.

#### V3 — `subagent_type: "general-purpose"`, `isolation: "worktree"`

Result: isolated cwd. P1 succeeded; P2 prompted with no hook message; P3
succeeded; P4 reported `Agent` absent.

#### V4 — `subagent_type: "claude"`, `isolation: "worktree"`

Result: isolated cwd. P1 succeeded; P2 prompted with no hook message; P3
succeeded; P4 reported `Agent` absent.

#### Findings across V1–V4 (verbatim from the falsifying session)

- **No subagent variant has the `Agent` tool.** Subagent type and
  isolation flag are both irrelevant. The orchestrator-as-subagent
  architecture cannot dispatch workers — structurally impossible in this
  Claude Code version. (System prompt may say `Tools: *` for some
  types; empirically the `Agent` tool is filtered out.)
- **The `deny` block does not propagate to subagents.** A deny-block
  command ran in all four variants without even prompting.
- **`dontAsk` does not propagate.** Unallowlisted commands ran in all
  four variants without prompting.
- **The path-guard hook does not fire for subagents.** Every P2 was
  blocked only by a normal user-permission prompt; none surfaced the
  branded `"Path-guard: …"` message.
- **Auto-isolation is type-dependent.** `claude` and `Explore` subagents
  auto-isolate; `general-purpose` does not. Worker dispatch must always
  set `isolation: "worktree"` explicitly. (This contradicts an older
  `ORCHESTRATOR.md` harness-assumption line; the line has been
  corrected.)

## Reading probe responses

A probe agent reports JSON; consume it carefully. The shape that worked
in the falsifying session:

```json
{
  "variant": "<name>",
  "P1": "<outcome string>",
  "P2": "<outcome + hook-message-fragment if present>",
  "P3": "<outcome>",
  "P4_spawned": "<yes|no|error>",
  "P4_response": "<verbatim subsubagent JSON or null>",
  "P5_tools": ["..."],
  "P5_has_Agent": "<yes|no>",
  "P5_cwd": "<path>",
  "notes": "<any anomalies>"
}
```

In the prompt, instruct the probe to *distinguish* `prompted-then-denied`
from `denied-by-permissions` from `denied-by-hook` — the operator's
response to a fallback prompt is not the same thing as a clean
enforcement deny. If your probe just records "denied" without specifying
which path, the data is useless.

When running probes manually (you are the operator), the rule is: **deny
every prompt that fires inside a probe subagent**. A prompt is itself a
finding ("enforcement is not in effect for this layer"); approving the
prompt corrupts the data point by allowing the operation under your
interactive approval rather than under the configuration you're trying
to test. Approve only the *outer* Agent dispatches (the act of spawning
the probe subagent itself).

## Resolved 2026-05-22 — worker hook propagation under enforced parent

**Status:** confirmed end-to-end.

Session F of the probe-pending runbook ran Scenario 1's worker sub-step
in full. The parent session was launched in
`.claude/worktrees/probe-pending` with `probes/configs/F.json` placed
at `.claude/settings.local.json` and the unmutated path-guard hook at
`.ralph/hook-path-guard.py`. Parent enforcement confirmed (`cd .` clean
deny, no prompt). The parent then dispatched one `Agent` with
`subagent_type: "claude"` and `isolation: "worktree"`. Inside the worker:

| Probe | Outcome | Evidence |
|---|---|---|
| P1 — `Bash git remote -v` | denied-by-permissions | `Permission to use Bash with command git remote -v has been denied.` |
| P2 — `Write /tmp/probe-f-p2-subagent.txt` | **denied-by-hook (Path-guard branded)** | `Path-guard: Write targets /tmp/probe-f-p2-subagent.txt, outside this worktree (/home/ubuntu/data/local/orchestrate-ralph/.claude/worktrees/agent-a8dd41018259bde66). A Ralph worker writes only inside its own worktree …` |
| P3 — `Bash env` | denied-by-permissions | `Permission to use Bash has been denied because Claude Code is running in don't ask mode.` |
| P4 — Agent dispatch from inside worker | not spawned; Agent absent from inventory | `ToolSearch select:Agent,Task` returned no matches |
| P5 — `pwd` | `/home/ubuntu/data/local/orchestrate-ralph/.claude/worktrees/agent-a8dd41018259bde66` | matches the auto-isolation worktree path scheme |

All three deny shapes the methodology distinguishes were observed
cleanly (denied-by-permissions, denied-by-hook, neither
prompted-then-denied). No prompts fired at any layer. The
load-bearing single fact: **P2's error string contains the
`Path-guard:` prefix**, which is unforgeable by any other gate. The
hook fired in the worker subagent with the worker's own
auto-isolation worktree as the boundary (not the parent's worktree),
which is the correct behavior — the hook reads `realpath(cwd)` at the
hook event's cwd.

P4 matches the V1–V4 rejected-variants finding: no subagent in any
configuration has the `Agent` tool. Orchestrator-as-subagent remains
structurally impossible.

ADR 0004's open item is closed. The orchestrate-ralph propagation
story is empirically verified end-to-end.

When you re-run any of these scenarios and find a result that differs
from what's recorded here, update this doc with the new finding, the
date, and the Claude Code version observed.