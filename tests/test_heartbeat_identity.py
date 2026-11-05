
import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask, jsonify, request


APP_FILE = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "app.py"
)


class TestHeartbeatIdentity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "receive_heartbeat"
        )

        # Test the handler independently of its route decorator.
        function.decorator_list = []

        module = ast.Module(
            body=[function],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)

        cls.flask_app = Flask(__name__)
        cls.verify_agent = MagicMock(return_value="agent-001")
        cls.db = MagicMock()
        cls.active_tasks = {}

        namespace = {
            "request": request,
            "jsonify": jsonify,
            "verify_registered_agent_request": cls.verify_agent,
            "db": cls.db,
            "active_tasks": cls.active_tasks,
        }

        exec(
            compile(module, "<heartbeat-test>", "exec"),
            namespace,
        )

        cls.handler = staticmethod(namespace["receive_heartbeat"])

    def setUp(self):
        self.verify_agent.reset_mock()
        self.verify_agent.return_value = "agent-001"
        self.db.reset_mock()
        self.active_tasks.clear()

    def call_handler(self, data):
        with self.flask_app.test_request_context(
            "/api/v1/heartbeat",
            method="POST",
            json=data,
        ):
            response, status = self.handler()

        return response.get_json(), status

    def test_valid_agent_receives_own_task(self):
        self.active_tasks["agent-001"] = {
            "command": "TEST_ONLY"
        }

        body, status = self.call_handler({
            "agent_id": "agent-001"
        })

        self.assertEqual(status, 200)
        self.assertEqual(
            body["task"],
            {"command": "TEST_ONLY"}
        )
        self.db.update_heartbeat.assert_called_once_with(
            "agent-001"
        )

    def test_agent_cannot_access_another_agents_tasks(self):
        self.active_tasks["agent-002"] = {
            "command": "TEST_ONLY"
        }

        _, status = self.call_handler({
            "agent_id": "agent-002"
        })

        self.assertEqual(status, 403)
        self.db.update_heartbeat.assert_not_called()
        self.assertIn("agent-002", self.active_tasks)

    def test_unauthenticated_request_is_rejected(self):
        self.verify_agent.return_value = None

        _, status = self.call_handler({
            "agent_id": "agent-001"
        })

        self.assertEqual(status, 403)
        self.db.update_heartbeat.assert_not_called()

    def test_missing_agent_id_is_rejected(self):
        _, status = self.call_handler({})

        self.assertEqual(status, 403)
        self.db.update_heartbeat.assert_not_called()

    def test_invalid_json_body_is_rejected(self):
        _, status = self.call_handler([])

        self.assertEqual(status, 400)
        self.db.update_heartbeat.assert_not_called()

    def test_successful_task_is_removed_once(self):
        self.active_tasks["agent-001"] = {
            "command": "TEST_ONLY"
        }

        _, first_status = self.call_handler({
            "agent_id": "agent-001"
        })

        second_body, second_status = self.call_handler({
            "agent_id": "agent-001"
        })

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertIsNone(second_body["task"])
