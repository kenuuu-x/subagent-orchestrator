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
10. One writer per worktree: an `orchestrator:implementer` or
    `orchestrator:tester` call or a writing custom role call (`writes: true`)
    needs a standalone `Worktree:` line, and is denied while an unfinished
    subagent of this session (not scout, planner, reviewer or visual-checker)
    has a brief with the same `Worktree:` line and was active in the last
    IDLE_LIMIT_SECONDS. Writers started in the same assistant message are not
    seen (none of them has a transcript yet).
11. `Write`, `Edit`, `MultiEdit` or `NotebookEdit` of
    `<home>/projects/*/settings.json` (names compared without case): denied
    from a subagent; `Edit`/`MultiEdit`/`NotebookEdit` denied (rewrite the
    whole file); `Write` denied when the new content fails the settings check.
    The target is resolved first (cwd, `~`, symlinks); the home is compared
    without case on a case-insensitive file system. The home is
    `find_home(cwd)` or a home that the project's repository names.
12. `Write`, `Edit`, `MultiEdit` or `NotebookEdit` from a read-only custom role
    (`writes: false`; found from `agent_id`, its transcript brief and the
    settings) outside its trusted task directory is denied. Bash writes are
    not covered.

Trusted home: rules 5-12 take the home from `find_home(event cwd)`. A brief's
`Task directory:` in another home is trusted only when the repository in that
project's settings names that home (`repo_names_home`). Any other home is
denied for `orchestrator:*` calls and ignored (cwd lookup instead) for other
calls.

Any unexpected error allows the call: the hook must never break the session.
Every known bad state is an explicit deny with a reason that says how to fix it.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import orchestrator_settings as settings_lib
except Exception:  # fail open: rules 5-12 are skipped without the module
    settings_lib = None

