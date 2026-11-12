#!/usr/bin/env python3
"""Structural contract for the plugin.

Fails when:
- a file mentions a forbidden (company-, product- or platform-specific) word;
- a skill, agent or command has broken frontmatter;
- a relative markdown link does not resolve;
- an `orchestrator:<role>` reference names an agent that does not exist;
- manifests disagree on name or version;
- the role table differs between README, spec and roles-and-models.md;
- a user-facing marker (home override line, pass goal, verdict line) is spelled
  differently from the spec;
- a stale work-home path from 0.1.0 appears anywhere;
- the implementer description does not name all six pass goals.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "orchestrator"

FORBIDDEN = re.compile(
    r"locali|localiapp|\bpult\b|opsbot|yandex|gitlab|\bglab\b|gradle|android|\bios\b"
    r"|maestro|emulator|figma|studioprojects|build-lock|work-slot|[а-яё]",
    re.IGNORECASE,
)
# The spec and this test list the forbidden words on purpose.
FORBIDDEN_SKIP = {ROOT / "docs" / "spec.md", Path(__file__).resolve()}

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
    expected = {"scout", "planner", "implementer", "reviewer", "tester", "visual-checker"}
    if agents != expected:
        fail(PLUGIN / "agents", f"agents {sorted(agents)} != {sorted(expected)}")
    return agents


def check_links_and_refs(agents):
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
            if name not in agents and name != "orchestrate":
                fail(path, f"unknown agent orchestrator:{name}")


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
    tasks = "<home>/projects/<project-key>/tasks/<task-id>/"
    verdicts = ("APPROVE (<n> findings)", "REQUEST CHANGES (<n> findings)", "BLOCKED (<n> findings): <reason>")
    refs = PLUGIN / "skills" / "orchestrator" / "references"
    wanted = [
        (ROOT / "README.md", [home]),
        (ROOT / "docs" / "spec.md", [home, runs, tasks, *verdicts]),
        (PLUGIN / "skills" / "orchestrator" / "SKILL.md", [home, runs, tasks]),
        (refs / "task-files.md", [home, runs, tasks, "- Status:", "- Sessions:"]),
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


def main():
    check_forbidden()
    check_stale_paths()
    agents = check_frontmatter()
    check_implementer_description()
    check_links_and_refs(agents)
    check_manifests()
    check_role_tables()
    check_markers()
    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} contract error(s)")
        return 1
    print("contract OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
