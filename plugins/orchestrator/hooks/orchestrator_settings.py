"""Shared settings code of the orchestrator hooks (Python standard library only).

The schema and the project lookup are defined in
`skills/orchestrator/references/setup.md` and `references/task-files.md`.
Keep this module and those two files in step.

- `find_home(cwd)`: the work home.
- `main_checkout(path)`: the main checkout of the repository that holds `path`.
- `project_key(repo)`, `project_dir(home, repo)`: the project lookup.
- `load_settings(project_dir)`: `(settings, errors)`.
- `validate_settings(data)`: the pure schema check (no file system access).
- `check_instruction_paths(data)`: the separate existence check.
- `active_runs(home, session_id)`: the active run files that list a session.
- `task_dir_from_brief(prompt)`: the `Task directory:` line of a brief.
"""

import json
import os
import re
from datetime import datetime

HOME_ENV = "SUBAGENT_ORCHESTRATOR_HOME"
DEFAULT_HOME = "~/.subagent-orchestrator"
SETTINGS_FILE = "settings.json"
PLUGIN_PREFIX = "orchestrator:"

HOME_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?Subagent orchestrator home:[ \t]*`?([^`\n]*?)`?[ \t]*$",
    re.MULTILINE,
)
TASK_DIR_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?Task directory:[ \t]*`?([^`\n]*?)`?[ \t]*$",
    re.MULTILINE,
)
# <home>/projects/<key>/tasks/<id>; greedy, so a home that itself contains
# "/projects/" still splits at the last one.
TASK_DIR_LAYOUT = re.compile(r"^(/.+)/projects/([^/]+)/tasks/([^/]+)/?$")
RUN_LINE = re.compile(r"^[ \t]*-[ \t]*(Status|Sessions|Run id):[ \t]*(.*?)[ \t]*$", re.MULTILINE)

TOP_KEYS = ("version", "repo", "tracker", "code_host", "roles_off", "custom_roles", "chat_language", "saved")
TRACKER_KEYS = ("type", "name", "access", "mcp_server", "mode", "statuses")
STATUS_KEYS = ("start", "review", "done")
ROLE_KEYS = ("name", "agent_type", "instructions", "phase", "writes", "model", "effort")
TRACKER_TYPES = ("none", "github-issues", "jira", "linear", "yandex-tracker", "other")
ACCESS = ("gh", "mcp", "none")
MODES = ("read-only", "automate")
CODE_HOSTS = ("github", "gitlab", "none")
OPTIONAL_ROLES = ("scout", "tester", "visual-checker")
PLUGIN_ROLES = ("scout", "planner", "implementer", "reviewer", "tester", "visual-checker")
GENERAL_PURPOSE = "general-purpose"
PHASES = ("research", "plan", "review", "publish", "implementation")
MODELS = ("opus", "sonnet", "haiku")
EFFORTS = ("low", "medium", "high", "xhigh")
ROLE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def expand(path):
    return os.path.abspath(os.path.expanduser(path))


# ---------------------------------------------------------------- locations


def main_checkout(path):
    """Parent of the git common dir for `path`, or None outside a repository."""
    try:
        current = os.path.realpath(expand(path))
    except (TypeError, ValueError):
        return None
    if os.path.isfile(current):
        current = os.path.dirname(current)
    while True:
        dot_git = os.path.join(current, ".git")
        if os.path.isdir(dot_git):
            return current
        if os.path.isfile(dot_git):
            return _checkout_from_gitfile(current, dot_git)
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _checkout_from_gitfile(worktree, dot_git):
    try:
        with open(dot_git, encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError:
        return None
    if not text.startswith("gitdir:"):
        return None
    git_dir = os.path.realpath(os.path.join(worktree, text[len("gitdir:"):].strip()))
    common = git_dir
    try:
        with open(os.path.join(git_dir, "commondir"), encoding="utf-8") as handle:
            common = os.path.realpath(os.path.join(git_dir, handle.read().strip()))
    except OSError:
        pass
    return os.path.dirname(common)


def find_home(cwd):
    """`$SUBAGENT_ORCHESTRATOR_HOME`, else the home line of the main checkout's
    CLAUDE.md, else ~/.subagent-orchestrator. Always an absolute path."""
    env = os.environ.get(HOME_ENV, "").strip()
    if env:
        return expand(env)
    checkout = main_checkout(cwd) if cwd else None
    if checkout:
        try:
            with open(os.path.join(checkout, "CLAUDE.md"), encoding="utf-8") as handle:
                match = HOME_LINE.search(handle.read())
        except OSError:
            match = None
        if match and match.group(1).strip():
            candidate = os.path.expanduser(match.group(1).strip())
            if os.path.isabs(candidate):
                return os.path.abspath(candidate)
    return expand(DEFAULT_HOME)


def project_key(repo):
    """Name of the main checkout directory in lowercase kebab-case."""
    name = os.path.basename(os.path.normpath(repo)).lower()
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "project"


def _same_path(a, b):
    return os.path.realpath(expand(a)) == os.path.realpath(expand(b))


def project_dir(home, repo):
    """Steps 1-3 of the task-files.md lookup.

    Returns `(path, None)` for the project whose settings name `repo`,
    `(None, None)` when no project matches (run setup), and `(None, error)` for
    a settings file that cannot be parsed or has no string `repo` (never
    skipped).
    """
    base = os.path.join(expand(home), "projects", project_key(repo))
    suffix = 1
    while True:
        candidate = base if suffix == 1 else f"{base}-{suffix}"
        if not os.path.isdir(candidate):
            return None, None
        settings = os.path.join(candidate, SETTINGS_FILE)
        if os.path.exists(settings):
            data, error = _parse(settings)
            if error:
                return None, error
            stored = data.get("repo") if isinstance(data, dict) else None
            if not isinstance(stored, str) or not stored:
                return None, f"{settings}: no string 'repo'"
            if _same_path(stored, repo):
                return candidate, None
        suffix += 1


def _parse(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as error:
        return None, f"{path}: cannot read ({error.strerror or error})"
    except ValueError as error:
        return None, f"{path}: not valid JSON ({error})"


def settings_path(project):
    return os.path.join(project, SETTINGS_FILE)


def load_settings(project):
    """`(settings, errors)`. `settings` is None when the file is missing or
    cannot be parsed; `errors` is empty only for a valid file."""
    path = settings_path(project)
    if not os.path.exists(path):
        return None, [f"{path}: missing"]
    data, error = _parse(path)
    if error:
        return None, [error]
    errors = validate_settings(data)
    if not errors:
        errors = check_instruction_paths(data)
    return data, errors


# ---------------------------------------------------------------- schema


def _is_text(value):
    return isinstance(value, str) and value.strip() != ""


def _exact_keys(obj, keys, where, errors):
    for key in keys:
        if key not in obj:
            errors.append(f"{where}{key}: required (use null when it does not apply)")
    for key in obj:
        if key not in keys:
            errors.append(f"{where}{key}: unknown key")


def _enum(value, allowed, where, errors):
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{where}: {value!r} is not one of {', '.join(allowed)}")
        return False
    return True


def _text_or_null(value, required, where, why, errors):
    if required and not _is_text(value):
        errors.append(f"{where}: a non-empty string is required {why}")
    elif not required and value is not None:
        errors.append(f"{where}: must be null {why}")


def validate_settings(data):
    """Pure schema check of setup.md, version 1. Returns a list of errors."""
    if not isinstance(data, dict):
        return ["settings: must be one JSON object"]
    errors = []
    _exact_keys(data, TOP_KEYS, "", errors)
    if "version" in data and (type(data["version"]) is not int or data["version"] != 1):
        errors.append(f"version: must be the integer 1, not {data['version']!r}")
    if "repo" in data:
        repo = data["repo"]
        if not _is_text(repo) or not repo.startswith("/"):
            errors.append(f"repo: must be the absolute path of the main checkout, not {repo!r}")
    if "tracker" in data:
        _validate_tracker(data["tracker"], errors)
    if "code_host" in data:
        _enum(data["code_host"], CODE_HOSTS, "code_host", errors)
    if "roles_off" in data:
        _validate_roles_off(data["roles_off"], errors)
    if "custom_roles" in data:
        _validate_custom_roles(data["custom_roles"], errors)
    if "chat_language" in data and not _is_text(data["chat_language"]):
        errors.append("chat_language: a non-empty language name is required")
    if "saved" in data:
        saved = data["saved"]
        valid = isinstance(saved, str) and DATE.match(saved)
        if valid:
            try:
                datetime.strptime(saved, "%Y-%m-%d")
            except ValueError:
                valid = False
        if not valid:
            errors.append(f"saved: must be a date YYYY-MM-DD, not {saved!r}")
    return errors


def _validate_tracker(tracker, errors):
    if not isinstance(tracker, dict):
        errors.append("tracker: must be an object")
        return
    _exact_keys(tracker, TRACKER_KEYS, "tracker.", errors)
    kind = tracker.get("type")
    kind_ok = _enum(kind, TRACKER_TYPES, "tracker.type", errors)
    if "name" in tracker and kind_ok:
        _text_or_null(tracker["name"], kind == "other", "tracker.name", "when type is other" if kind == "other" else "unless type is other", errors)
    access = tracker.get("access")
    access_ok = _enum(access, ACCESS, "tracker.access", errors)
    if kind_ok and access_ok:
        allowed = {"github-issues": ("gh",), "none": ("none",)}.get(kind, ("mcp", "none"))
        if access not in allowed:
            errors.append(f"tracker.access: {access!r} does not fit type {kind!r} (use {' or '.join(allowed)})")
    if "mcp_server" in tracker and access_ok:
        _text_or_null(tracker["mcp_server"], access == "mcp", "tracker.mcp_server", "when access is mcp" if access == "mcp" else "unless access is mcp", errors)
    mode = tracker.get("mode")
    mode_ok = _enum(mode, MODES, "tracker.mode", errors)
    if mode_ok and access_ok and access == "none" and mode != "read-only":
        errors.append("tracker.mode: access none requires read-only")
    if "statuses" in tracker and mode_ok:
        statuses = tracker["statuses"]
        if mode == "automate":
            if not isinstance(statuses, dict):
                errors.append("tracker.statuses: an object with start, review and done is required when mode is automate")
            else:
                _exact_keys(statuses, STATUS_KEYS, "tracker.statuses.", errors)
                for key in STATUS_KEYS:
                    if key in statuses and not _is_text(statuses[key]):
                        errors.append(f"tracker.statuses.{key}: a non-empty status name is required")
        elif statuses is not None:
            errors.append("tracker.statuses: must be null unless mode is automate")


def _validate_roles_off(roles_off, errors):
    if not isinstance(roles_off, list):
        errors.append("roles_off: must be an array")
        return
    seen = set()
    for index, item in enumerate(roles_off):
        where = f"roles_off[{index}]"
        if _enum(item, OPTIONAL_ROLES, where, errors):
            if item in seen:
                errors.append(f"{where}: duplicate {item!r}")
            seen.add(item)


def _validate_custom_roles(roles, errors):
    if not isinstance(roles, list):
        errors.append("custom_roles: must be an array")
        return
    names, agent_types, paths = set(), set(), set()
    for index, role in enumerate(roles):
        where = f"custom_roles[{index}]"
        if not isinstance(role, dict):
            errors.append(f"{where}: must be an object")
            continue
        _exact_keys(role, ROLE_KEYS, where + ".", errors)
        name = role.get("name")
        if not isinstance(name, str) or not ROLE_NAME.fullmatch(name):
            errors.append(f"{where}.name: {name!r} is not kebab-case")
        elif name in PLUGIN_ROLES or name == GENERAL_PURPOSE:
            errors.append(f"{where}.name: {name!r} is a reserved role name")
        elif name in names:
            errors.append(f"{where}.name: duplicate {name!r}")
        else:
            names.add(name)
        agent_type = role.get("agent_type")
        if not _is_text(agent_type):
            errors.append(f"{where}.agent_type: a non-empty string is required")
        elif agent_type.startswith(PLUGIN_PREFIX):
            errors.append(f"{where}.agent_type: must not use the plugin's own prefix {PLUGIN_PREFIX!r}")
        elif agent_type != GENERAL_PURPOSE:
            if agent_type in agent_types:
                errors.append(f"{where}.agent_type: duplicate {agent_type!r}")
            agent_types.add(agent_type)
        if "instructions" in role:
            path = role["instructions"]
            if path is None:
                if agent_type == GENERAL_PURPOSE:
                    errors.append(f"{where}.instructions: required for general-purpose")
            elif not _is_text(path) or not path.startswith("/"):
                errors.append(f"{where}.instructions: must be an absolute path or null, not {path!r}")
            elif path in paths:
                errors.append(f"{where}.instructions: duplicate path {path!r}")
            else:
                paths.add(path)
        phase = role.get("phase")
        phase_ok = _enum(phase, PHASES, where + ".phase", errors)
        writes = role.get("writes")
        if not isinstance(writes, bool):
            errors.append(f"{where}.writes: must be true or false")
        elif phase_ok and writes and phase != "implementation":
            errors.append(f"{where}.writes: true requires phase implementation")
        elif phase_ok and not writes and phase == "implementation":
            errors.append(f"{where}.writes: false requires phase research, plan, review or publish")
        _enum(role.get("model"), MODELS, where + ".model", errors)
        _enum(role.get("effort"), EFFORTS, where + ".effort", errors)


def check_instruction_paths(data):
    """Existence check of the custom roles' instruction files."""
    errors = []
    roles = data.get("custom_roles") if isinstance(data, dict) else None
    for index, role in enumerate(roles if isinstance(roles, list) else []):
        path = role.get("instructions") if isinstance(role, dict) else None
        if _is_text(path) and not os.path.isfile(path):
            errors.append(f"custom_roles[{index}].instructions: file {path} does not exist")
    return errors


# ---------------------------------------------------------------- runs and briefs


def parse_run_file(path):
    """`{"path", "run_id", "status", "sessions"}` from the machine-read lines."""
    with open(path, encoding="utf-8", errors="ignore") as handle:
        text = handle.read()
    fields = {}
    for match in RUN_LINE.finditer(text):
        fields.setdefault(match.group(1), match.group(2))
    sessions = [s for s in re.split(r"[,\s]+", fields.get("Sessions", "")) if s and not s.startswith("<")]
    return {
        "path": path,
        "run_id": fields.get("Run id") or os.path.splitext(os.path.basename(path))[0],
        "status": fields.get("Status", "").strip("`").lower(),
        "sessions": sessions,
    }


def active_runs(home, session_id=None):
    """Run files with `- Status: active` in every project of `home`; with a
    `session_id`, only those whose `Sessions` line lists it."""
    found = []
    projects = os.path.join(expand(home), "projects")
    try:
        keys = sorted(os.listdir(projects))
    except OSError:
        return found
    for key in keys:
        runs = os.path.join(projects, key, "runs")
        try:
            names = sorted(os.listdir(runs))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".md"):
                continue
            try:
                run = parse_run_file(os.path.join(runs, name))
            except OSError:
                continue
            if run["status"] != "active":
                continue
            if session_id is None or session_id in run["sessions"]:
                run["project"] = key
                found.append(run)
    return found


def task_dir_line(prompt):
    """The raw value of the first `Task directory:` line, or None."""
    match = TASK_DIR_LINE.search(prompt or "")
    return match.group(1).strip() if match else None


def task_dir_from_brief(prompt):
    """The brief's task directory in the 0.2.0 layout, as
    `{"task_dir", "home", "project", "project_dir", "task_id"}`, or None."""
    value = task_dir_line(prompt)
    if not value:
        return None
    match = TASK_DIR_LAYOUT.match(os.path.normpath(value) if value.startswith("/") else value)
    if not match:
        return None
    home, key, task_id = match.groups()
    if key in (".", "..") or task_id in (".", ".."):
        return None
    return {
        "task_dir": os.path.join(home, "projects", key, "tasks", task_id),
        "home": home,
        "project": key,
        "project_dir": os.path.join(home, "projects", key),
        "task_id": task_id,
    }
