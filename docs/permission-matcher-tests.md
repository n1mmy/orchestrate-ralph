# Bash permission-matcher — behavioural tests

A procedure for empirically verifying what the Claude Code Bash
permission matcher actually does, and for catching drift when Claude
Code updates change its behaviour.

The matcher's exact algorithm is undocumented. Several core assumptions
in `orchestrate-ralph`'s doctrine depend on specific matcher behaviour
— this doc lists those assumptions, gives each a concrete test, and
provides the procedure to run the catalog.

When an empirical result here disagrees with the doctrine, **trust the
result and update the doctrine**.

## When to run

- Before relying on a new allowlist shape — confirm the matcher does
  what the shape implies it does.
- After a Claude Code version bump — re-run the catalog to catch drift.
- When a doctrine assumption ("compound shapes are distinct", "`:*`
  matches anything after the prefix") is being weighed against
  observation — pick the matching test and resolve the disagreement.
- After a worker exhibits unexpected behaviour (a gate passing that
  shouldn't have, a denied command that shouldn't have been) — the
  matcher's behaviour around the relevant shape is the first thing to
  verify.

## Procedure

The matcher applies to a session that **loaded a `.claude/settings.local.json`
at startup**. Setup is identical to the orchestrate-ralph happy path
(ADR 0004):

1. **Pick a worktree** (`git worktree add` somewhere disposable).
2. **Place a probe `.claude/settings.local.json`** — start from
   `setup-ralph/templates/settings.template.json`, then for each test
   adjust the `allow` / `deny` entries to the shape the test names.
3. **Place `.ralph/hook-path-guard.py`** from
   `setup-ralph/templates/hook-path-guard.py` (only matters for hook-
   related tests; harmless otherwise).
4. **Launch claude in this worktree.** This is the load-bearing step —
   claude reads `.claude/settings.local.json` at session start.
5. **Confirm enforcement** before running any test: dispatch a single
   bare `Bash` call `cd .`. It must return a clean tool error
   ("Denied by permissions") *without prompting*. If the call prompts
   or runs, the session is not enforced; exit, re-launch, retry.
6. **Run one test at a time** as bare single `Bash` calls. Record one
   of the four outcomes below.
7. **When a test requires a different allowlist shape** than the one
   loaded, edit `.claude/settings.local.json`, exit claude, re-launch,
   confirm enforcement again, then run the test. Settings are read at
   startup only.

### Outcome categories

For every test, classify the outcome into exactly one bucket:

- **Allowed** — the call executed and returned output. *No prompt.*
- **Denied (allow rule missing)** — `dontAsk` auto-denied because no
  allow rule matched. Tool error, no prompt.
- **Denied (deny rule)** — the command matched a `deny` entry. Tool
  error, no prompt.
- **Prompted** — the session is not enforced or `dontAsk` isn't in
  effect. **Stop and re-verify setup.** A prompted call's downstream
  outcome (allow / deny) doesn't tell you anything about the matcher.

`Denied (allow rule missing)` and `Denied (deny rule)` look identical
in the tool error text. To tell them apart, run the test once with
the supposedly-denying allow rule *added*: if the outcome is Allowed,
the original deny was "allow rule missing"; if it's still Denied,
the original was "deny rule."

## Load-bearing assumptions

Each row is a claim the package's doctrine, ADRs, or settings template
relies on. The "Test(s)" column points at the catalog entries that
validate it. **The "Status" column starts empty** — fill it in as you
run the tests; mark "confirmed", "falsified (see <test ID>)", or
"partial" with notes. A claim with no empirical status is just an
assumption; the doc is most useful once each row has a result.

| # | Assumption | Where it lives | Test(s) | Status |
|---|---|---|---|---|
| 1 | `:*` after a command name allowlists "any suffix" | `setup-ralph/SKILL.md` step 3; common template entries like `Bash(git:*)` | A1–A5 | — |
| 2 | A bare command name with no `:*` is an exact match | `Bash(date +%s)` in the template uses this shape | C1–C4 | — |
| 3 | Compound shapes (`&&` / `||` / `;` / pipes / redirects / subshells) are distinct patterns from their parts and fail when not explicitly allowlisted | `ORCHESTRATOR.md` "Bash command shape"; `PROMPT.md` "Bash command shape"; the live-run-doctrine commits | D1–D6, E1–E7 | — |
| 4 | The matcher decomposes `&&`-chained compounds and checks each half against allow + deny | `ORCHESTRATOR.md` step 6 implicitly; permission-denied worker doctrine | D1, D2, D3 | — |
| 5 | A flag-bearing variant of an allowlisted command (e.g. `ls -la`) is matched by `Bash(<cmd>:*)` | various template entries assume this | B1, B2, B4 | — |
| 6 | Worker subagents launched with `isolation: "worktree"` inherit the orchestrator's loaded `.claude/settings.local.json` (allowlist, deny, `dontAsk`, hook) | `ORCHESTRATOR.md` prereq #2; `handoff.md` "Resolved — hook propagation" | see `docs/subagent-permission-tests.md` instead — that catalog covers propagation | — |
| 7 | Top-level tools (`Write`, `Read`, `Edit`, `Agent`, `Glob`, `Grep`) need explicit allow entries under `dontAsk`, else they auto-deny | settings template lists them; ADR 0004 names `Agent` as the load-bearing one | T1–T3 | — |
| 8 | `dontAsk` causes any unallowlisted call to auto-deny as a tool error (no prompt) | `ORCHESTRATOR.md`; setup-ralph "worker permission mode" prose; ADR 0004 | covered by every catalog test — the procedure's enforcement-confirmation step is the canonical case | — |
| 9 | The `PreToolUse` path-guard hook fires for `Write` / `Edit` / `NotebookEdit` whose target resolves outside `realpath(cwd)` | `setup-ralph/templates/hook-path-guard.py`; ADR 0002 | H1–H4 | — |
| 10 | Glob expansion / quoting / env-var expansion in the command don't change which allow rule matches | implicit; no specific doctrine, but assumed by `Bash(echo:*)` matching `echo "hello world"` etc. | F1–F4 | — |

## Test catalog

Each test is self-contained: an allow / deny rule shape, a probe
command, the outcome a naive reading of the rules would predict, and
an empirical cell to fill in. **The Empirical column starts empty.**

When you run a test, fill in the result, the date, and the Claude Code
version observed. When a result diverges from the Expected column,
also update the relevant assumption row above and patch the doctrine
where it relied on the old behaviour (see "Updating this doc" at the
end).

Probes use `echo` as the safe primitive where possible (no side
effects). Where a destructive command is needed, use `cd .` (a genuine
no-op under Claude Code, since cwd does not persist across `Bash`
calls).

### Group A — `:*` prefix matching (assumption #1)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| A1 | `Bash(echo:*)` | `echo` | Allowed | |
| A2 | `Bash(echo:*)` | `echo hello` | Allowed | |
| A3 | `Bash(echo:*)` | `echo hello world` | Allowed | |
| A4 | `Bash(echo:*)` | `echo "hello world"` (quoted) | Allowed | |
| A5 | `Bash(echo:*)` | `  echo hello` (leading whitespace) | Allowed | |

### Group B — flag-arg variants (assumption #5)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| B1 | `Bash(ls:*)` | `ls` | Allowed | |
| B2 | `Bash(ls:*)` | `ls -la` | Allowed | |
| B3 | `Bash(ls:*)` | `ls /tmp` (positional arg) | Allowed | |
| B4 | `Bash(ls -la:*)` | `ls -la` | Allowed | |
| B5 | `Bash(ls -la:*)` | `ls -lah` | Allowed | |
| B6 | `Bash(ls -la:*)` | `ls -al` (flag order swapped) | Allowed | |
| B7 | `Bash(ls -la:*)` | `ls -la /tmp` (positional after flags) | Allowed | |

### Group C — exact match, no `:*` (assumption #2)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| C1 | `Bash(echo)` | `echo` | Allowed | |
| C2 | `Bash(echo)` | `echo hello` | Denied (allow rule missing) | |
| C3 | `Bash(date +%s)` | `date +%s` | Allowed | |
| C4 | `Bash(date +%s)` | `date +%s -u` | Denied | |
| C5 | `Bash(pnpm typecheck)` | `pnpm typecheck` | Allowed | |
| C6 | `Bash(pnpm typecheck)` | `pnpm typecheck 2>&1 \| tail -30` | Denied | |

### Group D — command separators (assumptions #3, #4)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| D1 | `Bash(echo:*)` | `echo a && echo b` | Allowed | |
| D2 | `Bash(echo:*)`, deny `Bash(cd:*)` | `echo a && cd .` | Denied (deny) | |
| D3 | `Bash(echo:*)` only | `echo a && whoami` | Denied (allow rule missing) | |
| D4 | `Bash(echo:*)` | `echo a ; echo b` | Allowed | |
| D5 | `Bash(echo:*)` | `echo a \|\| echo b` | Allowed | |
| D6 | `Bash(echo:*)` | `echo a &` (background) | Allowed | |

### Group E — pipes, redirects, subshells (assumption #3)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| E1 | `Bash(echo:*)`, `Bash(tail:*)` | `echo hello \| tail -1` | Allowed | |
| E2 | `Bash(echo:*)` only (no `tail`) | `echo hello \| tail -1` | Denied (allow rule missing) | |
| E3 | `Bash(echo:*)` | `echo hello > /tmp/x` | Allowed | |
| E4 | `Bash(echo:*)` | `echo hello 2>&1 \| tail -1` (no `tail` in allow) | Denied | |
| E5 | `Bash(echo:*)` | `echo $(whoami)` (command substitution, `whoami` unallowlisted) | Denied | |
| E6 | `Bash(echo:*)` | `` echo `whoami` `` (backtick substitution) | Denied | |
| E7 | `Bash(pnpm typecheck)` (exact) | `pnpm typecheck 2>&1 \| tail -30` | Denied | |

E2 and E1 together disambiguate two hypotheses for pipes: if E2 is
Allowed, pipes are intra-command (the whole pipeline is one command,
prefix-matched). If E2 is Denied, pipes decompose like `&&` (both
halves checked individually).

E5/E6 are the worst potential hole. If a subshell counts as
intra-command, `echo $(rm /tmp/probe)` matches `Bash(echo:*)` and runs
`rm` inside the subshell — same shape as a pipe bypass but with
arbitrary code in the subshell. **Probe before relying on the matcher
to block this.**

### Group F — quoting, glob, env (assumption #10)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| F1 | `Bash(echo:*)` | `echo "hello world"` | Allowed | |
| F2 | `Bash(echo:*)` | `echo *` (glob) | Allowed | |
| F3 | `Bash(echo:*)` | `echo $HOME` | Allowed | |
| F4 | `Bash(echo:*)` | `echo \$HOME` (escaped) | Allowed | |

### Group T — top-level tool gating (assumption #7)

| ID | Allow | Tool call | Expected | Empirical |
|---|---|---|---|---|
| T1 | `Agent` NOT in allow | `Agent` dispatch | Denied | |
| T2 | `Write` NOT in allow | `Write` to a worktree-internal path | Denied | |
| T3 | `Read` NOT in allow | `Read` of any file | Denied | |

T1–T3 probe whether the bare tool-name entries in the template
(`Write`, `Read`, `Edit`, `Glob`, `Grep`, `Agent`) are actually
necessary under `dontAsk`, or whether top-level tools are always
permitted regardless of the allow list.

### Group H — path-guard hook (assumption #9)

| ID | Setup | Tool call | Expected | Empirical |
|---|---|---|---|---|
| H1 | Hook installed, cwd is worktree root | `Write` `<worktree>/foo.txt` | Allowed | |
| H2 | Hook installed | `Write` `/tmp/probe.txt` | Denied (hook, branded "Path-guard" message) | |
| H3 | Hook installed, target uses `..` to climb above worktree | `Write` `../escape.txt` | Denied (hook canonicalises with realpath) | |
| H4 | Hook installed, `EXTRA_ALLOWED_ROOTS = ["/tmp/whitelisted"]` | `Write` `/tmp/whitelisted/foo.txt` | Allowed | |
| H5 | Hook installed | `Bash` `echo x > /tmp/escape.txt` (subprocess write outside worktree) | Allowed — hook does not cover subprocess writes | Documented in hook script header |

H5 documents the known limit: the hook only sees Claude's own
`Write`/`Edit`/`NotebookEdit` calls. Anything mediated by `Bash` — a
subprocess writing to the filesystem — bypasses the hook by design.

## Updating this doc

When you fill in an Empirical cell:

1. Record the result, the date, and the Claude Code version observed.
2. Compare against the row's Expected outcome.
3. If they differ, update the **assumptions table** at the top —
   change the Status, link to the test that falsified the assumption.
4. Check the **doctrine surface area** for any text that depended on
   the old behaviour. Likely places: `orchestrate-ralph/ORCHESTRATOR.md`
   ("Bash command shape" passages), `orchestrate-ralph/PROMPT.md`
   ("Bash command shape" section), `setup-ralph/SKILL.md` step 3,
   the ADRs.
5. Patch the doctrine in the same change as the test result. A
   falsified assumption left in the doctrine becomes the next bite.