#!/usr/bin/env python3
"""Structural contract for the plugin.

Fails when:
- a file mentions a forbidden (company-, product- or platform-specific) word;
- a skill, agent or command has broken frontmatter;
- a relative markdown link does not resolve;
- an `orchestrator:<name>` reference names neither an agent nor a command that
  exists;
- manifests disagree on name or version;
- the role table differs between README, spec and roles-and-models.md;
- a user-facing marker (home override line, pass goal, verdict line) is spelled
  differently from the spec;
- a stale work-home path from 0.1.0 appears anywhere;
- the implementer description does not name all six pass goals;
- a tracker or code-host adapter is missing or lacks one of its fixed headings;
- an integration name (a code host or tracker product) appears outside the
  adapters, the setup reference, the settings hook module and the README;
- a settings marker (path, language rule, custom-roles rule) is missing from
  the spec, the skill, the setup reference or the README;
- the settings example in the setup reference fails `validate_settings()`;
- the PreToolUse matcher does not cover the settings-file writes;
- a hook command runs a missing script;
- the context hook is not registered for UserPromptSubmit and SessionStart
  `compact|resume`.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "orchestrator"

FORBIDDEN = re.compile(
    r"locali|localiapp|\bpult\b|opsbot|yandex(?![ -]tracker)|gradle|android|\bios\b"
    r"|maestro|emulator|figma|studioprojects|build-lock|work-slot|[а-яё]",
    re.IGNORECASE,
)
# Integration names are product features, not company words: the adapters, the
# setup reference and the settings hook module (both hold the schema enums) and
# the README may name them.
# Any other file (the generic flow text) may not.
INTEGRATION = re.compile(r"gitlab|\bglab\b|yandex[ -]tracker", re.IGNORECASE)
REFS = PLUGIN / "skills" / "orchestrator" / "references"
ADAPTERS = REFS / "adapters"
HOOKS = PLUGIN / "hooks"
INTEGRATION_ALLOWED = {ROOT / "README.md", REFS / "setup.md", HOOKS / "orchestrator_settings.py"}
# The spec and this test list the forbidden words on purpose.
FORBIDDEN_SKIP = {ROOT / "docs" / "spec.md", Path(__file__).resolve()}

TRACKER_ADAPTERS = (
    "tracker-github-issues", "tracker-mcp", "tracker-jira", "tracker-linear",
    "tracker-yandex-tracker", "tracker-other",
)
TRACKER_HEADINGS = ("Read a task", "Task id", "Change status", "Comment", "Link a pull request")
HOST_ADAPTERS = ("host-github", "host-gitlab", "host-none")
HOST_HEADINGS = (
    "Check access", "Find or open", "Review threads", "Reply and resolve",
    "Checks and approval", "Merge",
)

# Work-home paths of 0.1.0. The layout is per project now, so they must not
# come back. This test is the only file that spells them out.
STALE_PATHS = re.compile(r"<home>/(?:orchestrator\.md|tasks\b)")
PASS_GOALS = ("implementation", "review fixes", "publish", "PR comments", "merge base", "merge")

TEXT_SUFFIXES = {".md", ".json", ".py", ".sh", ".yaml", ".yml", ".txt"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
AGENT_REF = re.compile(r"orchestrator:([a-z][a-z-]*)")

errors = []


def fail(path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def text_files():
    for path in sorted(ROOT.rglob("*")):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"LICENSE", ".gitignore"}:
            yield path


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fields = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def check_forbidden():
    for path in text_files():
        if path in FORBIDDEN_SKIP:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = FORBIDDEN.search(line)
            if match:
                fail(path, f"line {number}: forbidden word {match.group(0)!r}")
            match = INTEGRATION.search(line)
            if match and path not in INTEGRATION_ALLOWED and ADAPTERS not in path.parents:
                fail(path, f"line {number}: integration name {match.group(0)!r} outside the adapters")


def check_adapters():
    for names, headings in ((TRACKER_ADAPTERS, TRACKER_HEADINGS), (HOST_ADAPTERS, HOST_HEADINGS)):
        for name in names:
            path = ADAPTERS / f"{name}.md"
            if not path.is_file():
                fail(path, "adapter missing")
                continue
            lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
            for heading in headings:
                if f"## {heading}" not in lines:
                    fail(path, f"missing heading '## {heading}'")


def check_stale_paths():
    for path in text_files():
        if path == Path(__file__).resolve():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = STALE_PATHS.search(line)
            if match:
                fail(path, f"line {number}: stale path {match.group(0)!r}")


def check_implementer_description():
    path = PLUGIN / "agents" / "implementer.md"
    description = (frontmatter(path) or {}).get("description", "")
    for goal in PASS_GOALS:
        # "merge" alone must not be satisfied by "merge base".
        tail = r"(?! base)" if goal == "merge" else ""
        if not re.search(rf"(?<![\w-]){re.escape(goal)}(?![\w-]){tail}", description):
            fail(path, f"description does not name the pass goal {goal!r}")


def check_frontmatter():
    agents = set()
    for path in sorted((PLUGIN / "agents").glob("*.md")):
        fields = frontmatter(path)
        if not fields:
            fail(path, "missing frontmatter")
            continue
        if fields.get("name") != path.stem:
            fail(path, f"name {fields.get('name')!r} does not match file name")
        if not fields.get("description"):
            fail(path, "missing description")
        if "model" in fields or "effort" in fields:
            fail(path, "model/effort must come from the caller, not frontmatter")
        agents.add(path.stem)
    for path in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        fields = frontmatter(path)
        if not fields:
            fail(path, "missing frontmatter")
            continue
        if fields.get("name") != path.parent.name:
            fail(path, f"name {fields.get('name')!r} does not match directory")
        if not fields.get("description", "").startswith("Use when"):
            fail(path, "description must start with 'Use when'")
        if fields.get("disable-model-invocation") != "true":
            fail(path, "skills are read by path and need disable-model-invocation: true")
    for path in sorted((PLUGIN / "commands").glob("*.md")):
        fields = frontmatter(path)
        if not fields or not fields.get("description"):
            fail(path, "missing description")
        elif fields.get("disable-model-invocation") != "true":
            fail(path, "commands need disable-model-invocation: true")
    expected = {"scout", "planner", "implementer", "reviewer", "tester", "visual-checker"}
    if agents != expected:
        fail(PLUGIN / "agents", f"agents {sorted(agents)} != {sorted(expected)}")
    return agents


def check_links_and_refs(agents):
    # `orchestrator:<name>` is an agent or a command of this plugin.
    names = agents | {path.stem for path in (PLUGIN / "commands").glob("*.md")}
    for path in text_files():
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                continue
            file_part = target.split("#", 1)[0]
            if file_part and not (path.parent / file_part).exists():
                fail(path, f"broken link {target}")
        if path in FORBIDDEN_SKIP:
            continue
        for name in AGENT_REF.findall(text):
            if name not in names:
                fail(path, f"unknown agent or command orchestrator:{name}")


def check_manifests():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    entry = next((p for p in market["plugins"] if p["name"] == plugin["name"]), None)
    if entry is None:
        fail(ROOT / ".claude-plugin" / "marketplace.json", "plugin entry missing")
    elif entry["version"] != plugin["version"]:
        fail(PLUGIN / ".claude-plugin" / "plugin.json", "version differs from marketplace")
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
    if "PreToolUse" not in hooks.get("hooks", {}):
        fail(PLUGIN / "hooks" / "hooks.json", "PreToolUse hook missing")


def role_table(path):
    text = path.read_text(encoding="utf-8")
    start = text.find("| Role | Light | Medium | Hard |")
    if start == -1:
        return None
    rows = []
    for line in text[start:].splitlines():
        if not line.startswith("|"):
            break
        rows.append(line.strip())
    return rows


def check_role_tables():
    reference = PLUGIN / "skills" / "orchestrator" / "references" / "roles-and-models.md"
    expected = role_table(reference)
    if not expected:
        fail(reference, "role table missing")
        return
    for path in (ROOT / "README.md", ROOT / "docs" / "spec.md"):
        if role_table(path) != expected:
            fail(path, "role table differs from roles-and-models.md")


def check_markers():
    home = "Subagent orchestrator home: <absolute path>"
    goals = PASS_GOALS
    runs = "<home>/projects/<project-key>/runs/<run-id>.md"
    settings = "<home>/projects/<project-key>/settings.json"
    language = "Repository artifacts keep the project's own language"
    # The rule under the role table: custom roles are not rows of the table.
    roles_rule = "Custom roles come from the settings"
    tasks = "<home>/projects/<project-key>/tasks/<task-id>/"
    verdicts = ("APPROVE (<n> findings)", "REQUEST CHANGES (<n> findings)", "BLOCKED (<n> findings): <reason>")
    refs = PLUGIN / "skills" / "orchestrator" / "references"
    wanted = [
        (ROOT / "README.md", [home, language, roles_rule]),
        (ROOT / "docs" / "spec.md", [home, runs, tasks, settings, language, roles_rule, *verdicts]),
        (PLUGIN / "skills" / "orchestrator" / "SKILL.md", [home, runs, tasks, settings, language]),
        (refs / "task-files.md", [home, runs, tasks, settings, "- Status:", "- Sessions:"]),
        (refs / "setup.md", [settings, language]),
        (refs / "roles-and-models.md", [roles_rule]),
        (PLUGIN / "skills" / "code-review" / "SKILL.md", list(verdicts)),
        (PLUGIN / "agents" / "reviewer.md", list(verdicts)),
        (refs / "briefs.md", [f"`{goal}`" for goal in goals]),
        (PLUGIN / "agents" / "implementer.md", [f"`{goal}`" for goal in goals]),
    ]
    for path, needles in wanted:
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                fail(path, f"missing {needle!r}")
    template = refs / "task-files.md"
    if "Complexity class:" in template.read_text(encoding="utf-8"):
        fail(template, "state.md uses 'Complexity:', never 'Complexity class:'")


def check_settings_example():
    """The JSON example of the setup reference passes the hook's schema check
    (not the existence check: the example's instruction file does not exist)."""
    sys.path.insert(0, str(HOOKS))
    import orchestrator_settings

    path = REFS / "setup.md"
    text = path.read_text(encoding="utf-8")
    section = text.find("## Schema, version 1")
    match = re.search(r"```json\n(.*?)\n```", text[section:], re.DOTALL) if section != -1 else None
    if not match:
        fail(path, "settings example (```json block under '## Schema, version 1') missing")
    else:
        try:
            data = json.loads(match.group(1))
        except ValueError as error:
            fail(path, f"settings example is not valid JSON: {error}")
        else:
            for error in orchestrator_settings.validate_settings(data):
                fail(path, f"settings example: {error}")


def check_settings_matcher():
    """The PreToolUse matcher covers every tool that can change a settings
    file, so the hook can check the write."""
    hooks = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    matchers = [entry.get("matcher", "") for entry in hooks.get("hooks", {}).get("PreToolUse", [])]
    for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        if not any(tool in matcher.split("|") for matcher in matchers):
            fail(HOOKS / "hooks.json", f"PreToolUse matcher does not cover {tool}")


def check_hook_scripts():
    """Every hook command runs a script that exists."""
    hooks = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8")).get("hooks", {})
    for event, entries in hooks.items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                for name in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"\s]+)", hook.get("command", "")):
                    if not (PLUGIN / name).is_file():
                        fail(HOOKS / "hooks.json", f"{event} runs a missing script {name}")


def check_context_hook():
    """The context hook is registered for every prompt and for compaction
    and resume."""
    hooks = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8")).get("hooks", {})
    context = "hooks/orchestrator-context.py"
    for event, matcher in (("UserPromptSubmit", None), ("SessionStart", "compact|resume")):
        if not any(
            entry.get("matcher") == matcher
            and any(context in hook.get("command", "") for hook in entry.get("hooks", []))
            for entry in hooks.get(event, [])
        ):
            fail(HOOKS / "hooks.json", f"{event} does not run {context} (matcher {matcher})")


def main():
    check_forbidden()
    check_stale_paths()
    check_adapters()
    agents = check_frontmatter()
    check_implementer_description()
    check_links_and_refs(agents)
    check_manifests()
    check_role_tables()
    check_markers()
    check_settings_example()
    check_settings_matcher()
    check_hook_scripts()
    check_context_hook()
    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} contract error(s)")
        return 1
    print("contract OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