CONTEXT_LIMIT = 200_000
IDLE_LIMIT_SECONDS = 60 * 60
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
IMPLEMENTER = "orchestrator:implementer"
PLUGIN_PREFIX = "orchestrator:"
VISUAL_CHECKER = ("orchestrator:visual-checker", "visual-checker")
# Plugin roles that never write in a worktree; they do not hold the writer lock.
READ_ONLY_PLUGIN_ROLES = (
    "orchestrator:scout", "orchestrator:planner", "orchestrator:reviewer", "orchestrator:visual-checker",
)
# Plugin roles that write in a worktree; rule 10 checks their calls.
WRITING_PLUGIN_ROLES = {IMPLEMENTER: "An implementer", "orchestrator:tester": "A tester"}
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
    cwd = event_cwd(event)
    task, home = settings_lib.trusted_task(prompt, cwd)
    if task is None:
        found = settings_lib.task_dir_line(prompt)
        got = f" (found {found!r})" if found else ""
        deny(
            f"The brief has no task directory in the project layout{got}: start the brief with "
            "Task directory: <home>/projects/<key>/tasks/<id> (absolute path, see task-files.md)."
        )
    if not task["trusted"]:
        no_settings = ""
        if settings_lib.load_settings(task["project_dir"])[1]:
            no_settings = ", or that project has no valid settings.json yet: run /orchestrator:setup"
        deny(
            f"Task directory is outside the work home: {task['task_dir']} is not under {home}/projects, "
            f"and the repository in {task['project_dir']}/settings.json does not name {task['home']}. "
            f"The hook's work home for this session (cwd {cwd}) is {home}: start the session in the "
            f"repository whose CLAUDE.md names {task['home']}, or set SUBAGENT_ORCHESTRATOR_HOME"
            f"{no_settings}."
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
        homes = [task["home"]] + ([] if settings_lib.same_path(task["home"], home) else [home])
        if not any(settings_lib.active_runs(h, session_id) for h in homes):
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
    # Rule 10.
    if subagent_type in WRITING_PLUGIN_ROLES:
        check_one_writer(event, prompt, WRITING_PLUGIN_ROLES[subagent_type])


def event_cwd(event):
    cwd = event.get("cwd")
    return cwd if isinstance(cwd, str) and cwd else os.getcwd()


def first_user_text(transcript):
    """Text of the first user message of a transcript (a subagent's brief)."""
    try:
        with open(transcript, encoding="utf-8", errors="ignore") as lines:
            for line in lines:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "user":
                    continue
                content = (entry.get("message") or {}).get("content")
                if isinstance(content, list):
                    content = "\n".join(
                        str(part.get("text") or "") for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    )
                return content if isinstance(content, str) else ""
    except OSError:
        return ""
    return ""


def last_activity(transcript):
    """Time of the last timestamped entry (read from the tail), else mtime."""
    try:
        size = os.path.getsize(transcript)
        with open(transcript, "rb") as handle:
            handle.seek(max(0, size - 65536))
            tail = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        stamp = parse_time(entry.get("timestamp")) if isinstance(entry, dict) else None
        if stamp:
            return stamp
    try:
        return datetime.fromtimestamp(os.path.getmtime(transcript), timezone.utc)
    except OSError:
        return None


def subagent_dir(event):
    transcript = event.get("transcript_path")
    if not isinstance(transcript, str) or not transcript.endswith(".jsonl"):
        return None
    return os.path.join(transcript[: -len(".jsonl")], "subagents")


def busy_writer(event, worktree):
    """`(agent id, agent type, last activity)` of an unfinished subagent of
    this session whose brief has the same `Worktree:` line, or None."""
    folder = subagent_dir(event)
    try:
        names = sorted(os.listdir(folder)) if folder else []
    except OSError:
        return None
    caller = event.get("agent_id")
    now = datetime.now(timezone.utc)
    for name in names:
        if not (name.startswith("agent-") and name.endswith(".meta.json")):
            continue
        agent_id = name[len("agent-"): -len(".meta.json")]
        if agent_id == caller:
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                meta = json.load(handle)
        except (OSError, ValueError):
            continue
        agent_type = str(meta.get("agentType") or "") if isinstance(meta, dict) else ""
        if not isinstance(meta, dict) or meta.get("finished") is True or agent_type in READ_ONLY_PLUGIN_ROLES:
            continue
        transcript = os.path.join(folder, f"agent-{agent_id}.jsonl")
        other = settings_lib.brief_line(first_user_text(transcript), "Worktree")
        if not other or not settings_lib.same_path(other, worktree):
            continue
        stamp = last_activity(transcript) or now
        if (now - stamp).total_seconds() <= IDLE_LIMIT_SECONDS:
            return agent_id, agent_type or "unknown type", stamp
    return None


def check_one_writer(event, prompt, who):
    # Rule 10.
    worktree = settings_lib.brief_line(prompt, "Worktree")
    if not worktree or not os.path.isabs(os.path.expanduser(worktree)):
        deny(
            f"{who} writes in a worktree: add the standalone line 'Worktree: <absolute path>' to the "
            "brief, so the hook can keep one writer per worktree."
        )
    busy = busy_writer(event, worktree)
    if busy:
        agent_id, agent_type, stamp = busy
        limit = IDLE_LIMIT_SECONDS // 60
        idle = int((datetime.now(timezone.utc) - stamp).total_seconds() // 60)
        free = (stamp + timedelta(seconds=IDLE_LIMIT_SECONDS)).astimezone()
        deny(
            f"Only one writer per worktree: subagent {agent_id} ({agent_type}) of this session is still "
            f"working in {worktree} (last activity {clock(stamp)}, {idle} min ago). Wait for it to finish "
            f"or stop it. After a resume the old subagent is gone and cannot be stopped: wait until "
            f"{clock(free)} ({limit} min after its last activity), or ask the human."
        )


def clock(stamp):
    """Local time with offset, for deny reasons."""
    return stamp.astimezone().strftime("%Y-%m-%d %H:%M %Z")


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
    cwd = event_cwd(event)
    task, home = settings_lib.trusted_task(prompt, cwd)
    if task is not None and not task["trusted"]:
        task = None  # a task directory outside the trusted home: use the cwd lookup
    if task is not None:
        project = task["project_dir"]
        if not os.path.exists(settings_lib.settings_path(project)):
            return None
    else:
        repo = settings_lib.main_checkout(cwd)
        if not repo:
            return None
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
    fitting = [
        r for r in matched
        if model == r.get("model") and (not has_effort or effort == r.get("effort"))
    ]
    if not fitting:
        wanted = ", ".join(f"{r.get('name')}: model {r.get('model')}, effort {r.get('effort')}" for r in matched)
        deny(
            f"A custom role call must use the model and effort from {path} ({wanted}). "
            "Pass both explicitly on the Agent call."
        )
    # Rule 10.
    writers = [r for r in fitting if r.get("writes") is True]
    if writers:
        check_one_writer(event, prompt, f"The writing custom role {writers[0].get('name')}")


def check_read_only_role_write(event, tool_input):
    # Rule 12.
    agent_id = event.get("agent_id")
    agent_type = str(event.get("agent_type") or "")
    folder = subagent_dir(event)
    if not isinstance(agent_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", agent_id) or not folder:
        return
    if agent_type.startswith(PLUGIN_PREFIX):
        return
    brief = first_user_text(os.path.join(folder, f"agent-{agent_id}.jsonl"))
    if not brief:
        return
    found = settings_for_call(event, brief)
    if found is None or not isinstance(found["data"], dict):
        return
    matched = matching_roles(found["data"], agent_type, brief)
    if not matched or any(r.get("writes") is not False for r in matched):
        return
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str) or not target:
        return
    cwd = event_cwd(event)
    task, _ = settings_lib.trusted_task(brief, cwd)
    if task is not None and task["trusted"] and settings_lib.is_inside(target, task["task_dir"], cwd):
        return
    names = ", ".join(str(r.get("name")) for r in matched)
    where = task["task_dir"] if task is not None and task["trusted"] else (
        "its task directory (its brief has no Task directory line in the work home)"
    )
    deny(
        f"The custom role {names} is read-only (writes: false in {found['path']}): it writes only "
        f"inside {where}, not {target}. Put its notes into <task dir>/custom-<name>-N.md."
    )


def check_settings_write(event, tool):
    # Rule 11.
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str) or not target:
        return
    # Resolve first (cwd, ~, symlinks), then check the name, so a symlink or a
    # case variant of the home cannot hide the settings file.
    cwd = event_cwd(event)
    target = os.path.realpath(os.path.join(cwd, os.path.expanduser(target)))
    if os.path.basename(target).lower() != settings_lib.SETTINGS_FILE:
        return
    projects = os.path.dirname(os.path.dirname(target))
    if os.path.basename(projects).lower() != "projects":
        return
    home = os.path.dirname(projects)
    if not settings_lib.same_path(home, settings_lib.find_home(cwd)) and not written_home_named(
        os.path.dirname(target), tool_input
    ):
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


def written_home_named(project, tool_input):
    """Rule 11 outside the cwd home: the home counts when the repository in
    the present settings file or in the new content names it."""
    if settings_lib.repo_names_home(project):
        return True
    try:
        data = json.loads(str(tool_input.get("content") or ""))
    except ValueError:
        return False
    repo = data.get("repo") if isinstance(data, dict) else None
    return isinstance(repo, str) and settings_lib.repo_names_home(project, repo)


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
            if isinstance(event.get("tool_input"), dict):
                check_read_only_role_write(event, event["tool_input"])
    except SystemExit:
        raise
    except Exception:  # fail open: the hook must not break the session
        return


if __name__ == "__main__":
    main()
