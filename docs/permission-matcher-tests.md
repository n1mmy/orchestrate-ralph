# Bash permission-matcher — behavioural tests

A procedure for empirically verifying what the Claude Code Bash
permission matcher actually does, and for catching drift when Claude
Code updates change its behaviour.

The matcher's exact algorithm is undocumented. Several core assumptions
in `orchestrate-ralph`'s doctrine depend on specific matcher behaviour
— this doc lists those assumptions, gives each a concrete test, and
provides the procedure to run the catalog.

When an empirical result here disagrees with the doctrine, **trust the
result and update the doctrine**. Doctrine is descriptive
([ADR 0005](adr/0005-descriptive-doctrine-after-the-matcher-catalog.md));
falsified assumptions must be removed, not just demoted.

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
(ADR 0004). For a worked example with multi-session swap-and-restart
and minimal-allowlist probe configurations, see
[`probes/group-m-runbook.md`](probes/group-m-runbook.md).

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
| 1 | `:*` after a command name allowlists "any suffix" | `setup-ralph/SKILL.md` step 3; common template entries like `Bash(git:*)` | A1–A5 | partial — A1–A5 confirmed for flag-only suffixes; B3 falsifies for absolute paths outside the worktree when the command is on the §2 path-typed list (`ls`, `cat`, `head`, `tail`, `wc`, `grep`, `find`, `stat`); 2026-05-22 Bm14 shows §2 does NOT fire for commands off that list (`git status /tmp` Allowed by matcher) — see Findings §2 update. |
| 2 | A bare command name with no `:*` is an exact match | `Bash(date +%s)` in the template uses this shape | C3, C4 superseded; Cr1–Cr9; D1–D5 for multi-word | **confirmed** (2026-05-22) — single-word: Cr1 Allowed (`rmdir` bare matches the exact rule); Cr2–Cr9 all Denied (any suffix — flag, positional, empty quoted arg, extra whitespace — fails the exact match). Multi-word: D1 Allowed (`pnpm typecheck` bare matches); D2/D3 Denied (`pnpm typecheck --watch`, `pnpm typecheck src` both rejected). The earlier "falsified" reading was a safe-list confound: `Bash(date +%s)` couldn't be isolated because `date` is safe-listed, and `Bash(echo)` couldn't either because `echo` is safe-listed too. Using non-safe-listed targets gives clean tests and the assumption holds for both single-word and multi-word exact-match rules. |
| 3 | Compound shapes (`&&` / `||` / `;` / pipes / redirects / subshells) are distinct patterns from their parts and fail when not explicitly allowlisted | `ORCHESTRATOR.md` "Bash command shape"; `PROMPT.md` "Bash command shape"; the live-run-doctrine commits | D1–D6, E1–E7, R19–R23 | confirmed — every stage of a compound (whether `&&` / `;` / pipe) must independently clear allow-or-safe-list AND the §2 path-locality gate. R19 (`echo hello \| env` Denied), R21 (`env \| echo hi` Denied), R23 (`echo hello \| cat /etc/issue` Denied) lay this out for pipes; D1–D6 covered the other separators. E5/E6 confirm subshells don't bypass. D3's earlier "Allowed" anomaly was the safe-list, not pipe-decomposition. |
| 4 | The matcher decomposes `&&`-chained compounds and checks each half against allow + deny | `ORCHESTRATOR.md` step 6 implicitly; permission-denied worker doctrine | D1, D2, D3 | confirmed — D2 catches a deny on the right half; follow-up probe `echo a && env` is denied because `env` is denied alone. D3 was Allowed only because the right half is on the built-in safe list. |
| 5 | A flag-bearing variant of an allowlisted command (e.g. `ls -la`) is matched by `Bash(<cmd>:*)` | various template entries assume this | B1, B2, B4–B7 superseded; Bm1–Bm17 | confirmed — Bm1–Bm6 confirm `:*` accepts arbitrary suffix (flags, `=`-suffixed flags, multiple flags). Bm9–Bm11 confirm strict word-boundary on both sides. Bm14 confirms §2 is command-specific (does not fire for `git status`). Bm16 confirms multi-word rules are position-locked at argv 0/1 — a leading flag like `git -c X status` does NOT match `Bash(git status:*)`. Group B's original B4–B7 (`Bash(ls -la:*)`) were superseded by Group Bm using a non-safe-listed target because Session A confirmed `ls` is safe-listed. |
| 6 | Worker subagents launched with `isolation: "worktree"` inherit the orchestrator's loaded `.claude/settings.local.json` (allowlist, deny, `dontAsk`, hook) | `ORCHESTRATOR.md` prereq #2; `handoff.md` "Resolved — hook propagation" | see `docs/subagent-permission-tests.md` instead — that catalog covers propagation | — |
| 7 | Top-level tools (`Write`, `Read`, `Edit`, `Agent`, `Glob`, `Grep`) need explicit allow entries under `dontAsk`, else they auto-deny | settings template lists them; ADR 0004 names `Agent` as the load-bearing one | T1–T5 | **falsified for most tools — split into per-tool behaviour** (see Findings §4). Gated: `Write` (T2), `Edit` (T5). Auto-permitted under `dontAsk`: `Read` (T3), `Agent` (T1), `NotebookEdit` (T4). Unobservable on this host: `Glob`, `Grep` (the v2.1.117+ Linux build drops them entirely). Practical impact: the template's `Read`/`Agent`/`Glob`/`Grep` entries are dead weight under `dontAsk`; `Write`/`Edit` are load-bearing. |
| 8 | `dontAsk` causes any unallowlisted call to auto-deny as a tool error (no prompt) | `ORCHESTRATOR.md`; setup-ralph "worker permission mode" prose; ADR 0004 | covered by every catalog test — the procedure's enforcement-confirmation step is the canonical case | confirmed — every `cd .`, `env`, `rm`, `mkdir`, `claude --version`, `ls /tmp`, `ls /` produced "Denied by permissions" with no prompt; refinements: "unallowlisted" excludes (a) the built-in Bash safe-command list and (b) the auto-permitted top-level tools `Read`/`Agent`/`NotebookEdit` (see Findings §4). |
| 9 | The `PreToolUse` path-guard hook fires for `Write` / `Edit` / `NotebookEdit` whose target resolves outside `realpath(cwd)` | `setup-ralph/templates/hook-path-guard.py`; ADR 0002 | H1–H4 | confirmed for H1–H3; H4 not run (needs `EXTRA_ALLOWED_ROOTS` edit + session restart) |
| 10 | Glob expansion / quoting / env-var expansion in the command don't change which allow rule matches | implicit; no specific doctrine, but assumed by `Bash(echo:*)` matching `echo "hello world"` etc. | F1–F4 | falsified — F3 (`echo $HOME`) was Denied; the matcher rejects commands containing unexpanded `$VAR` references in the same shape that gets blocked for absolute external paths. Quoted strings (F1) and globs (F2) and escaped `\$` (F4) are unaffected. |
| 11 | A command invoked by full path (e.g. `/usr/bin/git`) is "a different, unrecognised shape" and fails to match the allow rule for the bare command name | `PROMPT.md:93–94`; `ORCHESTRATOR.md:110` ("never run a command by full path") | N1–N6 | confirmed — but the rationale is sharper than the doctrine states. N5 shows the gate fires even for an absolute path **inside** the worktree, so it isn't the argument-path gate (§2) re-firing on the first token. It is a separate name-shape lookup: any `/` in the first token (`/abs/path` or `./relative`) makes the lookup miss against both the allow list and the safe list. |
| 12 | Multi-word `:*` prefixes in allow / deny rules (`Bash(git push:*)`, `Bash(git status:*)`) match exactly the multi-word prefix plus any suffix, and do not match unrelated subcommands | `setup-ralph/templates/settings.template.json` deny block (`Bash(git push:*)`, `Bash(git fetch:*)`, etc.); template-mode prose | M1, M2, M5 | confirmed — multi-word `:*` matches the prefix plus any suffix and does not over-match unrelated subcommands, on both sides. M1/M2 cover the **deny** side (`Bash(git push:*)` denied `git push --help`; did not over-match `git status`). M5 covers the **allow** side (`Bash(git status:*)` allowed `git status --short` with no `Bash(git:*)` present to confound). |
| 13 | `Bash(<cmd>:*)` matches strictly the first-token command name, not arbitrary first-token text starting with `<cmd>` (i.e., the matcher tokenises on word boundary, so `Bash(rm:*)` does not match `rmdir`) | Implicit everywhere a short command is allowlisted via `:*` (`Bash(rm:*)` would be problematic if it over-matched `rmdir`); also a security-relevant property of every `Bash(<short>:*)` rule | M4 | confirmed via M4 — word-boundary tokenisation, not pure literal-prefix matching. With `Bash(rm:*)` as the only allow rule, `rmdir --help` was Denied. `Bash(<short>:*)` rules are scoped to the exact command name as intended. |

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
| A1 | `Bash(echo:*)` | `echo` | Allowed | Allowed (2026-05-20) |
| A2 | `Bash(echo:*)` | `echo hello` | Allowed | Allowed (2026-05-20) |
| A3 | `Bash(echo:*)` | `echo hello world` | Allowed | Allowed (2026-05-20) |
| A4 | `Bash(echo:*)` | `echo "hello world"` (quoted) | Allowed | Allowed (2026-05-20) |
| A5 | `Bash(echo:*)` | `  echo hello` (leading whitespace) | Allowed | Allowed (2026-05-20) |

