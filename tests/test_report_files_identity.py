
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


class TestReportFilesIdentity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "report_files"
        )

        function.decorator_list = []

        module = ast.Module(
            body=[function],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)

        cls.flask_app = Flask(__name__)
        cls.verify_agent = MagicMock(return_value="agent-001")
        cls.file_explorer_results = {}

        namespace = {
            "request": request,
            "jsonify": jsonify,
            "verify_registered_agent_request": cls.verify_agent,
            "file_explorer_results": cls.file_explorer_results,
        }

        exec(
            compile(module, "<report-files-test>", "exec"),
            namespace,
        )

        cls.handler = staticmethod(namespace["report_files"])

    def setUp(self):
        self.verify_agent.reset_mock()
        self.verify_agent.return_value = "agent-001"
        self.file_explorer_results.clear()

    def call_handler(self, data):
        with self.flask_app.test_request_context(
            "/api/v1/report_files",
            method="POST",
            json=data,
        ):
            response, status = self.handler()

        return response.get_json(), status

    def test_authenticated_agent_can_report_files(self):
        file_data = [{"name": "example.txt"}]

        _, status = self.call_handler({
            "agent_id": "agent-001",
            "data": file_data,
        })

        self.assertEqual(status, 200)
        self.assertEqual(
            self.file_explorer_results["agent-001"],
            file_data,
        )

    def test_agent_cannot_overwrite_another_agents_results(self):
        original_data = [{"name": "private.txt"}]
        self.file_explorer_results["agent-002"] = original_data

        _, status = self.call_handler({
            "agent_id": "agent-002",
            "data": [{"name": "malicious.txt"}],
        })

        self.assertEqual(status, 403)
        self.assertEqual(
            self.file_explorer_results["agent-002"],
            original_data,
        )
        self.assertNotIn(
            "agent-001",
            self.file_explorer_results,
        )

    def test_unauthenticated_request_is_rejected(self):
        self.verify_agent.return_value = None

        _, status = self.call_handler({
            "agent_id": "agent-001",
            "data": [{"name": "example.txt"}],
        })

        self.assertEqual(status, 403)
        self.assertEqual(self.file_explorer_results, {})

    def test_missing_agent_id_is_rejected(self):
        _, status = self.call_handler({
            "data": [{"name": "example.txt"}],
        })

        self.assertEqual(status, 403)
        self.assertEqual(self.file_explorer_results, {})

    def test_missing_file_data_is_rejected(self):
        _, status = self.call_handler({
            "agent_id": "agent-001",
        })

        self.assertEqual(status, 400)
        self.assertEqual(self.file_explorer_results, {})

    def test_invalid_json_body_is_rejected(self):
        _, status = self.call_handler([])

        self.assertEqual(status, 400)
        self.assertEqual(self.file_explorer_results, {})


if __name__ == "__main__":
    unittest.main()
