import ast
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock

from flask import Flask, jsonify, request, g


APP_FILE = Path(__file__).resolve().parents[1] / "server" / "app.py"


class AgentApprovalTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(APP_FILE.read_text(encoding="utf-8"))

        endpoint = copy.deepcopy(
            next(
                node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "approve_agent_endpoint"
            )
        )
        endpoint.decorator_list = []

        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.db = Mock()

        namespace = {
            "request": request,
            "jsonify": jsonify,
            "db": self.db,
            "app": self.app,
        }

        module = ast.Module(
            body=[endpoint],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)
        exec(
            compile(module, str(APP_FILE), "exec"),
            namespace,
        )

        self.app.add_url_rule(
            "/api/v1/admin/agents/approve",
            view_func=namespace["approve_agent_endpoint"],
            methods=["POST"],
        )

        self.client = self.app.test_client()

    def test_approval_creates_pending_agent(self):
        self.db.create_pending_agent.return_value = True

        response = self.client.post(
            "/api/v1/admin/agents/approve",
            json={"agent_id": "agent-a"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json()["agent_status"],
            "Pending",
        )
        self.db.create_pending_agent.assert_called_once_with("agent-a")

    def test_duplicate_agent_is_rejected(self):
        self.db.create_pending_agent.return_value = False

        response = self.client.post(
            "/api/v1/admin/agents/approve",
            json={"agent_id": "agent-a"},
        )

        self.assertEqual(response.status_code, 409)

    def test_invalid_agent_id_is_rejected(self):
        for invalid in ("", " agent-a ", 123, None, "x" * 129):
            with self.subTest(value=invalid):
                self.db.reset_mock()

                response = self.client.post(
                    "/api/v1/admin/agents/approve",
                    json={"agent_id": invalid},
                )

                self.assertEqual(response.status_code, 400)
                self.db.create_pending_agent.assert_not_called()

    def test_database_error_is_sanitized(self):
        self.db.create_pending_agent.side_effect = RuntimeError(
            "Sensitive internal database details"
        )

        response = self.client.post(
            "/api/v1/admin/agents/approve",
            json={"agent_id": "agent-a"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "Sensitive internal database details",
            response.get_data(as_text=True),
        )


if __name__ == "__main__":
    unittest.main()