### Group B — flag-arg variants (assumption #5)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| B1 | `Bash(ls:*)` | `ls` | Allowed | Allowed (2026-05-20) |
| B2 | `Bash(ls:*)` | `ls -la` | Allowed | Allowed (2026-05-20) |
| B3 | `Bash(ls:*)` | `ls /tmp` (positional arg) | Allowed | **Denied** (2026-05-20) — absolute path outside the worktree. Probes during this run: `ls .`, `ls README.md`, `ls docs`, `ls /home/ubuntu/data/local/orchestrate-ralph` all Allowed; `ls /tmp`, `ls /usr/bin`, `ls /etc`, `ls /home` (ancestor of worktree), `ls /` all Denied. The gate is "absolute path not contained by `realpath(cwd)`" — ancestor paths count as outside, not just sibling paths. |
| B4 | `Bash(ls -la:*)` | `ls -la` | Allowed | **superseded** (2026-05-22) — Session A's safe-list expansion confirmed `ls` is on the built-in safe list (Findings §1), so any `ls -la …` probe would be Allowed regardless of the multi-word rule. Multi-word allow semantics are now covered by Group Bm using a non-safe-listed target (`Bash(git status:*)`). |
| B5 | `Bash(ls -la:*)` | `ls -lah` | Allowed | superseded — see B4. |
| B6 | `Bash(ls -la:*)` | `ls -al` (flag order swapped) | Allowed | superseded — see B4. |
| B7 | `Bash(ls -la:*)` | `ls -la /tmp` (positional after flags) | Allowed | superseded — see B4. |

