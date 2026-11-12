#!/usr/bin/env python3
"""Behaviour of plugins/orchestrator/hooks/subagent-guard.py on synthetic events."""

import json
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


def run_raw(stdin_text):
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True, timeout=20
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
        for name in ("SendMessage", "Agent", "Read"):
            self.assertIn(name, entry["matcher"])
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


class AgentTest(unittest.TestCase):
    def agent(self, subagent_type=IMPLEMENTER, model="opus", prompt="Do the work."):
        tool_input = {"subagent_type": subagent_type, "prompt": prompt}
        if model is not None:
            tool_input["model"] = model
        return {"tool_name": "Agent", "tool_input": tool_input}

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

    def test_other_type_without_model_allowed(self):
        self.assertEqual(decide(self.agent(subagent_type="orchestrator:planner", model=None)), "allow")
        self.assertEqual(decide(self.agent(subagent_type="general-purpose", model=None)), "allow")

    def test_other_type_on_opus_allowed(self):
        self.assertEqual(decide(self.agent(subagent_type="orchestrator:planner")), "allow")

    def test_general_purpose_allowed(self):
        self.assertEqual(decide(self.agent(subagent_type="general-purpose")), "allow")


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
        self.assert_allows(json.dumps({"tool_name": "Read", "tool_input": None, "agent_type": 5}))


if __name__ == "__main__":
    unittest.main()
