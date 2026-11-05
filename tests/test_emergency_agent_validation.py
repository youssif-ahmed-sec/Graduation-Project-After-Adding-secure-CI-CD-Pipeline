
import ast
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask, jsonify, request


APP_FILE = Path(__file__).resolve().parents[1] / "server" / "app.py"


class TestEmergencyAgentValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "emergency_containment"
        )

        # Test the handler without starting Flask or Socket.IO.
        function.decorator_list = []
        module = ast.Module(body=[function], type_ignores=[])
        ast.fix_missing_locations(module)

        cls.flask_app = Flask(__name__)
        cls.db = MagicMock()
        cls.socketio = MagicMock()

        namespace = {
            "request": request,
            "jsonify": jsonify,
            "db": cls.db,
            "socketio": cls.socketio,
            "time": time,
            "app": cls.flask_app,
            "get_username_from_token": lambda req: "test-superadmin",
        }

        exec(
            compile(module, "<emergency-test>", "exec"),
            namespace,
        )

        cls.handler = staticmethod(namespace["emergency_containment"])

    def setUp(self):
        self.db.reset_mock()
        self.socketio.reset_mock()
        self.db.agent_exists.side_effect = None
        self.db.agent_exists.return_value = True

    def call_handler(self, data):
        with self.flask_app.test_request_context(
            "/api/v1/admin/emergency_action",
            method="POST",
            json=data,
        ):
            response, status = self.handler()

        return response.get_json(), status

    def test_invalid_agent_id_does_not_emit(self):
        for agent_id in (None, "", " ", 123, [], {}):
            with self.subTest(agent_id=agent_id):
                self.db.reset_mock()
                self.socketio.reset_mock()

                _, status = self.call_handler({
                    "agent_id": agent_id,
                    "action": "ISOLATE_NETWORK",
                })

                self.assertEqual(status, 400)
                self.socketio.emit.assert_not_called()

    def test_unknown_agent_does_not_emit(self):
        self.db.agent_exists.return_value = False

        _, status = self.call_handler({
            "agent_id": "unknown-agent",
            "action": "ISOLATE_NETWORK",
        })

        self.assertEqual(status, 404)
        self.socketio.emit.assert_not_called()

    def test_database_failure_does_not_emit(self):
        self.db.agent_exists.side_effect = RuntimeError(
            "Simulated database failure"
        )

        _, status = self.call_handler({
            "agent_id": "agent-001",
            "action": "ISOLATE_NETWORK",
        })

        self.assertEqual(status, 503)
        self.socketio.emit.assert_not_called()

    def test_invalid_action_does_not_emit(self):
        _, status = self.call_handler({
            "agent_id": "agent-001",
            "action": "UNKNOWN_ACTION",
        })

        self.assertEqual(status, 400)
        self.socketio.emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