### Group C — exact match, no `:*` (assumption #2)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| C1 | `Bash(echo)` | `echo` | Allowed | superseded (2026-05-22) — `echo` is on the built-in safe list (Cs1 below), so `Bash(echo)` cannot be discriminated from "no rule + safe list" with this target. See Cr1–Cr9 for exact-match probes with `Bash(rmdir)` (a non-safe-listed target). |
| C2 | `Bash(echo)` | `echo hello` | Denied (allow rule missing) | superseded — see C1; Cs2 below confirms `echo hello` also runs via safe list with no rule. |
| C3 | `Bash(date +%s)` | `date +%s` | Allowed | Allowed (2026-05-20) — but follow-up probes show `date`, `date +%Y` also Allowed, so the rule is not load-bearing; `date` is on the built-in safe-command list |
| C4 | `Bash(date +%s)` | `date +%s -u` | Denied | **Allowed** (2026-05-20) — same: `date` is on the built-in safe list |
| C5 | `Bash(pnpm typecheck)` | `pnpm typecheck` | Allowed | Allowed (2026-05-22) — D1: bare multi-word matches the exact rule. Underlying pnpm errored (no package.json) but the matcher decided before exec. |
| C6 | `Bash(pnpm typecheck)` | `pnpm typecheck 2>&1 \| tail -30` | Denied | Expected revised after `tail` confirmed safe-listed in Session A. **Allowed** (2026-05-22) — D8: both pipeline stages clear (pnpm via the exact rule, tail via the safe list). The compound-decomposition story is intact — D6 (`pnpm typecheck \| env`) is **Denied** because `env` is genuinely not safe-listed; see new E-series rows below. |
| D2 | `Bash(pnpm typecheck)` (exact) | `pnpm typecheck --watch` | Denied | Denied (2026-05-22) — confirms multi-word exact is genuinely exact (no implicit `:*`); same shape as Cr2 for single-word exact. |
| D3 | same | `pnpm typecheck src` (positional suffix) | Denied | Denied (2026-05-22) — positional arg also rejected by exact match. |
| D4 | same | `pnpm` (bare command) | Denied | Denied (2026-05-22) — no rule for bare `pnpm`; not safe-listed. |
| D5 | same | `pnpm install` (different subcommand) | Denied | Denied (2026-05-22) — multi-word exact doesn't match a different subcommand. |
| Cr1 | `Bash(rmdir)` | `rmdir` | Allowed | Allowed (2026-05-22) — bare token matches the exact rule; underlying `rmdir` errored `missing operand` but that's after the matcher |
| Cr2 | `Bash(rmdir)` | `rmdir foo` | Denied (allow rule missing) | Denied (2026-05-22) — exact-match does NOT accept any suffix token |
| Cr3 | `Bash(rmdir)` | `rmdir ""` (empty quoted arg) | Denied | Denied (2026-05-22) — empty quoted arg still counts as a suffix |
| Cr4 | `Bash(rmdir)` | `rmdir  foo` (two spaces) | Denied | Denied (2026-05-22) — extra whitespace is not normalised; the second space + foo is a suffix |
| Cr5 | `Bash(rmdir)` | `rmdir --help` | Denied | Denied (2026-05-22) — a flag arg is still a suffix |
| Cr6 | `Bash(rmdir)` | `rmdir -p foo` | Denied | Denied (2026-05-22) |
| Cr7 | `Bash(rmdir)` | `rmdir foo bar` | Denied | Denied (2026-05-22) |
| Cr8 | `Bash(rmdir)` | `rmdir /tmp/probe-c8` (outside-cwd path) | Denied | Denied (allow rule missing) (2026-05-22) — the exact rule doesn't match this shape; §2 never gets a turn. Probing §2 for `rmdir` requires `Bash(rmdir:*)` as the allow shape (deferred). |
| Cr9 | `Bash(rmdir)` | `rmdir probe-c9` (cwd-relative) | Denied | Denied (2026-05-22) — same; allow rule doesn't match |
| Cs1 | `Bash(rmdir)` (irrelevant to echo) | `echo` (bare) | unknown — depends on safe list | **Allowed** (2026-05-22) — no `Bash(echo*)` rule present; `echo` is on the built-in safe list. Updates Findings §1. |
| Cs2 | same | `echo hello` | depends | Allowed (2026-05-22) — with-arg form also safe-listed |
| Cs3 | same | `printf` (bare) | depends | Allowed (2026-05-22) — bare printf safe-listed (the Session A `printf "hi\n"` probe only confirmed the with-arg shape; this fills the gap) |
| Cs4 | same | `yes` (bare) | Denied if not safe-listed | Denied (2026-05-22) — `yes` is genuinely not safe-listed; serves as the canonical clean negative control. |

### Group D — command separators (assumptions #3, #4)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| D1 | `Bash(echo:*)` | `echo a && echo b` | Allowed | Allowed (2026-05-20) |
| D2 | `Bash(echo:*)`, deny `Bash(cd:*)` | `echo a && cd .` | Denied (deny) | Denied (2026-05-20) |
| D3 | `Bash(echo:*)` only | `echo a && whoami` | Denied (allow rule missing) | **Allowed** (2026-05-20) — `whoami` is on the built-in safe list (Allowed on its own). Follow-up probe `echo a && env` is **Denied** (env is denied on its own), confirming `&&` does decompose for allow checks; the divergence is the safe list, not the decomposition. |
| D4 | `Bash(echo:*)` | `echo a ; echo b` | Allowed | Allowed (2026-05-20) |
| D5 | `Bash(echo:*)` | `echo a \|\| echo b` | Allowed | Allowed (2026-05-20) — second half was skipped by shell short-circuit but the matcher allowed the call |
| D6 | `Bash(echo:*)` | `echo a &` (background) | Allowed | Allowed (2026-05-20) |

### Group E — pipes, redirects, subshells (assumption #3)

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| E1 | `Bash(echo:*)`, `Bash(tail:*)` | `echo hello \| tail -1` | Allowed | Allowed (2026-05-20) |
| E2 | `Bash(echo:*)` only (no `tail`) | `echo hello \| tail -1` | Denied (allow rule missing) | **Allowed** (2026-05-22) — but not by pipe-bypass: `tail` is on the built-in safe list (see Findings §1, R5/R6), so every pipeline stage independently passes. Follow-up R19 (`echo hello \| env`) is Denied because `env` is neither allowed nor safe-listed, confirming pipes decompose like `&&` — every stage must clear matcher + §2. |
| E3 | `Bash(echo:*)` | `echo hello > /tmp/x` | Allowed | **Denied** (2026-05-20) — `/tmp/x` is outside the worktree; same path-aware gate as B3 |
| E4 | `Bash(echo:*)` | `echo hello 2>&1 \| tail -1` (no `tail` in allow) | Denied | **Allowed** (2026-05-22) — same as E2: `tail` is safe-listed. Stderr redirect is transparent to the matcher. |
| E5 | `Bash(echo:*)` | `echo $(whoami)` (command substitution, `whoami` unallowlisted) | Denied | Denied (2026-05-20) — note: even though `whoami` is on the built-in safe list (D3), wrapping it in `$(...)` still denies the outer call. Command substitution surfaces the inner command to the matcher and the wrapped form is rejected as a distinct shape. |
| E6 | `Bash(echo:*)` | `` echo `whoami` `` (backtick substitution) | Denied | Denied (2026-05-20) — same |
| E7 | `Bash(pnpm typecheck)` (exact) | `pnpm typecheck 2>&1 \| tail -30` | Denied | Expected revised — `tail` is safe-listed (Session A R5/R6). **Allowed** (2026-05-22, D8) — both stages clear; the catalog originally expected Denied under the false premise that `tail` needed a rule. |
| D6 | `Bash(pnpm typecheck)` + `Bash(rmdir:*)`; NO `Bash(echo:*)` | `pnpm typecheck \| env` | Denied | Denied (allow rule missing) (2026-05-22) — `env` is not safe-listed (Session A); compound decomposes per assumption #3, and the env stage fails to clear. The discriminating test for "does the compound rule bypass per-stage gating when the leader is multi-word?" — confirms it does not. |
| D7 | same | `pnpm typecheck 2>&1 \| env` | Denied | Denied (2026-05-22) — stderr redirect doesn't disguise the compound from the matcher. |
| D9 | same | `pnpm typecheck && env` | Denied | Denied (2026-05-22) — `&&` decomposes; the env half fails to clear. Re-confirms assumption #4 with a multi-word leading stage. |
| D10 | same | `pnpm typecheck && rmdir nonexistent-d10` | Allowed | Allowed (2026-05-22) — both halves clear (pnpm via the exact rule, rmdir via `Bash(rmdir:*)`); runtime short-circuits on pnpm's missing-package.json error so rmdir doesn't actually run, but matcher passed both. |
| D-bonus | same | `pnpm typecheck \| cat /tmp/x` | Denied | Denied (2026-05-22) — §2 fires on the downstream `cat /tmp/x` (outside-cwd path arg to a §2-listed command) even though the leading stage clears via the multi-word rule. Confirms §2 fires per pipeline stage independently of where the allowed stage lives — matches Session A R23 with a multi-word leader. |

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
| F1 | `Bash(echo:*)` | `echo "hello world"` | Allowed | Allowed (2026-05-20) |
| F2 | `Bash(echo:*)` | `echo *` (glob) | Allowed | Allowed (2026-05-20) |
| F3 | `Bash(echo:*)` | `echo $HOME` | Allowed | **Denied** (2026-05-20) — unexpanded `$VAR` triggers the same shape-rejection as outside-worktree paths; the matcher treats it as potentially resolving to a sensitive value |
| F4 | `Bash(echo:*)` | `echo \$HOME` (escaped) | Allowed | Allowed (2026-05-20) — escaping the `$` removes the variable reference, so the gate doesn't fire |

