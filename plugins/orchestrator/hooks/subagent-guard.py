#!/usr/bin/env python3
"""PreToolUse hook: enforces the subagent economy rules of the orchestrator plugin.

Three rules:

1. `SendMessage` to a finished `orchestrator:implementer` with a long history
   (over CONTEXT_LIMIT tokens) or a long pause (over IDLE_LIMIT_SECONDS) is
   denied: start a new implementer with the next pass number.
2. `Agent` with `orchestrator:implementer` is denied without an explicit
   `model`. On `opus` it is allowed only when the brief has a standalone line
   `Complexity: hard` or `Hard part: <files>` (an optional `- ` or `* ` bullet
   is accepted; `Hard part:` with nothing, `none`, `n/a`, a value starting with `<` or only
   punctuation does not count).
3. `Read` of an image from inside an `orchestrator:*` subagent other than
   `orchestrator:visual-checker` is denied. The main session and subagents of
   any other type may read images.

Any unexpected error allows the call: the hook must never break the session.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

CONTEXT_LIMIT = 200_000
IDLE_LIMIT_SECONDS = 60 * 60
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
IMPLEMENTER = "orchestrator:implementer"
PLUGIN_PREFIX = "orchestrator:"
VISUAL_CHECKER = ("orchestrator:visual-checker", "visual-checker")
HARD_MARKER = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?"
    r"(?:Complexity:[ \t]*hard\b|Hard part:[ \t]*(?!(?:none|n/a)[ \t]*$)(?!<)(?![^\w\s]+[ \t]*$)\S)",
    re.IGNORECASE | re.MULTILINE,
)


def deny(reason):
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def parse_time(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def last_turn(transcript):
    """Context size and time of the last assistant message in a transcript."""
    context, stamp = 0, None
    with open(transcript, encoding="utf-8", errors="ignore") as lines:
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "assistant":
                continue
            usage = (entry.get("message") or {}).get("usage") or {}
            size = (
                usage.get("input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0)
            )
            if size:
                context = size
            stamp = parse_time(entry.get("timestamp")) or stamp
    return context, stamp


def check_send_message(event):
    target = str((event.get("tool_input") or {}).get("to") or "")
    transcript = event.get("transcript_path") or ""
    if not re.fullmatch(r"[0-9a-f]{8,}", target) or not transcript.endswith(".jsonl"):
        return
    base = os.path.join(transcript[: -len(".jsonl")], "subagents", "agent-" + target)
    try:
        with open(base + ".meta.json", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        return
    if meta.get("agentType") != IMPLEMENTER or meta.get("finished") is not True:
        return
    context, stamp = last_turn(base + ".jsonl")
    idle = (datetime.now(timezone.utc) - stamp).total_seconds() if stamp else 0
    if context > CONTEXT_LIMIT:
        why = f"its history is {context // 1000}k tokens (limit {CONTEXT_LIMIT // 1000}k)"
    elif idle > IDLE_LIMIT_SECONDS:
        why = f"it has been idle for {int(idle // 60)} min (limit {IDLE_LIMIT_SECONDS // 60} min)"
    else:
        return
    deny(
        f"Do not continue this implementer: {why}. Continuing re-reads its whole history. "
        "Start a new orchestrator:implementer with the next pass number. It starts from "
        "state.md, 01-plan.md, all changes-*.md, the latest review-N.md and the worktree diff."
    )


def check_agent(event):
    tool_input = event.get("tool_input") or {}
    if tool_input.get("subagent_type") != IMPLEMENTER:
        return
    model = str(tool_input.get("model") or "").lower()
    if not model:
        deny("An implementer needs an explicit model: pass model and effort explicitly (see roles-and-models.md).")
    if not (model == "opus" or model.startswith("claude-opus")):
        return
    if HARD_MARKER.search(str(tool_input.get("prompt") or "")):
        return
    deny(
        "An implementer on opus is only for a hard task or a hard part. Add the standalone line "
        "'Complexity: hard' or 'Hard part: <files>' (as written in 01-plan.md) to the brief "
        "and limit the brief to those files. Otherwise start the implementer on sonnet."
    )


def check_read(event):
    agent_type = str(event.get("agent_type") or "")
    if not agent_type.startswith(PLUGIN_PREFIX) or agent_type in VISUAL_CHECKER:
        return
    path = str((event.get("tool_input") or {}).get("file_path") or "").lower()
    if not path.endswith(IMAGE_EXTENSIONS):
        return
    deny(
        "This role must not open images: every screenshot stays in its history and is re-read "
        "on every step. List the path under 'Screenshots' in changes-N.md; "
        "orchestrator:visual-checker looks at it when the orchestrator starts it."
    )


def main():
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return
        tool = event.get("tool_name")
        if tool == "SendMessage":
            check_send_message(event)
        elif tool == "Agent":
            check_agent(event)
        elif tool == "Read":
            check_read(event)
    except SystemExit:
        raise
    except Exception:  # fail open: the hook must not break the session
        return


if __name__ == "__main__":
    main()
