#!/usr/bin/env python3
"""Step viewer for Ralph orchestrator worker sub-agents.

Turns the workers' transcripts into a compact step log — one line per tool
call (`Read x`, `Edit y`, `Bash <cmd>`), never the tool output, never
narration. Two modes:

    python3 watch-steps.py <repo-worktree-path>   # live tail (separate terminal)
    python3 watch-steps.py agent.output           # replay one transcript

This is for a human watching an orchestrator run from a separate terminal — it
is a plain process, not an agent, so nothing it reads or prints enters any
agent's context. The data is the workers' tool calls only; the raw
transcript's (huge) tool outputs are never read out.
"""
import glob
import json
import os
import sys
import time

POLL_SECONDS = 0.5


def tasks_pattern(project_dir):
    """Glob for the transcripts of the sub-agents dispatched from
    `project_dir`. The harness files them under a slug of the dispatching
    worktree's absolute path, with both `/` and `.` flattened to `-`."""
    uid = os.getuid()
    slug = os.path.abspath(project_dir).rstrip("/").replace("/", "-").replace(".", "-")
    return f"/private/tmp/claude-{uid}/{slug}/*/tasks/*.output"


def shorten(value, limit=72):
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def relpath(path):
    """Strip the absolute / worktree prefix so a file shows as its repo-relative
    path (`PROMPT.md`, `src/page.tsx`) rather than a long, truncated absolute
    path into some `worktrees/agent-xxxx/` checkout."""
    path = str(path)
    marker = "/worktrees/"
    cut = path.find(marker)
    if cut != -1:
        rest = path[cut + len(marker):]
        slash = rest.find("/")
        if slash != -1:
            return rest[slash + 1:]
    parts = path.rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) > 1 else path


def describe(tool, tool_input):
    tool_input = tool_input or {}
    if tool in ("Read", "Edit", "Write", "NotebookEdit"):
        return shorten(relpath(tool_input.get("file_path", "")))
    if tool == "Bash":
        return shorten(tool_input.get("command", ""))
    if tool in ("Grep", "Glob"):
        target = tool_input.get("pattern", "")
        if tool_input.get("path"):
            target += f"  in {tool_input['path']}"
        return shorten(target)
    if tool in ("Agent", "Task"):
        return shorten(tool_input.get("description", ""))
    for value in tool_input.values():
        if isinstance(value, str) and value.strip():
            return shorten(value)
    return ""


def find_tool_uses(node):
    """Recursively collect every (tool name, input) pair in a transcript event,
    robust to however the event nests its content blocks."""
    found = []
    if isinstance(node, dict):
        if node.get("type") == "tool_use":
            found.append((node.get("name", "?"), node.get("input")))
        for value in node.values():
            found.extend(find_tool_uses(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(find_tool_uses(value))
    return found


def worker_label(path):
    return os.path.basename(path)[:8]


def format_lines(label, raw):
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [
        f"  [{label}] {tool:9} {describe(tool, tool_input)}"
        for tool, tool_input in find_tool_uses(event)
    ]


def split_complete(data):
    """Split a byte chunk at its last newline: (complete lines, bytes consumed).
    A trailing partial line is left for the next read."""
    cut = data.rfind(b"\n")
    if cut == -1:
        return [], 0
    return [r.strip() for r in data[: cut + 1].split(b"\n") if r.strip()], cut + 1


def replay(path):
    print(f"[watch-steps] replaying {path}\n", flush=True)
    label = worker_label(path)
    with open(path, "rb") as handle:
        for raw in handle:
            for line in format_lines(label, raw.strip()):
                print(line, flush=True)


def watch(project_dir):
    pattern = tasks_pattern(project_dir)
    print(f"[watch-steps] watching {pattern}", flush=True)
    print("[watch-steps] waiting for the orchestrator to dispatch workers…\n", flush=True)
    # Files present at startup belong to earlier runs — skip their backlog.
    offsets = {p: os.path.getsize(p) for p in glob.glob(pattern)}
    while True:
        for path in sorted(glob.glob(pattern)):
            if path not in offsets:
                offsets[path] = 0
                print(f"\n── worker {worker_label(path)} ──", flush=True)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size <= offsets[path]:
                continue
            with open(path, "rb") as handle:
                handle.seek(offsets[path])
                data = handle.read()
            lines, consumed = split_complete(data)
            if not consumed:
                continue
            offsets[path] += consumed
            label = worker_label(path)
            for raw in lines:
                for line in format_lines(label, raw):
                    print(line, flush=True)
        time.sleep(POLL_SECONDS)


def main():
    args = sys.argv[1:]
    if args and os.path.isfile(args[0]):
        replay(args[0])
    else:
        watch(args[0] if args else ".")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[watch-steps] stopped.", flush=True)