### Group T — top-level tool gating (assumption #7)

| ID | Allow | Tool call | Expected | Empirical |
|---|---|---|---|---|
| T1 | `Agent` NOT in allow | `Agent` dispatch | Denied | **Allowed** (2026-05-22) — `Agent` is auto-permitted under `dontAsk`; allow-list entry is not required. See Findings §4. |
| T2 | `Write` NOT in allow | `Write` to a worktree-internal path | Denied | Denied (2026-05-22) — generic "don't ask mode" denial; matcher rejects upstream of the path-guard hook. |
| T3 | `Read` NOT in allow | `Read` of any file | Denied | **Allowed** (2026-05-22) — `Read` is auto-permitted under `dontAsk`. See Findings §4. |
| T4 | `NotebookEdit` NOT in allow | `NotebookEdit` of any path | Denied | **Allowed** (2026-05-22, R27) — `NotebookEdit` is auto-permitted under `dontAsk`; the matcher passes and the call reaches the path-guard hook. See Findings §4. |
| T5 | `Edit` NOT in allow | `Edit` of any file | Denied | Denied (2026-05-22, R26) — same generic "don't ask mode" denial as `Write`. Matcher rejects upstream of the hook, so the hook never fires for unallowed Edits. |

T1–T5 probe whether the bare tool-name entries in the template
(`Write`, `Read`, `Edit`, `Glob`, `Grep`, `Agent`) are actually
necessary under `dontAsk`, or whether top-level tools are always
permitted regardless of the allow list. Result (Findings §4): the
split is **mutating-text vs everything else** — `Write` and `Edit`
require explicit allow; `Read`, `NotebookEdit`, `Agent` are
auto-permitted. `Glob` and `Grep` were not exposed in the Linux build
used here (v2.1.117+ drops them in favour of Bash `bfs`/`ugrep`).

### Group N — command-name shape (path-bearing first token)

Added 2026-05-20 after a follow-up probe. Doctrine claim:
`PROMPT.md:93–94` says "Run commands bare, not by full path. `git`,
`pnpm`, `node` — not `/usr/bin/git`; an explicit path is a different,
unrecognised shape." These tests measure that rule directly and
disambiguate it from Group B's argument-path gate.

| ID | Allow | Command | Expected | Empirical |
|---|---|---|---|---|
| N1 | `Bash(git:*)` | `/usr/bin/git status` | Denied | Denied (2026-05-20) |
| N2 | `Bash(echo:*)` | `/usr/bin/echo hello` | Denied | Denied (2026-05-20) |
| N3 | `Bash(ls:*)` | `/bin/ls` | Denied | Denied (2026-05-20) |
| N4 | (safe list) | `/usr/bin/whoami` | Denied | Denied (2026-05-20) — safe list doesn't cover the path-bearing form |
| N5 | `Bash(echo:*)` (irrelevant) | `/home/ubuntu/data/local/orchestrate-ralph/CONTEXT.md` (absolute path INSIDE worktree, non-executable file) | Denied if the gate is "first token contains `/`"; Allowed if it's the path-locality gate | Denied (2026-05-20) — proves the gate is on the first token's shape, not on whether the path is inside cwd |
| N6 | `Bash(echo:*)` (irrelevant) | `./CONTEXT.md` (relative, leading `./`) | Denied if the gate is "first token contains `/`" | Denied (2026-05-20) — `./X` is rejected the same way |

N5 is the disambiguation probe. Group B's `ls /tmp` (Denied) and
`ls /home/.../orchestrate-ralph` (Allowed) show the path-locality gate
*on argument tokens* draws a line at the worktree boundary. N5 puts an
absolute path **inside** the worktree as the *first* token and it's
still Denied — so the first-token gate doesn't care about the worktree
boundary, only that the token contains `/`.

### Group H — path-guard hook (assumption #9)

| ID | Setup | Tool call | Expected | Empirical |
|---|---|---|---|---|
| H1 | Hook installed, cwd is worktree root | `Write` `<worktree>/foo.txt` | Allowed | Allowed (2026-05-20) — probe written to `<worktree>/probe-h1.txt`; left behind because `rm` is not allowlisted |
| H2 | Hook installed | `Write` `/tmp/probe.txt` | Denied (hook, branded "Path-guard" message) | Denied (2026-05-20) — error text: `Path-guard: Write targets /tmp/probe-h2.txt, outside this worktree (/home/ubuntu/data/local/orchestrate-ralph). …` |
| H3 | Hook installed, target uses `..` to climb above worktree | `Write` `../escape.txt` | Denied (hook canonicalises with realpath) | Denied (2026-05-20) — `../probe-h3.txt` resolved to `/home/ubuntu/data/local/probe-h3.txt` and was rejected by the same hook message |
| H4 | Hook installed, `EXTRA_ALLOWED_ROOTS = ["/tmp/whitelisted"]` | `Write` `/tmp/whitelisted/foo.txt` | Allowed | not run — needs edit to `hook-path-guard.py` + session restart |
| H5 | Hook installed | `Bash` `echo x > /tmp/escape.txt` (subprocess write outside worktree) | Allowed — hook does not cover subprocess writes | Documented in hook script header. **2026-05-20 finding:** with the current `Bash(echo:*)` allow, this subprocess form is actually **Denied by the matcher** (E3) before the hook would have a chance to see it — so the hook's documented limit is masked by the path-aware Bash gate. The hook limit still applies to any subprocess form whose Bash command shape *is* allowlisted (e.g. `git`, `tee`, `cp`). |

