#!/usr/bin/env python3
"""UserPromptSubmit and SessionStart hook: re-injects the project settings of
an orchestrator run into the context.

- Only a session listed under `Sessions` in an active run file of a trusted
  work home gets context: `find_home(cwd)`, and for a cwd outside any
  repository also the homes that the repositories directly under it name in
  their CLAUDE.md (a run there counts only when its project's repository names
  that home, as in the guard). Ordinary sessions get nothing.
- UserPromptSubmit (every turn): at most three lines, the run, the chat
  language rule and the settings summary.
- SessionStart with source `compact` or `resume`: the full block, which adds
  the code host, the tracker, the run file, the active task directories and
  "re-read the run file and each state.md".
- Bootstrap: a prompt that starts with `/orchestrator:orchestrate` (or the
  short `/orchestrate`) also gets the session id and "record it in the
  Sessions line of the run file".
- Every value from the settings or the run file is quoted data: control
  characters and whitespace collapsed to one space, length capped.

Any error injects nothing: the hook must never break the session.
"""

import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import orchestrator_settings as settings_lib
except Exception:  # fail open: no module, no context
    settings_lib = None

COMMAND = re.compile(r"^/(?:orchestrator:)?orchestrate(?![\w-])")
NAME_LIMIT = 60
PATH_LIMIT = 200
LIST_LIMIT = 300
MAX_TASKS = 5
MAX_CHILDREN = 200
FULL_SOURCES = ("compact", "resume")
LANGUAGE_RULE = "repository artifacts keep the project's own language"


def emit(event_name, lines):
    if not lines:
        return
    json.dump(
        {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": "\n".join(lines)}},
        sys.stdout,
    )


def quoted(value, limit=NAME_LIMIT):
    """`value` as quoted data on one line: control, format and separator
    characters collapsed to one space, `"` replaced, length capped."""
    text = "".join(" " if unicodedata.category(c)[0] in "CZ" else c for c in str(value))
    text = " ".join(text.split()).replace('"', "'")
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return f'"{text}"'


def bootstrap_line(session_id):
    return (
        f"Orchestrator session id: {session_id}. Record it in the Sessions line of the run file "
        "(- Sessions: ...), then keep the file's Status active."
    )


def roles_summary(data):
    off = ", ".join(str(r) for r in data.get("roles_off") or []) or "none"
    custom = ", ".join(
        f"{r.get('name')} {r.get('model')}/{r.get('effort')} {r.get('phase')}"
        for r in data.get("custom_roles") or []
        if isinstance(r, dict)
    ) or "none"
    return f"roles off: {quoted(off, LIST_LIMIT)}; custom roles: {quoted(custom, LIST_LIMIT)}"


def tracker_summary(tracker):
    if not isinstance(tracker, dict):
        return '"unknown"'
    name = tracker.get("name") or tracker.get("type")
    via = tracker.get("mcp_server") if tracker.get("access") == "mcp" else tracker.get("access")
    return f"{quoted(name)} (access {quoted(via)}, mode {quoted(tracker.get('mode'))})"


def active_tasks(run_path):
    """Task directories of the run file's Queue rows whose phase is not done."""
    try:
        with open(run_path, encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
    except OSError:
        return []
    match = re.search(r"^## Queue[ \t]*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    header, tasks = None, []
    for line in match.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        path = row.get("task directory", "").strip("`")
        if path.startswith("/") and row.get("phase", "").lower() != "done":
            tasks.append(path)
    return tasks


def tasks_summary(tasks):
    if not tasks:
        return "none"
    shown = ", ".join(quoted(t, PATH_LIMIT) for t in tasks[:MAX_TASKS])
    more = len(tasks) - MAX_TASKS
    return shown + (f" and {more} more in the run file" if more > 0 else "")


def context_lines(run, home, full):
    project = os.path.join(home, "projects", run["project"])
    path = quoted(settings_lib.settings_path(project), PATH_LIMIT)
    data, errors = settings_lib.load_settings(project)
    run_id = quoted(run["run_id"])
    lines = []
    if errors or not isinstance(data, dict):
        lines.append(
            f"Orchestrator run {run_id} active. Reply to the human in the chat language "
            f"of the settings; {LANGUAGE_RULE}."
        )
        error = quoted(errors[0] if errors else "unreadable", PATH_LIMIT)
        lines.append(f"Settings: {path} is invalid ({error}); fix it or run /orchestrator:setup.")
    else:
        language = quoted(data.get("chat_language"))
        lines.append(
            f"Orchestrator run {run_id} active. Reply to the human in chat language {language}; "
            f"{LANGUAGE_RULE}."
        )
        lines.append(f"Settings: {path} ({roles_summary(data)}).")
        if full:
            lines.append(
                f"Code host: {quoted(data.get('code_host'))}. "
                f"Tracker: {tracker_summary(data.get('tracker'))}."
            )
    if full:
        lines.append(f"Run file: {quoted(run['path'], PATH_LIMIT)}")
        lines.append("Active tasks: " + tasks_summary(active_tasks(run["path"])))
        lines.append(
            "Context was compacted or resumed: re-read the run file and each state.md before the next step."
        )
    return lines


def child_homes(cwd, home):
    """Homes other than `home` named by the CLAUDE.md of git repositories
    directly under `cwd`, when `cwd` itself is outside any repository."""
    if settings_lib.main_checkout(cwd):
        return []
    try:
        names = sorted(os.listdir(cwd))[:MAX_CHILDREN]
    except OSError:
        return []
    homes = []
    for name in names:
        repo = os.path.join(cwd, name)
        if not os.path.exists(os.path.join(repo, ".git")):
            continue
        found = settings_lib.find_home(repo)
        if not any(settings_lib.same_path(found, h) for h in [home] + homes):
            homes.append(found)
    return homes


def session_run(cwd, session_id):
    """`(run, home)` of the last active run that lists the session, or
    `(None, None)`. The cwd home first; a run in another home counts only
    when its project's repository names that home."""
    home = settings_lib.find_home(cwd)
    runs = settings_lib.active_runs(home, session_id)
    if runs:
        return runs[-1], home
    for other in child_homes(cwd, home):
        trusted = [
            run for run in settings_lib.active_runs(other, session_id)
            if settings_lib.repo_names_home(os.path.join(other, "projects", run["project"]))
        ]
        if trusted:
            return trusted[-1], other
    return None, None


def main():
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict) or settings_lib is None:
            return
        name = event.get("hook_event_name")
        session_id = event.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return
        cwd = event.get("cwd") if isinstance(event.get("cwd"), str) and event.get("cwd") else os.getcwd()
        run, home = session_run(cwd, session_id)
        if name == "UserPromptSubmit":
            prompt = event.get("prompt")
            starts = isinstance(prompt, str) and COMMAND.match(prompt.lstrip())
            lines = context_lines(run, home, full=False) if run else []
            if starts:
                lines.append(bootstrap_line(session_id))
            emit(name, lines[:3])
        elif name == "SessionStart" and event.get("source") in FULL_SOURCES and run:
            emit(name, context_lines(run, home, full=True))
    except Exception:  # fail open: inject nothing, never break the session
        return


if __name__ == "__main__":
    main()
