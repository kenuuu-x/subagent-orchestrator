#!/usr/bin/env python3
"""Behaviour of plugins/orchestrator/hooks/subagent-guard.py on synthetic events."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugins/orchestrator/hooks/subagent-guard.py"
HOOKS_JSON = ROOT / "plugins/orchestrator/hooks/hooks.json"

IMPLEMENTER = "orchestrator:implementer"
SESSION = "sess-1111"

# Every run uses its own work home, never the real one.
_EMPTY_HOME = tempfile.TemporaryDirectory()
HOME_OVERRIDE = {"path": _EMPTY_HOME.name}


def run_raw(stdin_text):
    env = dict(os.environ, SUBAGENT_ORCHESTRATOR_HOME=HOME_OVERRIDE["path"], PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True, timeout=20, env=env
    )
    return result


def decide(event):
    """Return 'allow' or 'deny' for an event; fail if the hook crashes."""
    result = run_raw(json.dumps(event))
    if result.returncode != 0:
        raise AssertionError(f"hook exited {result.returncode}: {result.stderr}")
    if not result.stdout.strip():
        return "allow"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def reason(event):
    out = json.loads(run_raw(json.dumps(event)).stdout)
    return out["hookSpecificOutput"]["permissionDecisionReason"]


def settings_data(repo, instructions):
    return {
        "version": 1,
        "repo": str(repo),
        "tracker": {
            "type": "none", "name": None, "access": "none", "mcp_server": None,
            "mode": "read-only", "statuses": None,
        },
        "code_host": "github",
        "roles_off": ["tester"],
        "custom_roles": [
            {
                "name": "security-reviewer", "agent_type": "general-purpose",
                "instructions": str(instructions), "phase": "review", "writes": False,
                "model": "opus", "effort": "high",
            },
            {
                "name": "perf-fixer", "agent_type": "perf-agent", "instructions": None,
                "phase": "implementation", "writes": True, "model": "sonnet", "effort": "medium",
            },
        ],
        "chat_language": "German",
        "saved": "2026-11-12",
    }


def write_run(home, key, run_id, status, sessions):
    runs = Path(home) / "projects" / key / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{run_id}.md").write_text(
        f"# Orchestrator run {run_id}\n\n- Run id: {run_id}\n- Project: {key}\n"
        f"- Status: {status}\n- Sessions: {sessions}\n- Last update: now\n",
        encoding="utf-8",
    )


class HomeFixture(unittest.TestCase):
    """A temporary work home: project `app` with valid settings and an active
    run that lists SESSION; a repository `app` whose main checkout matches."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name).resolve()
        cls.home = root / "home"
        cls.repo = root / "repos" / "app"
        (cls.repo / ".git").mkdir(parents=True)
        cls.project = cls.home / "projects" / "app"
        cls.instructions = cls.project / "roles" / "security-reviewer.md"
        cls.instructions.parent.mkdir(parents=True)
        cls.instructions.write_text("Check security.", encoding="utf-8")
        cls.settings = cls.project / "settings.json"
        cls.settings.write_text(json.dumps(settings_data(cls.repo, cls.instructions)), encoding="utf-8")
        write_run(cls.home, "app", "20261112-1000", "active", f"other-session, {SESSION}")
        cls.task_dir = cls.project / "tasks" / "gh-1"
        cls.worktree = root / "repos" / "app-worktrees" / "gh-1"
        cls.worktree.mkdir(parents=True)
        HOME_OVERRIDE["path"] = str(cls.home)

    @classmethod
    def tearDownClass(cls):
        HOME_OVERRIDE["path"] = _EMPTY_HOME.name
        cls.tmp.cleanup()

    def brief(self, text="Do the work.", task_dir=None):
        task_dir = self.task_dir if task_dir is None else task_dir
        return f"Task directory: {task_dir}\nTask: gh-1, test\nWorktree: {self.worktree}\n{text}"

    def agent(self, subagent_type=IMPLEMENTER, model="opus", prompt="Do the work.", raw=False,
              session=SESSION, effort=None, cwd=None):
        tool_input = {"subagent_type": subagent_type, "prompt": prompt if raw else self.brief(prompt)}
        if model is not None:
            tool_input["model"] = model
        if effort is not None:
            tool_input["effort"] = effort
        event = {"tool_name": "Agent", "tool_input": tool_input}
        if session is not None:
            event["session_id"] = session
        if cwd is not None:
            event["cwd"] = str(cwd)
        return event


def write_agent(session_dir, agent_id, agent_type, context, minutes_ago, finished=True):
    sub = session_dir / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    meta = {"agentType": agent_type}
    if finished:
        meta["finished"] = True
    (sub / f"agent-{agent_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    stamp = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    lines = [
        {"type": "user", "timestamp": stamp, "message": {"content": "brief"}},
        {
            "type": "assistant",
            "timestamp": stamp,
            "message": {
                "usage": {
                    "input_tokens": 10,
                    "cache_read_input_tokens": context - 10,
                    "cache_creation_input_tokens": 0,
                }
            },
        },
    ]
    (sub / f"agent-{agent_id}.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")


