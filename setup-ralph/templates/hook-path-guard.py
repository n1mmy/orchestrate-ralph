#!/usr/bin/env python3
"""PreToolUse path-guard hook for the Ralph loop.

A worker sub-agent runs with `isolation: "worktree"`, which isolates its git
branch and index but NOT the filesystem — `Write` / `Edit` / `NotebookEdit` can
target any absolute path the OS permits. This hook is the filesystem guard: it
denies any of those calls whose target resolves outside the worktree the call
runs in.

Wired by `.ralph/settings.json` under `hooks.PreToolUse`. Reads the hook event
JSON on stdin. On a violation it prints a deny decision and exits 0; otherwise
it exits 0 silently so normal permission processing continues.

Fail-open by design: if the event cannot be parsed or the worktree root cannot
be resolved, the hook does not block. A crashing guard must never wedge an
unattended run — step-5 detection in ORCHESTRATOR.md remains the backstop.
"""
import json
import os
import subprocess
import sys

GUARDED = {"Write", "Edit", "NotebookEdit"}

# Extra absolute paths a worker may write to, beyond its own worktree. Empty by
# default. Add a directory here — e.g. "/data/shared" — to let workers write a
# shared location the worktree boundary would otherwise deny. This list is the
# ONLY part of this file meant to be edited; the guard logic below is not.
# `setup-ralph` repair mode edits this list. Each entry is matched with the
# same boundary care as the worktree root: the path itself, or a child under
# it — never a bare prefix.
EXTRA_ALLOWED_ROOTS = []


def deny(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.exit(0)


def main():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if event.get("tool_name", "") not in GUARDED:
        sys.exit(0)

    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        sys.exit(0)

    cwd = event.get("cwd") or os.getcwd()

    # The worktree root is the boundary. Derive it from the call's cwd, so the
    # hook is correct per-worker wherever the script itself happens to live.
    try:
        root = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        root = ""
    if not root:
        root = cwd

    # realpath resolves symlinks and `..` for existing components and appends
    # the rest literally, so a `../..` climb cannot slip past the comparison.
    abs_target = target if os.path.isabs(target) else os.path.join(cwd, target)
    real_target = os.path.realpath(abs_target)
    real_root = os.path.realpath(root)

    # The worktree root is the boundary; EXTRA_ALLOWED_ROOTS widens it. Every
    # allowed root is matched the same way — the path itself or a child under
    # it (the `+ os.sep` stops `/data/shared` matching `/data/shared-evil`).
    for allowed in [real_root] + [os.path.realpath(p) for p in EXTRA_ALLOWED_ROOTS]:
        if real_target == allowed or real_target.startswith(allowed + os.sep):
            sys.exit(0)

    deny(
        f"Path-guard: {event['tool_name']} targets {real_target}, outside this "
        f"worktree ({real_root}). A Ralph worker writes only inside its own "
        f"worktree — address project files by worktree-relative paths."
    )


if __name__ == "__main__":
    main()