H5 documents the known limit: the hook only sees Claude's own
`Write`/`Edit`/`NotebookEdit` calls. Anything mediated by `Bash` — a
subprocess writing to the filesystem — bypasses the hook by design.

### Group M — multi-word prefixes and first-token boundary (assumptions #12, #13)

Tests whether multi-word `:*` rules (`Bash(git push:*)`,
`Bash(git status:*)`) behave as intended — load-bearing for the template's
remote-git deny block — and whether the matcher tokenises the first token
on a word boundary (so `Bash(rm:*)` does not match `rmdir`) or treats
`:*` as a pure literal-prefix wildcard (which would make every short-name
allow rule over-broad).

**All probes are deliberately side-effect free.** `git push --help` is
intercepted by git's `--help` handler and execs the man page — no network
contact, no on-disk change. `git status` and `git status --short` are
read-only. `rmdir --help` prints help and exits without touching a
directory. If you add probes to this group, hold to the same standard:
**no probe may have real-world side effects even in the failure mode
where the matcher unexpectedly Allows.**

| ID | Allow / Deny | Command | Expected | Empirical |
|---|---|---|---|---|
| M0 | (no allow rule for `rmdir`) | `rmdir --help` | Denied | Denied (2026-05-20) — precondition for M4 holds; `rmdir` is not on the safe list. |
| M1 | deny `Bash(git push:*)`, allow `Bash(git:*)` | `git push --help` | Denied | Denied (2026-05-20) — multi-word deny `Bash(git push:*)` matches a `git push <suffix>` shape. |
| M2 | same | `git status` | Allowed | Allowed (2026-05-20) — multi-word deny does not over-match unrelated `git` subcommands. |
| M4 | allow `Bash(rm:*)` only (no other rule for `rmdir`) | `rmdir --help` | Denied if word-boundary tokenisation; Allowed if pure literal prefix matching | Denied (allow rule missing) (2026-05-20) — word-boundary tokenisation confirmed; `Bash(rm:*)` does not over-match `rmdir`. With M0 having established `rmdir` is not on the safe list, the only Allow path would have been pure-prefix over-match by `Bash(rm:*)`; that did not fire. |
| M5 | allow `Bash(git status:*)` only | `git status --short` | Allowed | Allowed (2026-05-20) — Session C's allow list contained only `Bash(git status:*)` (no `Bash(git:*)`), so the Allowed outcome attributes unambiguously to the multi-word rule. |

**Known limit:** the catalog does not probe whether a multi-word allow
like `Bash(git status:*)` over-matches a *similar* shape such as
`git status-x` or `git statusquery`. No real binary fits that probe
without inventing fictional `git` subcommands, and the matcher's response
is consistent enough across A1-style probes that pure-prefix
over-matching at the multi-word level would be the same falsification as
M4 at the first-token level. Re-probe if M4 reveals pure-prefix semantics.

*Update 2026-05-22:* Group Bm10 (`git status-x` under
`Bash(git status:*)` only — Denied) closes this. Word-boundary
tokenisation holds on the right side too: `Bash(git status:*)` does not
over-match `git status-x`.

### Group Bm — multi-word allow rule semantics (extends Group M; assumption #5)

Session B of the probe-pending runbook. Allow list = only
`Bash(git status:*)`; deny block keeps `Bash(git push:*)` etc. The
target was switched from `Bash(ls -la:*)` (original Group B) after
Session A confirmed `ls` is on the built-in safe list, which would
have allowed every `ls *` probe regardless of the multi-word rule.
Session Bf later found `git status` is *also* safe-listed (Bf17), so
the Allowed outcomes below are co-attributable to allow rule OR safe
list; the discriminating probes are the Denied ones.

| ID | Command | Expected | Empirical |
|---|---|---|---|
| Bm1 | `git status` | Allowed | Allowed (2026-05-22) — bare prefix; `:*` matches empty |
| Bm2 | `git status --short` | Allowed | Allowed (2026-05-22) — re-confirms M5 |
| Bm3 | `git status -s` | Allowed | Allowed (2026-05-22) |
| Bm4 | `git status --porcelain` | Allowed | Allowed (2026-05-22) |
| Bm5 | `git status --porcelain=v2` | Allowed | Allowed (2026-05-22) — `=` in arg fine |
| Bm6 | `git status --branch --short` | Allowed | Allowed (2026-05-22) — multiple flags after prefix |
| Bm7 | `git` (bare) | Denied | Denied (2026-05-22) — no allow rule for bare `git`, not safe-listed |
| Bm8 | `git log` | Denied if not safe-listed | **Allowed** (2026-05-22) — surprise; investigated in Group Bg (`git log` is on the built-in git safe list) |
| Bm9 | `git stat` (truncated subcommand) | Denied | Denied (2026-05-22) — word-boundary on the `status` token |
| Bm10 | `git status-x` (glued suffix) | Denied | Denied (2026-05-22) — `:*` only consumes tokens after a real whitespace boundary; closes Group M's "known limit" |
| Bm11 | `gitstatus` (no space) | Denied | Denied (2026-05-22) — first-token boundary holds |
| Bm12 | `git status .` (cwd-relative arg) | Allowed | Allowed (2026-05-22) |
| Bm13 | `git status README.md` | Allowed | Allowed (2026-05-22) |
| Bm14 | `git status /tmp` (outside-cwd absolute) | Denied by §2 | **Allowed** at the matcher (2026-05-22) — `git` rejected internally (`fatal: '/tmp' is outside repository`). §2 path-locality does NOT fire for `git status`. Falsifies the "content-aware §2" reading; the gate is on a hard-coded command list — see Findings §2 update. |
| Bm15 | `git status /home/ubuntu/data/local/orchestrate-ralph/.claude/worktrees/probe-pending/README.md` | Allowed | Allowed (2026-05-22) — absolute inside-cwd |
| Bm16 | `git -c color.ui=never status` (flag BEFORE subcommand) | unknown | **Denied** (2026-05-22) — matcher requires the multi-word prefix at positions 0/1 of argv; an inserted flag breaks the match. The matcher tokenises positionally, not via argv parsing. |
| Bm17 | `git push --help` (deny rule control) | Denied (deny) | Denied (2026-05-22) — deny rule fires; explicit "with command git push --help" message form distinguishes deny-rule from missing-allow denials |

**Conclusions (Group Bm):**

