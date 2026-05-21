# Group M — probe runbook

Procedure for running Group M in
[`../permission-matcher-tests.md`](../permission-matcher-tests.md) and
filling in its Empirical column. Three sessions, three settings — claude
reads `.claude/settings.local.json` at startup only, so the file is
swapped between sessions and claude is restarted each time.

The default settings (template) cover **M0, M1, M2**. M4 and M5 each
need a dedicated allowlist ([`m4-settings.json`](m4-settings.json) /
[`m5-settings.json`](m5-settings.json)) so the test is discriminating
— so an Allowed outcome can be attributed unambiguously to the rule
under test rather than to a broader rule.

**Safety rule for any probe added here:** no probe may have a real-world
side effect even in the failure mode where the matcher unexpectedly
Allows. `git push --help` is intercepted before any network call;
`git status` family is read-only; `rmdir --help` is a no-op.

**Sessions B and C ship minimal allow lists** (Read + the probe binary
only — no Edit / Write), so claude in those sessions cannot record
results into the catalog directly. Run each probe, note the outcome
verbatim, and defer the catalog update to a final default-template
session that has `Edit` back. The "Recording results" section at the
bottom is the consolidated catalog update step.

---

## Setup — fresh probe worktree

Before Session A, set up a disposable worktree off the current doctrine
branch:

```
git worktree add <disposable-path> -b probe-group-m-<date>
cd <disposable-path>
mkdir -p .claude .ralph
cp setup-ralph/templates/settings.template.json .claude/settings.local.json
cp setup-ralph/templates/hook-path-guard.py .ralph/hook-path-guard.py
```

`docs/probes/` (this runbook + the probe settings files) is already on
disk via the worktree checkout.

---

## Session A — default template (probes M0, M1, M2)

The `.claude/settings.local.json` placed during worktree setup is the
default template. Confirm by spot-checking it has both
`Bash(git push:*)` in `deny` and `Bash(git:*)` in `allow`.

1. Launch claude in this worktree.
2. Confirm enforcement: dispatch a single bare `Bash` call `cd .`. Must
   error with "Denied by permissions" and no prompt. If it prompts or
   succeeds, the session is not enforced — exit, re-launch, retry.
3. Run each probe as a bare `Bash` tool use, one at a time, recording
   the outcome:

   - **M0** — `rmdir --help`. Expected: Denied. Confirms `rmdir` is NOT
     on the safe list. If Allowed, M4 is uninterpretable and a different
     binary pair is needed.
   - **M1** — `git push --help`. Expected: Denied. Confirms multi-word
     deny `Bash(git push:*)` matches a `git push <suffix>` shape.
     `--help` is intercepted by git before any network call.
   - **M2** — `git status`. Expected: Allowed. Confirms multi-word deny
     doesn't over-match unrelated `git` subcommands.

4. Session A has `Edit` under the default template — fill in the Empirical
   column for M0, M1, M2 in `docs/permission-matcher-tests.md` with the
   result, date, and Claude Code version observed. (Sessions B and C
   cannot do this, so anything you can record here saves work later.)
5. Exit claude.

---

## Session B — M4 settings (the disambiguation probe)

1. From a shell in this worktree:

   ```
   cp docs/probes/m4-settings.json .claude/settings.local.json
   ```

2. Launch claude in this worktree.
3. Confirm enforcement (`cd .` denies).
4. Run **M4** — `rmdir --help`. Two possible outcomes:

   - **Denied** → matcher tokenises on word boundary. `Bash(rm:*)` does
     not over-match `rmdir`. Existing `Bash(<short>:*)` rules are scoped
     as expected. Doctrine stands.
   - **Allowed** → matcher does pure literal-prefix matching. Every
     short-name `:*` rule is broader than it looks; `Bash(rm:*)` would
     allow `rmdir`, `rmlink` if it existed, etc. Doctrine and template
     need a security-relevant patch.

5. Note the M4 outcome (Denied or Allowed) verbatim and any follow-up
   implications. Catalog update is deferred — Session B's allow list has
   no `Edit`, so the catalog change happens in the final default-template
   session (see "Recording results" below).
6. Exit claude.

---

## Session C — M5 settings (multi-word allow accepts suffix)

1. From a shell in this worktree:

   ```
   cp docs/probes/m5-settings.json .claude/settings.local.json
   ```

2. Launch claude in this worktree.
3. Confirm enforcement.
4. Run **M5** — `git status --short`. Expected: Allowed. Because the
   allowlist has ONLY `Bash(git status:*)` (no `Bash(git:*)`), an
   Allowed outcome can only be attributed to the multi-word rule.

5. Note the M5 outcome verbatim. Catalog update is deferred — same as
   Session B, the minimal allow list has no `Edit`.
6. Exit claude.

---

## Recording results — restore the default template and update the catalog

Sessions B and C ran without `Edit`, so M4 and M5 results — and any
M0/M1/M2 results Session A didn't get to — land here.

1. From a shell in this worktree, restore the default template so the
   next session has `Edit` again:

   ```
   cp setup-ralph/templates/settings.template.json .claude/settings.local.json
   ```

2. Launch claude in this worktree (or dispatch an edit-capable agent
   into the doctrine worktree where the catalog is git-tracked).
3. Edit `docs/permission-matcher-tests.md` to fill in the Empirical
   cells for M0–M5 and update the Status column of assumptions #12 and
   #13 accordingly. Then follow the catalog's "Updating this doc"
   step 4 — grep the skill folders for matcher-related terms
   (`compound`, `pipe`, `redirect`, `subshell`, `allowlist`, `:*`,
   `dontAsk`, `safe list`, `arg-locality`) and patch any doctrine that
   depended on the old assumption status. Land the doctrine patch in
   the same change set as the empirical results.
4. The probe worktree itself can be removed when done:

   ```
   git worktree remove <probe-worktree-path>
   git branch -d probe-group-m-<date>
   ```
