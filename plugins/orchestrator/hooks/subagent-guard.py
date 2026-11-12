#!/usr/bin/env python3
"""PreToolUse hook: enforces the subagent economy rules and the project settings
of the orchestrator plugin.

Rules, checked in this order:

1. `SendMessage` to a finished `orchestrator:implementer` with a long history
   (over CONTEXT_LIMIT tokens) or a long pause (over IDLE_LIMIT_SECONDS) is
   denied: start a new implementer with the next pass number.
2. `Agent` with `orchestrator:implementer` on `opus` is allowed only when the
   brief has a standalone line `Complexity: hard` or `Hard part: <files>` (an
   optional `- ` or `* ` bullet is accepted; `Hard part:` with nothing, `none`,
   `n/a`, a value starting with `<` or only punctuation does not count).
3. `Read` of an image from inside an `orchestrator:*` subagent other than
   `orchestrator:visual-checker` is denied. The main session and subagents of
   any other type may read images.
4. Every `orchestrator:*` `Agent` call needs an explicit `model`.
5. Every `orchestrator:*` call needs a brief line
   `Task directory: <home>/projects/<key>/tasks/<id>`. It gives the home and
   the project.
6. The project needs a valid `settings.json` (setup.md schema, instruction
   files present).
7. When the event carries `session_id`, an active run file in the home must
   list it under `Sessions`.
8. `orchestrator:scout`, `orchestrator:tester` and
   `orchestrator:visual-checker` are denied when switched off in `roles_off`.
9. A custom role call (its instruction path in the prompt, or a configured
   non-general-purpose `agent_type` as `subagent_type`) needs the configured
   `model`, and the configured `effort` when the call carries `effort`.
   Broken settings found from cwd (no `Task directory:` line) deny only a
   matching custom role call or a call from a session listed in an active run.
11. `Write`, `Edit`, `MultiEdit` or `NotebookEdit` of
    `<home>/projects/*/settings.json` (names compared without case): denied
    from a subagent; `Edit`/`MultiEdit`/`NotebookEdit` denied (rewrite the
    whole file); `Write` denied when the new content fails the settings check.

Any unexpected error allows the call: the hook must never break the session.
Every known bad state is an explicit deny with a reason that says how to fix it.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import orchestrator_settings as settings_lib
except Exception:  # fail open: rules 5-11 are skipped without the module
    settings_lib = None

CONTEXT_LIMIT = 200_000
IDLE_LIMIT_SECONDS = 60 * 60
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
IMPLEMENTER = "orchestrator:implementer"
PLUGIN_PREFIX = "orchestrator:"
VISUAL_CHECKER = ("orchestrator:visual-checker", "visual-checker")
OPTIONAL_ROLES = ("scout", "tester", "visual-checker")
SETUP_HINT = "run the setup interview (setup.md or /orchestrator:setup) before any subagent"
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
    if not isinstance(tool_input, dict):
        return
    subagent_type = str(tool_input.get("subagent_type") or "")
    prompt = str(tool_input.get("prompt") or "")
    if subagent_type.startswith(PLUGIN_PREFIX):
        check_plugin_agent(event, tool_input, subagent_type, prompt)
    elif settings_lib is not None:
        check_custom_role(event, tool_input, subagent_type, prompt)


def check_plugin_agent(event, tool_input, subagent_type, prompt):
    # Rule 4 (rule 2 before it covered only the implementer).
    model = str(tool_input.get("model") or "").lower()
    if not model:
        role = "An implementer" if subagent_type == IMPLEMENTER else subagent_type
        deny(f"{role} needs an explicit model: pass model and effort explicitly (see roles-and-models.md).")
    # Rule 2.
    if subagent_type == IMPLEMENTER and (model == "opus" or model.startswith("claude-opus")):
        if not HARD_MARKER.search(prompt):
            deny(
                "An implementer on opus is only for a hard task or a hard part. Add the standalone line "
                "'Complexity: hard' or 'Hard part: <files>' (as written in 01-plan.md) to the brief "
                "and limit the brief to those files. Otherwise start the implementer on sonnet."
            )
    if settings_lib is None:
        return
    # Rule 5.
    task = settings_lib.task_dir_from_brief(prompt)
    if task is None:
        found = settings_lib.task_dir_line(prompt)
        got = f" (found {found!r})" if found else ""
        deny(
            f"The brief has no task directory in the project layout{got}: start the brief with "
            "Task directory: <home>/projects/<key>/tasks/<id> (absolute path, see task-files.md)."
        )
    # Rule 6.
    project = task["project_dir"]
    path = settings_lib.settings_path(project)
    if not os.path.exists(path):
        deny(f"Project {task['project']} has no settings file {path}: {SETUP_HINT}.")
    data, errors = settings_lib.load_settings(project)
    if errors:
        deny(f"The settings file {path} is invalid: " + "; ".join(errors) + ". Fix it or re-run setup (/orchestrator:setup).")
    # Rule 7.
    session_id = event.get("session_id")
    if isinstance(session_id, str) and session_id:
        if not settings_lib.active_runs(task["home"], session_id):
            runs = os.path.join(task["home"], "projects", "<project-key>", "runs", "<run-id>.md")
            deny(
                f"This session ({session_id}) is not linked to an active run: add {session_id} to the "
                f"Sessions line of your run file ({runs}, with '- Status: active'), then repeat the call."
            )
    # Rule 8.
    role = subagent_type[len(PLUGIN_PREFIX):]
    if role in OPTIONAL_ROLES and role in (data.get("roles_off") or []):
        deny(
            f"{subagent_type} is switched off in roles_off of {path}: skip this role, "
            "or change the setting with /orchestrator:setup."
        )


def model_family(model):
    model = model.lower()
    for family in ("opus", "sonnet", "haiku"):
        if model == family or (model.startswith("claude-") and family in model):
            return family
    return model


def settings_for_call(event, prompt):
    """Settings of the project a non-plugin call belongs to, as a dict with
    `path`, `data`, `errors`, `home` and `via_cwd`, or None when the call is not
    tied to any project with settings."""
    task = settings_lib.task_dir_from_brief(prompt)
    if task is not None:
        project, home = task["project_dir"], task["home"]
        if not os.path.exists(settings_lib.settings_path(project)):
            return None
    else:
        cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else os.getcwd()
        repo = settings_lib.main_checkout(cwd)
        if not repo:
            return None
        home = settings_lib.find_home(cwd)
        project, error = settings_lib.project_dir(home, repo)
        if error:
            return {"path": None, "data": None, "errors": [error], "home": home, "via_cwd": True}
        if project is None:
            return None
    data, errors = settings_lib.load_settings(project)
    return {
        "path": settings_lib.settings_path(project),
        "data": data,
        "errors": errors,
        "home": home,
        "via_cwd": task is None,
    }


def matching_roles(data, subagent_type, prompt):
    """Custom roles of `data` that this call runs, by `agent_type` or by
    instruction path. Type-guarded, so it also works on invalid settings."""
    roles = data.get("custom_roles") if isinstance(data, dict) else None
    if not isinstance(roles, list):
        return []
    roles = [r for r in roles if isinstance(r, dict)]
    by_type = [
        r for r in roles
        if isinstance(r.get("agent_type"), str)
        and r["agent_type"] != settings_lib.GENERAL_PURPOSE
        and r["agent_type"] == subagent_type
    ]
    by_path = [
        r for r in roles
        if isinstance(r.get("instructions"), str) and r["instructions"] and r["instructions"] in prompt
    ]
    return by_type or by_path


def linked_session(event, home):
    session_id = event.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return False
    return bool(settings_lib.active_runs(home, session_id))


def check_custom_role(event, tool_input, subagent_type, prompt):
    # Rule 9.
    found = settings_for_call(event, prompt)
    if found is None:
        return
    path, data, errors = found["path"], found["data"], found["errors"]
    matched = matching_roles(data, subagent_type, prompt)
    if errors:
        # From cwd, broken settings block only a custom role call or a call
        # from a session that orchestrates a run; unrelated sessions go on.
        if found["via_cwd"] and not matched and not linked_session(event, found["home"]):
            return
        where = f"The settings file {path}" if path else "The project's settings file"
        deny(f"{where} is invalid: " + "; ".join(errors) + ". Fix it or re-run setup (/orchestrator:setup).")
    if not matched:
        return
    model = model_family(str(tool_input.get("model") or ""))
    has_effort = "effort" in tool_input
    effort = str(tool_input.get("effort") or "").lower()
    for role in matched:
        if model == role.get("model") and (not has_effort or effort == role.get("effort")):
            return
    wanted = ", ".join(f"{r.get('name')}: model {r.get('model')}, effort {r.get('effort')}" for r in matched)
    deny(
        f"A custom role call must use the model and effort from {path} ({wanted}). "
        "Pass both explicitly on the Agent call."
    )


def check_settings_write(event, tool):
    # Rule 11.
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str) or os.path.basename(target).lower() != settings_lib.SETTINGS_FILE:
        return
    target = os.path.abspath(os.path.expanduser(target))
    projects = os.path.dirname(os.path.dirname(target))
    if os.path.basename(projects).lower() != "projects":
        return
    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else os.getcwd()
    home = settings_lib.find_home(cwd)
    if os.path.realpath(os.path.dirname(projects)) != os.path.realpath(home):
        return
    if event.get("agent_type"):
        deny(f"Only the orchestrator writes {target}; a subagent must not change the settings.")
    if tool != "Write":
        deny(f"Do not {tool} {target}: rewrite the whole file with Write, so the hook can validate it.")
    try:
        data = json.loads(str(tool_input.get("content") or ""))
    except ValueError as error:
        deny(f"The new {target} is not valid JSON ({error}). Write one JSON object as setup.md describes.")
    errors = settings_lib.validate_settings(data) or settings_lib.check_instruction_paths(data)
    if errors:
        deny(
            f"The new {target} breaks the settings rules of setup.md: " + "; ".join(errors)
            + ". Write the instruction files first, then the settings."
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
        elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit") and settings_lib is not None:
            check_settings_write(event, tool)
    except SystemExit:
        raise
    except Exception:  # fail open: the hook must not break the session
        return


if __name__ == "__main__":
    main()