- `:*` after a multi-word allow accepts arbitrary suffix tokens including flags, `=`-suffixed flags, and multiple flags in sequence (Bm1–Bm6).
- Word boundaries are strict on both sides — left of the first space (Bm9, Bm11) and right of the second token (Bm10).
- §2 path-locality is **command-specific**, not content-aware (Bm14). Git escapes the gate even with an outside-cwd absolute path.
- Multi-word allow rules are **position-locked at argv positions 0/1** (Bm16). A leading flag like `git -c <X> status` does not match `Bash(git status:*)`.

### Group Bg — built-in git safe list (Session Bf)

Session Bf followup to Bm8. Same config as Session A (allow =
`Bash(echo:*)` only). Probes which git subcommands run with no
git-related allow rule present — i.e., which are on a built-in safe
list analogous to the Bash command safe list (Findings §1).

Rather than a full per-probe table (45 probes), the table below
summarises by outcome class.

| Class | Subcommands (probe IDs) | Outcome |
|---|---|---|
| Read-shape, safe-listed | `log`, `log --oneline …`, `log --grep …`, `diff`, `diff HEAD`, `show`, `show HEAD`, `blame <path>`, `reflog`, `describe`, `rev-parse`, `rev-parse --show-toplevel`, `ls-files`, `status`, `for-each-ref`, `stash list`, `worktree list`, `cat-file -p <ref>` (Bf1–Bf16, Bf17, Bf21, Bf23, Bf24, Bf25) | **Allowed** (2026-05-22) |
| Read-shape, dual-mode (bare/option-only allowed; positional name denied) | `branch` Allowed; `branch --list` Allowed; `branch <name>` Denied. `tag` Allowed; `tag <name>` Denied. (Bf8–Bf10 Allowed vs Bf31, Bf32 Denied.) | mixed — safe list discriminates the read form from the create form by argument shape |
| Read-shape, NOT safe-listed | `config --list`, `config <key>`, `symbolic-ref HEAD`, `hash-object <path>` (Bf18, Bf19, Bf20, Bf22) | **Denied (allow rule missing)** (2026-05-22) — surprise denies; pure reads but not on the safe list. Workers reading config must add `Bash(git config:*)` to allow. |
| Write-shape, expected denied | `add`, `commit -m`, `rm --dry-run`, `reset`, `stash push`, `checkout`, `restore` (Bf26–Bf30, Bf33, Bf34) | Denied (allow rule missing) (2026-05-22) — matcher decides before `--dry-run` is parsed; second-word semantics |
| Outside-cwd path arg | `log /tmp`, `diff /etc/passwd`, `blame /etc/issue`, `ls-files /tmp`, `log -- /tmp`, `show :/etc/passwd` (Bf35–Bf40) | **Allowed at the matcher** (2026-05-22) — git rejects internally; §2 does not fire. Matches Bm14 finding. |
| Deny-block, expected denied | `push --help`, `fetch --dry-run`, `pull --rebase`, `remote -v`, `ls-remote` (Bf41–Bf45) | Denied (deny rule) (2026-05-22) — distinct deny-rule message form ("with command \<X\> has been denied") |
| First-token shape control | `/usr/bin/git log` (Bonus) | Denied (allow rule missing) (2026-05-22) — first-token-shape gate (§3) intact; safe list applies only to bare `git` |

**Conclusions (Group Bg):**

- A **built-in git safe list** exists, parallel to the Bash command safe list. It covers most porcelain reads plus a few plumbing reads (notably `cat-file`, `for-each-ref`, `rev-parse`, `ls-files`) but not all (`symbolic-ref`, `hash-object`, all `config` forms are excluded).
- **`git cat-file -p <ref>`** is the most security-relevant entry — it dumps the contents of any object reachable from a ref, with no allow rule required. A worker can read every committed file by ref-walking. The path-guard hook covers `Write`/`Edit`/`NotebookEdit` but not subprocess reads, so this is not a hook-mitigable surface. Worth flagging in worker doctrine if any guarantee is being made about "worker can't see <X>" — the right answer is "ref-reachable contents are visible to any worker".
- The dual-mode subcommands (`git branch`, `git tag`) suggest the safe list is constructed by *(subcommand, arg-shape)* tuples rather than a flat set of subcommand names. The matcher knows `git branch` with no positional name is a read; `git branch <name>` is a create.
- `--dry-run` does NOT exempt write-shape subcommands. The matcher decides before flag parsing. Workers cannot use `--dry-run` to probe what a write would do under a restrictive config.
- §2 path-locality is **not git-aware**. Outside-cwd paths pass the matcher for any safe-listed git subcommand; git's own "outside repository" check catches the obvious cases, but that's git's check, not the matcher's. A subcommand that didn't enforce outside-repo (or that read absolute paths transparently) would have access.
- The first-token shape gate (Findings §3) remains intact: the safe list applies only to bare `git`. `/usr/bin/git log` denies — confirms the gate is independent of which command's safe list would apply.

## Findings from the 2026-05-20 run

Two cross-cutting behaviours surfaced that no single test row captures
cleanly. Both contradict assumptions the doctrine relies on; both
warrant doctrine patches.

### 1. Built-in safe-command list (bypasses the allow list)

A set of read-only commands run successfully under `dontAsk` even when
they have no allow-rule. The 2026-05-22 Session A run (allow = only
`Bash(echo:*)`) expanded the catalog significantly. Confirmed members:

- **Identity / environment:** `whoami`, `pwd`, `id`, `uname`, `date`,
  `date +%Y`, `hostname`, `groups`, `uptime`, `ps`, `ps aux`, `free`,
  `df`, `du`.
- **Path / metadata (no content read):** `test`, `realpath`, `readlink`,
  `dirname`, `basename`.
- **Content-reading (subject to §2):** `cat`, `head`, `tail`, `wc`,
  `grep` (`ugrep` on this host), `find` (`bfs` on this host), `stat`,
  `ls`. These run iff every positional path arg is inside `realpath(cwd)`
  — the §2 gate fires on outside-cwd args before the safe-list check
  has any effect.
- **Trivial output / arithmetic:** `echo`, `printf`, `true`, `false`,
  `seq`, `expr`. (`echo` and `printf` confirmed 2026-05-22 via Session
  C's Cs1–Cs3 — bare and with-arg shapes both run with no rule. Note: in
  Session A and earlier, `Bash(echo:*)` rule attributions were
  *redundant* with the safe list — both admitted echo simultaneously.
  The Session A conclusions about pipe decomposition still hold because
  the load-bearing falsifications used `env` (R19), which is genuinely
  not safe-listed.)
- **Tool location:** `which`, `type`.

Confirmed **denied** without a rule:

