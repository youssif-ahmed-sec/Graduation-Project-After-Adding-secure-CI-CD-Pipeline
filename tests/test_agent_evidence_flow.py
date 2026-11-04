
import ast
import copy
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WATCHER_PATH = PROJECT_ROOT / "agent" / "modules" / "watcher.py"


def load_network_flow():
    source = WATCHER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    handler = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "HoneyFileHandler"
    )

    process = next(
        node for node in handler.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "process"
    )

    start = next(
        i for i, node in enumerate(process.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "alert_payload"
            for target in node.targets
        )
    )

    register_try = next(
        i for i in range(start, len(process.body))
        if isinstance(process.body[i], ast.Try)
    )

    upload_if = next(
        i for i in range(register_try + 1, len(process.body))
        if isinstance(process.body[i], ast.If)
        and isinstance(process.body[i].test, ast.Compare)
        and isinstance(process.body[i].test.left, ast.Name)
        and process.body[i].test.left.id == "server_log_id"
    )

    # Extract only network communication statements.
    statements = copy.deepcopy(
        process.body[start:upload_if + 1]
    )

    isolated = ast.parse(
        "def isolated_flow(self):\n    pass\n"
    )
    isolated.body[0].body = statements

    namespace = {}
    exec(
        compile(
            ast.fix_missing_locations(isolated),
            str(WATCHER_PATH),
            "exec",
        ),
        namespace,
    )

    return namespace["isolated_flow"]


class TestAgentEvidenceFlow(unittest.TestCase):

    def setUp(self):
        self.flow = load_network_flow()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.file_path = Path(self.temp_dir.name) / "ss_test.png"
        self.file_path.write_bytes(b"safe-test-evidence")

        self.agent = SimpleNamespace(
            agent_id="test-agent",
            base_url="https://test.invalid/api/v1",
            get_secure_headers=lambda: {
                "Authorization": "Bearer test-only-token"
            },
        )

        self.handler = SimpleNamespace(agent=self.agent)

        self.log_response = Mock()
        self.log_response.json.return_value = {"log_id": 42}

        self.upload_response = Mock()

        self.post = Mock(
            side_effect=[
                self.log_response,
                self.upload_response,
            ]
        )

        self.network = SimpleNamespace(
            post=self.post,
            RequestException=requests.RequestException,
        )

    def run_flow(self):
        # These globals are test-only values.
        # No Agent, Playbook or containment code is executed.
        self.flow.__globals__.update({
            "requests": self.network,
            "os": os,
            "time": time,
            "evidence": {
                "screenshot": str(self.file_path)
            },
            "action": "EDITED",
            "abs_path": "test-file.txt",
            "hash_before": "before",
            "hash_after": "after",
            "action_status": "Logged",
            "attacker_pid": None,
            "process_tree": [],
        })

        self.flow(self.handler)

    def test_registers_incident_before_upload(self):
        self.run_flow()

        self.assertEqual(self.post.call_count, 2)

        first = self.post.call_args_list[0]
        second = self.post.call_args_list[1]

        self.assertTrue(first.args[0].endswith("/log_threat"))
        self.assertTrue(second.args[0].endswith("/upload_artifact"))

        self.assertEqual(
            second.kwargs["data"]["log_id"],
            "42",
        )

        self.assertEqual(
            second.kwargs["data"]["agent_id"],
            "test-agent",
        )

    def test_does_not_upload_when_registration_fails(self):
        self.log_response.raise_for_status.side_effect = (
            requests.HTTPError("Simulated registration failure")
        )

        self.run_flow()

        self.assertEqual(self.post.call_count, 1)
        self.assertTrue(
            self.post.call_args.args[0].endswith("/log_threat")
        )

    def test_rejects_invalid_server_log_id(self):
        for invalid_response in (
            {"log_id": "LOG_123"},
            {"log_id": 0},
            {"log_id": None},
            [],
            None,
        ):
            with self.subTest(response=invalid_response):
                self.post.reset_mock()
                self.log_response.reset_mock()

                self.log_response.json.return_value = (
                    invalid_response
                )
                self.post.side_effect = [
                    self.log_response,
                    self.upload_response,
                ]

                self.run_flow()
                self.assertEqual(self.post.call_count, 1)

    def test_upload_failure_does_not_change_incident(self):
        self.upload_response.raise_for_status.side_effect = (
            requests.HTTPError("Simulated upload failure")
        )

        self.run_flow()

        self.assertEqual(self.post.call_count, 2)
        self.assertEqual(
            self.post.call_args_list[1].kwargs["data"]["log_id"],
            "42",
        )


if __name__ == "__main__":
    unittest.main()