class HooksJsonTest(unittest.TestCase):
    def test_registration(self):
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        entry = config["hooks"]["PreToolUse"][0]
        for name in ("SendMessage", "Agent", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit"):
            self.assertIn(name, entry["matcher"].split("|"))
        command = entry["hooks"][0]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/subagent-guard.py", command["command"])
        self.assertEqual(command["timeout"], 10)


class SendMessageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        session = Path(cls.tmp.name) / "session"
        cls.transcript = str(session) + ".jsonl"
        Path(cls.transcript).write_text("", encoding="utf-8")
        write_agent(session, "a1111111111111111", IMPLEMENTER, 900_000, 5)
        write_agent(session, "a2222222222222222", IMPLEMENTER, 50_000, 5)
        write_agent(session, "a3333333333333333", IMPLEMENTER, 50_000, 90)
        write_agent(session, "a4444444444444444", "orchestrator:planner", 900_000, 90)
        write_agent(session, "a5555555555555555", IMPLEMENTER, 900_000, 1, finished=False)
        # Corrupt transcript lines must be skipped, not crash the hook.
        write_agent(session, "a6666666666666666", IMPLEMENTER, 50_000, 5)
        path = session / "subagents" / "agent-a6666666666666666.jsonl"
        path.write_text("not json\n[1, 2]\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        # Empty transcript: no context, no timestamp.
        sub = session / "subagents"
        (sub / "agent-a7777777777777777.meta.json").write_text(
            json.dumps({"agentType": IMPLEMENTER, "finished": True}), encoding="utf-8"
        )
        (sub / "agent-a7777777777777777.jsonl").write_text("", encoding="utf-8")
        # Meta that is not JSON.
        (sub / "agent-a8888888888888888.meta.json").write_text("{broken", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def send(self, target, transcript=None):
        return {
            "tool_name": "SendMessage",
            "transcript_path": transcript if transcript is not None else self.transcript,
            "tool_input": {"to": target, "message": "pass 2"},
        }

    def test_long_context_denied(self):
        event = self.send("a1111111111111111")
        self.assertEqual(decide(event), "deny")
        self.assertIn("next pass number", reason(event))

    def test_short_fresh_allowed(self):
        self.assertEqual(decide(self.send("a2222222222222222")), "allow")

    def test_idle_denied(self):
        event = self.send("a3333333333333333")
        self.assertEqual(decide(event), "deny")
        self.assertIn("idle", reason(event))

    def test_other_agent_type_allowed(self):
        self.assertEqual(decide(self.send("a4444444444444444")), "allow")

    def test_unfinished_allowed(self):
        self.assertEqual(decide(self.send("a5555555555555555")), "allow")

    def test_corrupt_transcript_lines_skipped(self):
        self.assertEqual(decide(self.send("a6666666666666666")), "allow")

    def test_empty_transcript_allowed(self):
        self.assertEqual(decide(self.send("a7777777777777777")), "allow")

    def test_broken_meta_allowed(self):
        self.assertEqual(decide(self.send("a8888888888888888")), "allow")

    def test_unknown_agent_allowed(self):
        self.assertEqual(decide(self.send("abcdef0123456789")), "allow")

    def test_target_by_name_allowed(self):
        self.assertEqual(decide(self.send("implementer-1")), "allow")

    def test_missing_target_allowed(self):
        event = {"tool_name": "SendMessage", "transcript_path": self.transcript, "tool_input": {}}
        self.assertEqual(decide(event), "allow")

    def test_no_transcript_path_allowed(self):
        event = {"tool_name": "SendMessage", "tool_input": {"to": "a1111111111111111"}}
        self.assertEqual(decide(event), "allow")

    def test_transcript_without_jsonl_suffix_allowed(self):
        self.assertEqual(decide(self.send("a1111111111111111", transcript="/tmp/no-suffix")), "allow")


class AgentTest(HomeFixture):
    def test_opus_without_marker_denied(self):
        event = self.agent()
        self.assertEqual(decide(event), "deny")
        self.assertIn("Complexity: hard", reason(event))

    def test_full_opus_id_without_marker_denied(self):
        self.assertEqual(decide(self.agent(model="claude-opus-9")), "deny")

    def test_opus_with_complexity_marker_allowed(self):
        self.assertEqual(decide(self.agent(prompt="Task X.\nComplexity: hard\nPlan: /p")), "allow")

    def test_opus_with_hard_part_marker_allowed(self):
        self.assertEqual(decide(self.agent(prompt="Task X.\nHard part: src/sync.py")), "allow")

    def test_bullet_markers_allowed(self):
        for prompt in ("- Complexity: hard", "* Hard part: src/sync.py", "  - Hard part: a.py, b.py"):
            with self.subTest(prompt=prompt):
                self.assertEqual(decide(self.agent(prompt="Task X.\n" + prompt + "\nPlan: /p")), "allow")

    def test_empty_hard_part_denied(self):
        self.assertEqual(decide(self.agent(prompt="Hard part:\nnothing")), "deny")
        self.assertEqual(decide(self.agent(prompt="Hard part:   ")), "deny")
        self.assertEqual(decide(self.agent(prompt="- Hard part:\n")), "deny")

    def test_none_hard_part_denied(self):
        for value in ("none", "None", "NONE", "n/a", "N/A", "none  "):
            with self.subTest(value=value):
                self.assertEqual(decide(self.agent(prompt="Hard part: " + value)), "deny")
                self.assertEqual(decide(self.agent(prompt="- Hard part: " + value)), "deny")

    def test_placeholder_or_punctuation_hard_part_denied(self):
        for value in ("<files>", "<src/sync.py>", "...", "-", "--", "?!", "/ ", "<"):
            with self.subTest(value=value):
                self.assertEqual(decide(self.agent(prompt="Hard part: " + value)), "deny")
                self.assertEqual(decide(self.agent(prompt="- Hard part: " + value)), "deny")

    def test_hard_part_starting_with_none_allowed(self):
        self.assertEqual(decide(self.agent(prompt="Hard part: none_sync.py")), "allow")

    def test_complexity_not_hard_denied(self):
        self.assertEqual(decide(self.agent(prompt="Complexity: hardly")), "deny")
        self.assertEqual(decide(self.agent(prompt="Complexity: medium")), "deny")

    def test_marker_mid_line_denied(self):
        self.assertEqual(decide(self.agent(prompt="It is not Complexity: hard here")), "deny")

    def test_sonnet_allowed(self):
        self.assertEqual(decide(self.agent(model="sonnet")), "allow")

    def test_implementer_without_model_denied(self):
        event = self.agent(model=None)
        self.assertEqual(decide(event), "deny")
        self.assertIn("model and effort explicitly", reason(event))
        self.assertIn("roles-and-models.md", reason(event))

    def test_implementer_with_empty_model_denied(self):
        self.assertEqual(decide(self.agent(model="")), "deny")

    def test_plugin_type_without_model_denied(self):
        # Rule 4: every orchestrator:* call needs a model, not only the implementer.
        for role in ("orchestrator:planner", "orchestrator:reviewer", "orchestrator:scout"):
            with self.subTest(role=role):
                event = self.agent(subagent_type=role, model=None)
                self.assertEqual(decide(event), "deny")
                self.assertIn(role + " needs an explicit model", reason(event))

    def test_other_type_without_model_allowed(self):
        self.assertEqual(decide(self.agent(subagent_type="general-purpose", model=None)), "allow")
        self.assertEqual(decide(self.agent(subagent_type="Explore", model=None, raw=True)), "allow")

    def test_other_type_on_opus_allowed(self):
        self.assertEqual(decide(self.agent(subagent_type="orchestrator:planner")), "allow")

    def test_general_purpose_allowed(self):
        self.assertEqual(decide(self.agent(subagent_type="general-purpose")), "allow")


class SettingsGateTest(HomeFixture):
    """Rules 5-8 on orchestrator:* calls."""

    def planner(self, **kwargs):
        kwargs.setdefault("subagent_type", "orchestrator:planner")
        kwargs.setdefault("model", "opus")
        return self.agent(**kwargs)

    def project_with(self, key, text):
        project = self.home / "projects" / key
        project.mkdir(parents=True, exist_ok=True)
        if text is not None:
            (project / "settings.json").write_text(text, encoding="utf-8")
        return project / "tasks" / "t1"

    def test_valid_call_allowed(self):
        self.assertEqual(decide(self.planner()), "allow")
        self.assertEqual(decide(self.agent(model="sonnet")), "allow")

    def test_missing_task_directory_denied(self):
        event = self.planner(prompt="Plan the task.", raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("Task directory: <home>/projects/<key>/tasks/<id>", reason(event))

    def test_legacy_task_directory_denied(self):
        event = self.planner(prompt="Task directory: /h/.subagent-orchestrator/tasks/gh-1\nPlan.", raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("found '/h/.subagent-orchestrator/tasks/gh-1'", reason(event))

    def test_missing_task_directory_denied_for_implementer(self):
        self.assertEqual(decide(self.agent(model="sonnet", prompt="Work.", raw=True)), "deny")

    def test_project_without_settings_denied(self):
        task = self.project_with("nosettings", None)
        event = self.planner(prompt=self.brief(task_dir=task), raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("run the setup interview (setup.md or /orchestrator:setup) before any subagent", reason(event))

    def test_unknown_project_denied(self):
        task = self.home / "projects" / "ghost" / "tasks" / "t1"
        self.assertIn("setup interview", reason(self.planner(prompt=self.brief(task_dir=task), raw=True)))

    def test_malformed_settings_denied(self):
        task = self.project_with("broken", "{not json")
        event = self.planner(prompt=self.brief(task_dir=task), raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("not valid JSON", reason(event))
        self.assertIn("re-run setup", reason(event))

    def test_schema_error_denied(self):
        data = settings_data(self.repo, self.instructions)
        data["code_host"] = "svn"
        task = self.project_with("schema", json.dumps(data))
        event = self.planner(prompt=self.brief(task_dir=task), raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("code_host", reason(event))

    def test_missing_instruction_file_denied(self):
        data = settings_data(self.repo, self.home / "nowhere.md")
        task = self.project_with("noinstr", json.dumps(data))
        event = self.planner(prompt=self.brief(task_dir=task), raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("does not exist", reason(event))

    def test_unlinked_session_denied_with_id(self):
        event = self.planner(session="sess-unknown-42")
        self.assertEqual(decide(event), "deny")
        text = reason(event)
        self.assertIn("add sess-unknown-42 to the Sessions line of your run file", text)

    def test_finished_run_does_not_link(self):
        write_run(self.home, "app", "20261101-0900", "finished", "sess-old")
        self.assertEqual(decide(self.planner(session="sess-old")), "deny")

    def test_run_in_other_project_links(self):
        write_run(self.home, "elsewhere", "20261112-1200", "active", "sess-other-project")
        self.assertEqual(decide(self.planner(session="sess-other-project")), "allow")

    def test_no_session_id_skips_link_rule(self):
        self.assertEqual(decide(self.planner(session=None)), "allow")
        self.assertEqual(decide(self.planner(session="")), "allow")

    def test_role_switched_off_denied(self):
        event = self.agent(subagent_type="orchestrator:tester", model="sonnet")
        self.assertEqual(decide(event), "deny")
        self.assertIn("switched off in roles_off", reason(event))
        self.assertIn(str(self.settings), reason(event))

    def test_role_switched_on_allowed(self):
        for role in ("scout", "visual-checker", "reviewer"):
            with self.subTest(role=role):
                self.assertEqual(decide(self.agent(subagent_type="orchestrator:" + role, model="sonnet")), "allow")

    def test_order_model_before_task_directory(self):
        event = self.planner(model=None, prompt="no brief", raw=True)
        self.assertIn("needs an explicit model", reason(event))


class CustomRoleTest(HomeFixture):
    """Rule 9."""

    def role_call(self, model="opus", effort="high", **kwargs):
        kwargs.setdefault("subagent_type", "general-purpose")
        kwargs.setdefault("prompt", f"Instructions: {self.instructions}\nReview the diff.")
        return self.agent(model=model, effort=effort, **kwargs)

    def test_matching_model_and_effort_allowed(self):
        self.assertEqual(decide(self.role_call()), "allow")
        self.assertEqual(decide(self.role_call(model="claude-opus-4-1")), "allow")

    def test_effort_optional(self):
        self.assertEqual(decide(self.role_call(effort=None)), "allow")

    def test_wrong_model_denied(self):
        event = self.role_call(model="sonnet")
        self.assertEqual(decide(event), "deny")
        self.assertIn("security-reviewer: model opus, effort high", reason(event))

    def test_missing_model_denied(self):
        self.assertEqual(decide(self.role_call(model=None)), "deny")

    def test_wrong_effort_denied(self):
        self.assertEqual(decide(self.role_call(effort="low")), "deny")

    def test_by_agent_type(self):
        call = {"subagent_type": "perf-agent", "prompt": "Fix it."}
        self.assertEqual(decide(self.role_call(model="sonnet", effort="medium", **call)), "allow")
        self.assertEqual(decide(self.role_call(model="opus", effort="medium", **call)), "deny")
        self.assertEqual(decide(self.role_call(model="sonnet", effort="high", **call)), "deny")

    def test_plain_general_purpose_allowed(self):
        self.assertEqual(decide(self.role_call(model=None, effort=None, prompt="Search for X.")), "allow")

    def test_plugin_role_mentioning_instructions_is_not_a_custom_role(self):
        event = self.role_call(subagent_type="orchestrator:reviewer", model="sonnet", effort="low")
        self.assertEqual(decide(event), "allow")

    def test_cwd_lookup_without_task_directory(self):
        prompt = f"Instructions: {self.instructions}\nReview."
        sub = self.repo / "src"
        sub.mkdir(exist_ok=True)
        good = self.role_call(prompt=prompt, raw=True, cwd=sub)
        self.assertEqual(decide(good), "allow")
        bad = self.role_call(model="haiku", prompt=prompt, raw=True, cwd=sub)
        self.assertEqual(decide(bad), "deny")

    def test_cwd_outside_projects_allowed(self):
        event = self.role_call(model="haiku", prompt="x", raw=True, cwd=self.home)
        self.assertEqual(decide(event), "allow")

    def broken_repo(self, name, content):
        """A repository `name` whose settings file holds `content` (text)."""
        repo = Path(self.tmp.name).resolve() / "repos" / name
        (repo / ".git").mkdir(parents=True, exist_ok=True)
        project = self.home / "projects" / name
        project.mkdir(parents=True, exist_ok=True)
        (project / "settings.json").write_text(content, encoding="utf-8")
        return repo

    def test_cwd_lookup_broken_settings_unlinked_session_allowed(self):
        repo = self.broken_repo("broken-repo", "{bad")
        for subagent_type in ("general-purpose", "Explore", "perf-agent"):
            with self.subTest(subagent_type=subagent_type):
                event = self.role_call(subagent_type=subagent_type, model=None, prompt="Search.",
                                       raw=True, cwd=repo, session="unrelated-session")
                self.assertEqual(decide(event), "allow")
        no_session = self.role_call(model=None, prompt="Search.", raw=True, cwd=repo, session=None)
        self.assertEqual(decide(no_session), "allow")

    def test_cwd_lookup_broken_settings_linked_session_denied(self):
        repo = self.broken_repo("broken-repo", "{bad")
        event = self.role_call(model=None, prompt="Search.", raw=True, cwd=repo)
        self.assertEqual(decide(event), "deny")
        self.assertIn("not valid JSON", reason(event))

    def test_cwd_lookup_schema_invalid_settings(self):
        data = settings_data(Path(self.tmp.name).resolve() / "repos" / "invalid-repo", self.instructions)
        data["extra"] = True
        repo = self.broken_repo("invalid-repo", json.dumps(data))
        plain = self.role_call(model=None, prompt="Search.", raw=True, cwd=repo, session="unrelated-session")
        self.assertEqual(decide(plain), "allow")
        linked = self.role_call(model=None, prompt="Search.", raw=True, cwd=repo)
        self.assertEqual(decide(linked), "deny")
        self.assertIn("extra: unknown key", reason(linked))
        by_type = self.role_call(subagent_type="perf-agent", model="sonnet", effort="medium",
                                 prompt="Fix it.", raw=True, cwd=repo, session="unrelated-session")
        self.assertEqual(decide(by_type), "deny")
        self.assertIn("extra: unknown key", reason(by_type))
        by_path = self.role_call(prompt=f"Instructions: {self.instructions}\nReview.", raw=True,
                                 cwd=repo, session="unrelated-session")
        self.assertEqual(decide(by_path), "deny")

    def test_cwd_lookup_wrongly_typed_roles_do_not_crash(self):
        data = settings_data(Path(self.tmp.name).resolve() / "repos" / "typed-repo", self.instructions)
        data["custom_roles"] = [5, {"agent_type": 7, "instructions": ["x"]}, "perf-agent"]
        repo = self.broken_repo("typed-repo", json.dumps(data))
        event = self.role_call(subagent_type="perf-agent", model=None, prompt="Fix it.", raw=True,
                               cwd=repo, session="unrelated-session")
        self.assertEqual(decide(event), "allow")

    def test_task_directory_with_invalid_settings_denied(self):
        project = self.home / "projects" / "invalid-gp"
        project.mkdir(parents=True, exist_ok=True)
        (project / "settings.json").write_text(json.dumps({"version": 1}), encoding="utf-8")
        event = self.role_call(prompt=self.brief(task_dir=project / "tasks" / "t1"), raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("re-run setup", reason(event))

    def test_task_directory_without_settings_allowed(self):
        event = self.role_call(model="haiku", prompt=self.brief(task_dir=self.home / "projects" / "none" / "tasks" / "t"), raw=True)
        self.assertEqual(decide(event), "allow")


class SettingsWriteTest(HomeFixture):
    """Rule 11."""

    def write(self, content, tool="Write", path=None, agent_type=None, cwd=None):
        path = str(self.settings) if path is None else str(path)
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        tool_input = {key: path}
        if tool == "Write":
            tool_input["content"] = content if isinstance(content, str) else json.dumps(content)
        else:
            tool_input.update({"old_string": "a", "new_string": "b"})
        event = {"tool_name": tool, "tool_input": tool_input, "session_id": SESSION}
        if agent_type:
            event["agent_type"] = agent_type
        if cwd:
            event["cwd"] = str(cwd)
        return event

    def valid(self):
        return settings_data(self.repo, self.instructions)

    def test_valid_write_allowed(self):
        self.assertEqual(decide(self.write(self.valid())), "allow")

    def test_new_project_settings_validated(self):
        target = self.home / "projects" / "fresh" / "settings.json"
        self.assertEqual(decide(self.write(self.valid(), path=target)), "allow")
        bad = self.valid()
        bad["roles_off"] = ["planner"]
        event = self.write(bad, path=target)
        self.assertEqual(decide(event), "deny")
        self.assertIn("roles_off[0]", reason(event))

    def test_invalid_write_denied(self):
        bad = self.valid()
        bad["extra"] = True
        event = self.write(bad)
        self.assertEqual(decide(event), "deny")
        self.assertIn("extra: unknown key", reason(event))

    def test_not_json_denied(self):
        event = self.write("{oops")
        self.assertEqual(decide(event), "deny")
        self.assertIn("not valid JSON", reason(event))

    def test_missing_instruction_file_denied(self):
        data = settings_data(self.repo, self.home / "missing.md")
        event = self.write(data)
        self.assertEqual(decide(event), "deny")
        self.assertIn("instruction files first", reason(event))

    def test_edit_denied(self):
        for tool in ("Edit", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                event = self.write(None, tool=tool)
                self.assertEqual(decide(event), "deny")
                self.assertIn("rewrite the whole file with Write", reason(event))

    def test_name_case_variants_checked(self):
        for path in (
            self.project / "Settings.json",
            self.project / "SETTINGS.JSON",
            self.home / "Projects" / "app" / "settings.json",
        ):
            with self.subTest(path=path):
                event = self.write("{oops", path=path)
                self.assertEqual(decide(event), "deny")
                self.assertIn("not valid JSON", reason(event))
                self.assertEqual(decide(self.write(None, tool="Edit", path=path)), "deny")

    def test_subagent_denied(self):
        event = self.write(self.valid(), agent_type="orchestrator:implementer")
        self.assertEqual(decide(event), "deny")
        self.assertIn("subagent must not change the settings", reason(event))

    def test_other_files_allowed(self):
        others = (
            self.home / "projects" / "app" / "runs" / "settings.json",
            self.home / "projects" / "app" / "notes.json",
            self.repo / "settings.json",
            Path(self.tmp.name) / "projects" / "app" / "settings.json",
        )
        for path in others:
            with self.subTest(path=path):
                self.assertEqual(decide(self.write("junk", path=path)), "allow")
                self.assertEqual(decide(self.write(None, tool="Edit", path=path)), "allow")


def write_sub(session_dir, agent_id, agent_type, brief, minutes_ago=1, finished=False, content_list=False):
    """A subagent transcript whose first user message is `brief`."""
    sub = Path(session_dir) / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    meta = {"agentType": agent_type}
    if finished:
        meta["finished"] = True
    (sub / f"agent-{agent_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    stamp = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    content = [{"type": "text", "text": brief}] if content_list else brief
    lines = [
        {"type": "user", "timestamp": stamp, "message": {"role": "user", "content": content}},
        {"type": "assistant", "timestamp": stamp, "message": {"usage": {"input_tokens": 5}}},
    ]
    (sub / f"agent-{agent_id}.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")


class OneWriterTest(HomeFixture):
    """Rule 10."""

    def setUp(self):
        self.session_tmp = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.session_tmp.name) / "session"
        self.transcript = str(self.session_dir) + ".jsonl"
        Path(self.transcript).write_text("", encoding="utf-8")

    def tearDown(self):
        self.session_tmp.cleanup()

    def with_transcript(self, event, agent_id=None):
        event["transcript_path"] = self.transcript
        if agent_id:
            event["agent_id"] = agent_id
        return event

    def implementer(self, prompt="Pass 2.", raw=False, agent_id=None):
        return self.with_transcript(self.agent(model="sonnet", prompt=prompt, raw=raw), agent_id)

    def perf_call(self, prompt=None):
        prompt = prompt if prompt is not None else self.brief("Fix it.")
        event = self.agent(subagent_type="perf-agent", model="sonnet", effort="medium", prompt=prompt, raw=True)
        return self.with_transcript(event)

    def busy(self, agent_id="a1", agent_type=IMPLEMENTER, worktree=None, **kwargs):
        worktree = self.worktree if worktree is None else worktree
        write_sub(self.session_dir, agent_id, agent_type, self.brief(f"Worktree: {worktree}"), **kwargs)

    def test_missing_worktree_line_denied(self):
        prompt = f"Task directory: {self.task_dir}\nTask: gh-1, test\nWork in the worktree."
        event = self.implementer(prompt=prompt, raw=True)
        self.assertEqual(decide(event), "deny")
        self.assertIn("standalone line 'Worktree: <absolute path>'", reason(event))

    def test_relative_worktree_denied(self):
        prompt = f"Task directory: {self.task_dir}\nWorktree: repos/app\nWork."
        self.assertEqual(decide(self.implementer(prompt=prompt, raw=True)), "deny")

    def test_free_worktree_allowed(self):
        self.assertEqual(decide(self.implementer()), "allow")

    def test_unfinished_writer_denied(self):
        write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."))
        event = self.implementer()
        self.assertEqual(decide(event), "deny")
        text = reason(event)
        self.assertIn("Only one writer per worktree", text)
        self.assertIn("a1", text)
        self.assertIn(str(self.worktree), text)
        self.assertRegex(text, r"last activity \d{4}-\d{2}-\d{2} \d{2}:\d{2}")
        self.assertRegex(text, r"After a resume .* wait until \d{4}-\d{2}-\d{2} \d{2}:\d{2}")
        self.assertIn("ask the human", text)

    def test_brief_as_text_blocks(self):
        write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."), content_list=True)
        self.assertEqual(decide(self.implementer()), "deny")

    def test_finished_writer_allowed(self):
        write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."), finished=True)
        self.assertEqual(decide(self.implementer()), "allow")

    def test_idle_writer_allowed(self):
        write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."), minutes_ago=61)
        self.assertEqual(decide(self.implementer()), "allow")

    def test_other_worktree_allowed(self):
        other = Path(self.tmp.name).resolve() / "repos" / "app-worktrees" / "gh-2"
        other.mkdir(parents=True, exist_ok=True)
        write_sub(self.session_dir, "a1", IMPLEMENTER, f"Task directory: {self.task_dir}\nWorktree: {other}\n")
        self.assertEqual(decide(self.implementer()), "allow")

    def test_symlinked_worktree_denied(self):
        link = Path(self.session_tmp.name) / "wt-link"
        link.symlink_to(self.worktree)
        write_sub(self.session_dir, "a1", IMPLEMENTER, f"Task directory: {self.task_dir}\nWorktree: {link}\n")
        self.assertEqual(decide(self.implementer()), "deny")

    def test_read_only_plugin_roles_do_not_lock(self):
        for index, role in enumerate(("orchestrator:reviewer", "orchestrator:scout",
                                      "orchestrator:planner", "orchestrator:visual-checker")):
            write_sub(self.session_dir, f"r{index}", role, self.brief("Review."))
        self.assertEqual(decide(self.implementer()), "allow")

    def test_tester_and_custom_roles_lock(self):
        for agent_type in ("orchestrator:tester", "general-purpose", "perf-agent"):
            with self.subTest(agent_type=agent_type):
                write_sub(self.session_dir, "w1", agent_type, self.brief("Write."))
                self.assertEqual(decide(self.implementer()), "deny")

    def test_tester_call_checked(self):
        original = self.settings.read_text(encoding="utf-8")
        data = json.loads(original)
        data["roles_off"] = []
        self.settings.write_text(json.dumps(data), encoding="utf-8")
        try:
            tester = self.with_transcript(self.agent(subagent_type="orchestrator:tester", model="sonnet"))
            self.assertEqual(decide(tester), "allow")
            prompt = f"Task directory: {self.task_dir}\nTask: gh-1, tests\nWrite tests."
            bare = self.with_transcript(self.agent(subagent_type="orchestrator:tester", model="sonnet",
                                                   prompt=prompt, raw=True))
            self.assertEqual(decide(bare), "deny")
            self.assertIn("A tester writes in a worktree", reason(bare))
            write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."))
            self.assertEqual(decide(tester), "deny")
        finally:
            self.settings.write_text(original, encoding="utf-8")

    def test_caller_itself_skipped(self):
        write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."))
        self.assertEqual(decide(self.implementer(agent_id="a1")), "allow")

    def test_no_transcript_allows(self):
        event = self.agent(model="sonnet")
        self.assertEqual(decide(event), "allow")

    def test_writing_custom_role(self):
        prompt = f"Task directory: {self.task_dir}\nFix it."
        event = self.perf_call(prompt)
        self.assertEqual(decide(event), "deny")
        self.assertIn("The writing custom role perf-fixer", reason(event))
        self.assertEqual(decide(self.perf_call()), "allow")
        write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."))
        self.assertEqual(decide(self.perf_call()), "deny")

    def test_read_only_custom_role_not_locked(self):
        write_sub(self.session_dir, "a1", IMPLEMENTER, self.brief("Pass 1."))
        prompt = f"Instructions: {self.instructions}\nReview."
        event = self.with_transcript(self.agent(subagent_type="general-purpose", model="opus",
                                                effort="high", prompt=prompt))
        self.assertEqual(decide(event), "allow")


class ReadOnlyRoleWriteTest(HomeFixture):
    """Rule 12."""

    def setUp(self):
        self.session_tmp = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.session_tmp.name) / "session"
        self.transcript = str(self.session_dir) + ".jsonl"
        self.task_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.session_tmp.cleanup()

    def reviewer_brief(self, task_dir=None):
        return self.brief(f"Instructions: {self.instructions}\nRead-only.", task_dir=task_dir)

    def write_event(self, path, agent_id="ro1", agent_type="general-purpose", tool="Write", cwd=None):
        tool_input = {"file_path": str(path), "content": "x"}
        event = {"tool_name": tool, "tool_input": tool_input, "session_id": SESSION,
                 "transcript_path": self.transcript, "agent_id": agent_id, "agent_type": agent_type}
        if cwd is not None:
            event["cwd"] = str(cwd)
        return event

    def test_outside_task_directory_denied(self):
        write_sub(self.session_dir, "ro1", "general-purpose", self.reviewer_brief())
        for tool in ("Write", "Edit", "MultiEdit"):
            with self.subTest(tool=tool):
                event = self.write_event(self.worktree / "src.py", tool=tool)
                self.assertEqual(decide(event), "deny")
                self.assertIn("security-reviewer is read-only", reason(event))
                self.assertIn(str(self.task_dir), reason(event))

    def test_inside_task_directory_allowed(self):
        write_sub(self.session_dir, "ro1", "general-purpose", self.reviewer_brief())
        self.assertEqual(decide(self.write_event(self.task_dir / "custom-security-reviewer-1.md")), "allow")
        relative = self.write_event("custom-security-reviewer-1.md", cwd=self.task_dir)
        self.assertEqual(decide(relative), "allow")

    def test_dot_dot_escape_denied(self):
        write_sub(self.session_dir, "ro1", "general-purpose", self.reviewer_brief())
        self.assertEqual(decide(self.write_event(f"{self.task_dir}/../gh-2/x.md")), "deny")

    def test_symlink_escape_denied(self):
        write_sub(self.session_dir, "ro1", "general-purpose", self.reviewer_brief())
        link = self.task_dir / "escape"
        if not link.exists():
            link.symlink_to(self.worktree)
        self.assertEqual(decide(self.write_event(link / "src.py")), "deny")

    def test_untrusted_task_directory_denied(self):
        foreign = Path(self.session_tmp.name) / "other-home" / "projects" / "app" / "tasks" / "gh-1"
        write_sub(self.session_dir, "ro1", "general-purpose", self.reviewer_brief(task_dir=foreign) )
        event = self.write_event(foreign / "notes.md", cwd=self.repo)
        self.assertEqual(decide(event), "deny")
        self.assertIn("no Task directory line in the work home", reason(event))

    def test_notebook_edit_denied(self):
        write_sub(self.session_dir, "ro1", "general-purpose", self.reviewer_brief())
        event = self.write_event(self.worktree / "a.ipynb", tool="NotebookEdit")
        event["tool_input"] = {"notebook_path": str(self.worktree / "a.ipynb")}
        self.assertEqual(decide(event), "deny")

    def test_writing_role_allowed(self):
        write_sub(self.session_dir, "w1", "perf-agent", self.brief("Fix it."))
        self.assertEqual(decide(self.write_event(self.worktree / "src.py", "w1", "perf-agent")), "allow")

    def test_plain_general_purpose_allowed(self):
        write_sub(self.session_dir, "g1", "general-purpose", self.brief("Search for X."))
        self.assertEqual(decide(self.write_event(self.worktree / "src.py", "g1")), "allow")

    def test_plugin_agent_skipped(self):
        write_sub(self.session_dir, "p1", IMPLEMENTER, self.reviewer_brief())
        self.assertEqual(decide(self.write_event(self.worktree / "src.py", "p1", IMPLEMENTER)), "allow")

    def test_without_agent_id_allowed(self):
        event = self.write_event(self.worktree / "src.py")
        del event["agent_id"]
        self.assertEqual(decide(event), "allow")

    def test_unsafe_agent_id_skipped(self):
        write_sub(self.session_dir, "ro1", "general-purpose", self.reviewer_brief())
        self.assertEqual(decide(self.write_event(self.worktree / "src.py", agent_id="../ro1")), "allow")

    def test_missing_transcript_allowed(self):
        self.assertEqual(decide(self.write_event(self.worktree / "src.py", agent_id="nobody")), "allow")


class TrustedHomeTest(HomeFixture):
    """Hardening: the brief's home must be the trusted home (rules 5-9) and
    the settings-file target is resolved before rule 11 checks it."""

    def setUp(self):
        self.other = tempfile.TemporaryDirectory()
        self.foreign_home = Path(self.other.name).resolve() / "home"
        project = self.foreign_home / "projects" / "app"
        project.mkdir(parents=True)
        data = settings_data(self.repo, self.instructions)
        data["custom_roles"][0]["model"] = "haiku"
        data["roles_off"] = []
        (project / "settings.json").write_text(json.dumps(data), encoding="utf-8")
        write_run(self.foreign_home, "app", "20261112-0100", "active", "sess-foreign")
        self.foreign_task = project / "tasks" / "gh-1"

    def tearDown(self):
        self.other.cleanup()

    def test_plugin_call_outside_home_denied(self):
        event = self.agent(subagent_type="orchestrator:planner", prompt=self.brief(task_dir=self.foreign_task),
                           raw=True, session="sess-foreign")
        self.assertEqual(decide(event), "deny")
        self.assertIn("Task directory is outside the work home", reason(event))

    def test_symlinked_home_allowed(self):
        link = Path(self.other.name) / "home-link"
        link.symlink_to(self.home)
        task = link / "projects" / "app" / "tasks" / "gh-1"
        event = self.agent(subagent_type="orchestrator:planner", prompt=self.brief(task_dir=task), raw=True)
        self.assertEqual(decide(event), "allow")

    def test_custom_role_uses_trusted_settings(self):
        prompt = self.brief(f"Instructions: {self.instructions}\nReview.", task_dir=self.foreign_task)
        event = self.agent(subagent_type="general-purpose", model="haiku", effort="high", prompt=prompt,
                           raw=True, cwd=self.repo)
        self.assertEqual(decide(event), "deny")
        self.assertIn(str(self.settings), reason(event))

    def settings_write(self, path, cwd=None, content="{oops"):
        event = {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": content},
                 "session_id": SESSION}
        if cwd is not None:
            event["cwd"] = str(cwd)
        return event

    def test_symlink_to_project_checked(self):
        link = Path(self.other.name) / "proj-link"
        link.symlink_to(self.project)
        event = self.settings_write(link / "settings.json")
        self.assertEqual(decide(event), "deny")
        self.assertIn("not valid JSON", reason(event))

    def test_symlink_named_otherwise_checked(self):
        link = Path(self.other.name) / "innocent.json"
        link.symlink_to(self.settings)
        self.assertEqual(decide(self.settings_write(link)), "deny")

    def test_relative_target_checked(self):
        event = self.settings_write("settings.json", cwd=self.project)
        self.assertEqual(decide(event), "deny")
        event = self.settings_write("../settings.json", cwd=self.project / "roles")
        self.assertEqual(decide(event), "deny")

    def test_home_case_variant_checked(self):
        variant = Path(str(self.home).swapcase())
        if not variant.exists():
            self.skipTest("case-sensitive file system")
        event = self.settings_write(variant / "projects" / "app" / "settings.json")
        self.assertEqual(decide(event), "deny")

    def test_foreign_home_settings_ignored(self):
        self.assertEqual(decide(self.settings_write(self.foreign_home / "projects" / "app" / "settings.json")), "allow")


class RepoHomeTest(unittest.TestCase):
    """A session started outside the repository: the brief's home is trusted
    when the repository in that project's settings names it in CLAUDE.md."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.parent = self.root / "work"
        self.repo = self.parent / "app"
        (self.repo / ".git").mkdir(parents=True)
        self.home = self.root / "app-home"
        (self.repo / "CLAUDE.md").write_text(f"Subagent orchestrator home: {self.home}\n", encoding="utf-8")
        self.instructions = self.root / "role.md"
        self.instructions.write_text("Check.", encoding="utf-8")
        self.forged = self.root / "forged"
        for home in (self.home, self.forged):
            project = home / "projects" / "app"
            project.mkdir(parents=True)
            data = settings_data(self.repo, self.instructions)
            (project / "settings.json").write_text(json.dumps(data), encoding="utf-8")
            write_run(home, "app", "20261112-1000", "active", SESSION)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, event):
        env = {k: v for k, v in os.environ.items() if k != "SUBAGENT_ORCHESTRATOR_HOME"}
        env.update(HOME=str(self.root / "user"), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True,
                                text=True, timeout=20, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else None

    def planner(self, home):
        prompt = f"Task directory: {home}/projects/app/tasks/gh-1\nTask: gh-1, plan\n"
        return {"tool_name": "Agent", "session_id": SESSION, "cwd": str(self.parent),
                "tool_input": {"subagent_type": "orchestrator:planner", "model": "opus", "prompt": prompt}}

    def test_home_named_by_repository_allowed(self):
        self.assertIsNone(self.hook(self.planner(self.home)))

    def test_forged_home_denied(self):
        out = self.hook(self.planner(self.forged))
        self.assertEqual(out["permissionDecision"], "deny")
        text = out["permissionDecisionReason"]
        self.assertIn("Task directory is outside the work home", text)
        self.assertIn(f"cwd {self.parent}", text)
        self.assertIn(f"CLAUDE.md names {self.forged}", text)
        self.assertIn("SUBAGENT_ORCHESTRATOR_HOME", text)
        self.assertNotIn("/orchestrator:setup", text)

    def test_named_home_without_settings_points_to_setup(self):
        settings = self.home / "projects" / "app" / "settings.json"
        for content in (None, "{oops"):
            with self.subTest(content=content):
                if content is None:
                    settings.unlink()
                else:
                    settings.write_text(content, encoding="utf-8")
                out = self.hook(self.planner(self.home))
                self.assertEqual(out["permissionDecision"], "deny")
                self.assertIn("no valid settings.json yet: run /orchestrator:setup",
                              out["permissionDecisionReason"])

    def test_settings_write_in_named_home_checked(self):
        target = self.home / "projects" / "app" / "settings.json"
        event = {"tool_name": "Write", "cwd": str(self.parent),
                 "tool_input": {"file_path": str(target), "content": "{oops"}}
        self.assertEqual(self.hook(event)["permissionDecision"], "deny")
        event["tool_input"]["file_path"] = str(self.forged / "projects" / "app" / "settings.json")
        self.assertIsNone(self.hook(event))


class ReadTest(unittest.TestCase):
    def read(self, path, agent_type=None):
        event = {"tool_name": "Read", "tool_input": {"file_path": path}}
        if agent_type is not None:
            event["agent_type"] = agent_type
        return event

    def test_image_from_implementer_denied(self):
        event = self.read("/tmp/shot.png", IMPLEMENTER)
        self.assertEqual(decide(event), "deny")
        self.assertIn("visual-checker", reason(event))

    def test_every_image_extension_denied(self):
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".PNG"):
            with self.subTest(ext=ext):
                self.assertEqual(decide(self.read("/tmp/shot" + ext, "orchestrator:reviewer")), "deny")

    def test_image_from_every_other_plugin_role_denied(self):
        for role in ("scout", "planner", "implementer", "reviewer", "tester"):
            with self.subTest(role=role):
                self.assertEqual(decide(self.read("/tmp/a.jpg", "orchestrator:" + role)), "deny")

    def test_image_from_foreign_subagents_allowed(self):
        for agent_type in ("general-purpose", "Explore", "Plan", "other-plugin:reviewer"):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(decide(self.read("/tmp/a.jpg", agent_type)), "allow")

    def test_image_from_bare_visual_checker_allowed(self):
        self.assertEqual(decide(self.read("/tmp/shot.png", "visual-checker")), "allow")

    def test_image_from_visual_checker_allowed(self):
        self.assertEqual(decide(self.read("/tmp/shot.png", "orchestrator:visual-checker")), "allow")

    def test_image_from_main_session_allowed(self):
        self.assertEqual(decide(self.read("/tmp/shot.png")), "allow")

    def test_text_file_from_subagent_allowed(self):
        self.assertEqual(decide(self.read("/tmp/notes.md", IMPLEMENTER)), "allow")

    def test_missing_path_allowed(self):
        event = {"tool_name": "Read", "tool_input": {}, "agent_type": IMPLEMENTER}
        self.assertEqual(decide(event), "allow")


class FailOpenTest(unittest.TestCase):
    def assert_allows(self, stdin_text):
        result = run_raw(stdin_text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_malformed_json(self):
        self.assert_allows("{not json")

    def test_empty_stdin(self):
        self.assert_allows("")

    def test_non_object_json(self):
        self.assert_allows("[1, 2, 3]")

    def test_unknown_tool(self):
        self.assert_allows(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))

    def test_missing_tool_name(self):
        self.assert_allows(json.dumps({"tool_input": {}}))

    def test_wrong_field_types(self):
        self.assert_allows(json.dumps({"tool_name": "Agent", "tool_input": "text"}))
        self.assert_allows(json.dumps({"tool_name": "Write", "tool_input": None}))
        self.assert_allows(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": 5}}))
        self.assert_allows(json.dumps({"tool_name": "Read", "tool_input": None, "agent_type": 5}))


if __name__ == "__main__":
    unittest.main()