- **Environment leaks:** `env`, `printenv`, `printenv PATH`.
- **Mutating filesystem:** `mkdir`, `rm`, `rmdir`.
- **Session metadata:** `tty`, `who`, `w`, `hostnamectl`,
  `claude --version`, `command -v`, `hash`.
- **Pipeline sources:** `yes` (Session C Cs4 confirmed bare yes Denied —
  which is why `yes | head -1` is Denied even though `head` is
  safe-listed; every stage must clear, see Findings §3 and assumption
  row #3). `yes` is the canonical *non-safe-listed token* to use as a
  negative control when a probe needs an unambiguous allow-rule
  attribution.

So "allow list" is `template allow ∪ Claude-Code's built-in safe list`,
and the safe list is wider than initially thought — most common
read-only Unix utilities (~25 commands) are on it. The built-in list is
not documented; treat it as opaque and re-probe after version bumps.
Aliases matter: `grep`→`ugrep` and `find`→`bfs` on the Linux build used
here; flag semantics differ from GNU coreutils.

Doctrine impact: any reasoning that says "if I don't allow X, the
worker can't run X" is wrong for the safe-list commands. In particular:

- `Bash(date +%s)` and `Bash(test:*)` in
  `setup-ralph/templates/settings.template.json` are dead weight — both
  commands run regardless.
- `Bash(cat:*)`, `Bash(head:*)`, `Bash(tail:*)`, `Bash(grep:*)`,
  `Bash(find:*)`, `Bash(ls:*)` are also dead weight *for any path
  inside the worktree* — the safe list covers them. They ARE still
  load-bearing as "explicit permission to use this command across the
  full argument shape the worker constructs" — but per §2 even the
  explicit `Bash(<cmd>:*)` rule cannot reach outside `realpath(cwd)`,
  so the template entries don't unlock outside-cwd access either.

**There is a second built-in safe list scoped to `git` subcommands**,
parallel to the Bash command safe list. The 2026-05-22 Session Bf
enumeration (Group Bg) is the dedicated probe. Summary:

- **Safe-listed git subcommands** (run with no `Bash(git:*)` rule):
  `log`, `diff`, `show`, `blame`, `reflog`, `describe`, `rev-parse`,
  `ls-files`, `status`, `cat-file`, `for-each-ref`, `stash list`,
  `worktree list`. Plus `branch` and `tag` in bare or option-only
  shape (`branch <name>` and `tag <name>` are denied).
- **Read-shape git subcommands NOT safe-listed:** `config` (all
  forms), `symbolic-ref`, `hash-object`. A worker that needs config
  values must add `Bash(git config:*)` explicitly.
- **`git cat-file -p <ref>` is the standout exposure** — it dumps the
  contents of any object reachable from a ref, with no allow rule
  required and the path-guard hook does not cover subprocess reads.
  Worker doctrine should treat ref-reachable contents as visible to
  any worker.
- **§2 path-locality does NOT fire** for any safe-listed git
  subcommand. `git status /tmp` and similar pass the matcher; git's
  own "outside repository" check is the only thing catching obvious
  cases.

### 2. Argument path-locality gate (stricter than `:*` suggests)

`Bash(<cmd>:*)` does NOT match every suffix. The matcher rejects
command shapes whose **argument tokens** reference absolute paths
outside `realpath(cwd)`, or contain unexpanded `$VAR` references, even
when the command name and explicit allow rule match. The gate is
**general across multiple content-reading commands**, not specific to
`ls`. Confirmed on 2026-05-20:

| Command | Outside cwd | Inside cwd |
|---|---|---|
| `ls` | Denied (`/tmp`, `/usr/bin`, `/etc`, `/home` (ancestor), `/`) | Allowed (`.`, `README.md`, `docs`, `/home/ubuntu/data/local/orchestrate-ralph`) |
| `cat` | Denied (`/etc/issue`) | Allowed (`/home/.../README.md`) |
| `head` | Denied (`/etc/issue`) | (pattern fits) |
| `tail` | Denied (`/etc/issue`) | (pattern fits) |
| `grep` | Denied (`grep ubuntu /etc/passwd`) | Allowed (`grep -l permission /home/.../docs/permission-matcher-tests.md`) |
| `find` | Denied (`find /tmp …`) | Allowed (`find /home/.../docs -name "*.md"`) |
| `echo > path` | Denied (`echo hello > /tmp/x`) | (not probed) |
| **`test`** | **Allowed** (`test -f /etc/issue`, `test -r /etc/shadow`, `test -f /etc/passwd && echo yes`) | Allowed |

Plus the `$VAR` shape:

- `echo $HOME` — Denied
- `echo \$HOME` — Allowed

The gate fires on any literal absolute path not contained by
`realpath(cwd)` — ancestor paths like `/home` are rejected too, not
just sibling paths — and on any token starting with `$` that the
shell would expand. Quoting alone does not suppress (`echo "$HOME"`
would presumably still be Denied, untested), but escaping the `$` does.

**The gate is command-specific, not derived from a content property.**
The 2026-05-22 Session A re-probe and Session B Bm14 together rule out
the "content-aware" framing. Content-reading utilities (`cat`, `head`,
`tail`, `wc`, `grep`, `find`, `stat`, `ls`) all trip the gate; pure
metadata / string commands (`test`, `realpath`, `readlink`, `dirname`,
`basename`) bypass it; but `git status /tmp` (Bm14) and every other
safe-listed git subcommand with an outside-cwd path arg
(Bf35–Bf40) **also bypass** the gate, even though git CAN read content.
So the gate fires on a hard-coded list of commands the matcher knows
have path-typed positional args, not on any property derived from
what the command does at runtime.

Practical list:

| Fires §2 (outside-cwd args rejected) | Bypasses §2 (outside-cwd args allowed by matcher) |
|---|---|
| `cat`, `head`, `tail`, `wc`, `grep` (ugrep), `find` (bfs), `stat`, `ls`, `rmdir` | `test`, `realpath`, `readlink`, `dirname`, `basename`, `git <safe-listed subcmd>`, any explicitly allowlisted shape not on the §2 list |

`rmdir` was confirmed on the §2 list 2026-05-22 (Cf4 `rmdir /tmp/...` Denied even with `Bash(rmdir:*)` explicitly allowed; Cf2/Cf3 cwd-relative + inside-cwd absolute Allowed). So **§2 fires for both safe-listed AND explicitly-allowlisted path-typed commands** — the gate is independent of whether the command is on the safe list; it gates on the command-name+arg-shape regardless of how the command gained its allow.

A worker under the strictest allowlist can still enumerate `realpath`,
`dirname`, etc., and can use the git safe list (`git log`,
`git cat-file -p <ref>`) to dump ref-reachable contents from anywhere.
Doctrine should note this if any guarantee is being made about
"worker can't see outside its worktree."

**§2 fires per pipeline stage**, not just on the leading command. The
2026-05-22 R23 probe — `echo hello | cat /etc/issue` — was Denied,
because `cat`'s argument `/etc/issue` resolves outside cwd. The
matcher decomposes the pipeline and applies §2 to every stage's
arguments independently. This is the same per-stage rule confirmed for
assumption #3 (pipes / `&&` / `;` all decompose).

Doctrine impact: the "Bash command shape" passages in `ORCHESTRATOR.md`
and `PROMPT.md` describe a coarse prefix matcher. The real matcher is
finer-grained and *also* enforces a path-locality rule that the
doctrine doesn't mention. Two follow-ups for the doctrine:

- Describe the path-locality gate explicitly so workers know that
  `cat /etc/passwd` won't be reachable through `Bash(cat:*)`.
- Stop relying on the "any positional arg works" reading of `:*` —
  it doesn't hold for paths outside the worktree.

### 3. Command-name shape gate (rejects path-bearing first tokens)

A separate gate from §2: the matcher also rejects any first token that
contains `/`, regardless of whether the path is inside or outside the
worktree. Confirmed on 2026-05-20 (Group N):

- `/usr/bin/git status` — Denied (despite `Bash(git:*)`)
- `/usr/bin/echo hello` — Denied (despite `Bash(echo:*)`)
- `/bin/ls` — Denied (despite `Bash(ls:*)`)
- `/usr/bin/whoami` — Denied (despite `whoami` on the built-in safe list)
- `/home/ubuntu/data/local/orchestrate-ralph/CONTEXT.md` — Denied (absolute path **inside** the worktree)
- `./CONTEXT.md` — Denied (relative path, leading `./`)

The N5 probe is the load-bearing one: an absolute path *inside* the
worktree is rejected as a first token, so this can't be the §2 gate
firing — the §2 gate would have let an inside-cwd path through. The
matcher uses the bare command-name token as the lookup key into the
allow rules and the safe list; any `/` in that token makes the lookup
miss.

So PROMPT.md:93–94's rule "Run commands bare, not by full path" is
**correct** — but the actual reason is the name-shape lookup, not "an
explicit path is a different, unrecognised shape" (which conflates two
distinct mechanisms). Doctrine should distinguish:

- **Don't write `/usr/bin/git`** — the *first token* must be a bare
  command name with no `/`.
- **Don't write `cat /etc/passwd`** — *argument tokens* must not be
  absolute paths outside the worktree.

These are independent. A worker can hit one without the other.

### 4. Top-level tools are auto-permitted under `dontAsk` except `Write` / `Edit`

The 2026-05-22 Session A run probed the top-level tools with none of
them in the allow list (only `Bash(echo:*)`). Outcome:

| Tool | Under `dontAsk` without allow | Evidence |
|---|---|---|
| `Write` | **Denied** (allow rule missing) | T2: probe-t2.txt inside worktree, generic "don't ask mode" denial |
| `Edit` | **Denied** (allow rule missing) | R26: small Edit on README.md, same denial template |
| `NotebookEdit` | **Allowed** by matcher | R27: matcher passes; call reaches NotebookEdit's own "read-before-write" precondition error |
| `Read` | **Allowed** | T3: CONTEXT.md returned in full |
| `Agent` | **Allowed** | T1: subagent dispatched and replied |
| `Glob` | Not observable | R24: not exposed in this Linux build (v2.1.117+ drops it for Bash `bfs`) |
| `Grep` | Not observable | R25: same — dropped for Bash `ugrep` |

The split is **mutating-text vs everything else**: `Write` and `Edit`
require explicit allow entries; `NotebookEdit`, `Read`, `Agent` are
auto-permitted. The denial template for `Write` / `Edit` is the same
generic "don't ask mode" string used for unallowlisted `Bash` calls,
suggesting all three are gated by the same matcher pass.

Doctrine impact:

- The template entries `Read`, `Agent` (and `Glob`, `Grep` on hosts
  that have them) are **not load-bearing** for enforcement. They are
  harmless and explicit, but a config that omits them gates exactly
  the same set of calls. `Write` and `Edit` ARE load-bearing —
  removing them disables the worker's primary tooling.
- **`NotebookEdit` is auto-permitted** and represents a write surface
  that a restrictive `dontAsk` config does NOT cover via the matcher.
  The orchestrate-ralph template's path-guard hook covers
  `NotebookEdit` (matcher = `Write|Edit|NotebookEdit`), so the loop is
  safe — but any reader copying the template piecemeal and omitting
  the hook would leak a write vector. Flag this when documenting
  `dontAsk` to external readers.
- **The path-guard hook is masked by the matcher for `Write` / `Edit`
  when those tools aren't in the allow list.** The matcher denies
  upstream; the hook never sees the call. The hook only earns its
  keep in configs where `Write` / `Edit` ARE allowed (the worker
  config). It is not generic `dontAsk` hardening — it is
  specifically the worker-enforcement complement to a matcher-allowed
  Write/Edit surface.

### 5. Command substitution stays denied (good news for the doctrine)

E5/E6 confirmed: `$(...)` and backtick wrappers do not bypass the
matcher. `echo $(whoami)` was Denied even though both `echo` (via the
explicit allow rule) and `whoami` (via the built-in safe list) are
individually permitted. Subshell expansion is treated as a distinct
shape and rejected.

This is the assumption that mattered most for the orchestrator's
worker-isolation story; it holds.

## Updating this doc

When you fill in an Empirical cell:

1. Record the result, the date, and the Claude Code version observed.
2. Compare against the row's Expected outcome.
3. If they differ, update the **assumptions table** at the top —
   change the Status, link to the test that falsified the assumption.
4. **Search the doctrine surface for any text that depended on the old
   behaviour.** Anywhere worker, orchestrator, setup, or repair prose
   describes matcher behaviour or names specific forbidden shapes is a
   candidate. Grep across the skill folders for matcher-related terms —
   `compound`, `pipe`, `redirect`, `subshell`, `allowlist`, `:*`,
   `dontAsk`, `safe list`, `arg-locality`. Doctrine that names
   mechanisms the catalog has falsified must be updated; doctrine that
   enumerates shapes the catalog has shown to work can be relaxed.
5. Patch the doctrine in the same change set as the test result. A
   falsified assumption left in the doctrine becomes the next bite —
   especially under the descriptive frame
   ([ADR 0005](adr/0005-descriptive-doctrine-after-the-matcher-catalog.md)),
   where doctrine accuracy is the optimisation target.