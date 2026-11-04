
import ast
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from flask import Flask, jsonify, request


class TestThreatLogging(unittest.TestCase):

    def setUp(self):
        source = Path("server/app.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)

        function_node = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "log_threat"
        )

        # Remove Flask decorators in this isolated test.
        function_node.decorator_list = []

        self.app = Flask(__name__)
        self.fake_db = Mock()
        self.fake_socketio = Mock()

        namespace = {
            "request": request,
            "jsonify": jsonify,
            "json": json,
            "db": self.fake_db,
            "socketio": self.fake_socketio,
            "app": self.app,
            "verify_agent": lambda req: True,
        }

        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(
                        body=[function_node],
                        type_ignores=[],
                    )
                ),
                "<threat-logging-test>",
                "exec",
            ),
            namespace,
        )

        self.app.add_url_rule(
            "/api/v1/log_threat",
            view_func=namespace["log_threat"],
            methods=["POST"],
        )

        self.payload = {
            "agent_id": "test-agent",
            "action_type": "EDITED",
            "file_path": "test-file.txt",
            "severity_level": "High",
        }

    def test_returns_real_log_id(self):
        self.fake_db.log_threat.return_value = 42

        with self.app.test_client() as client:
            response = client.post(
                "/api/v1/log_threat",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "success", "log_id": 42},
        )

        self.fake_db.log_threat.assert_called_once()

        self.fake_socketio.emit.assert_called_once()
        self.assertEqual(
            self.fake_socketio.emit.call_args.args[1]["log_id"],
            42,
        )

    def test_does_not_attach_recent_evidence(self):
        self.fake_db.log_threat.return_value = 42

        with self.app.test_client() as client:
            response = client.post(
                "/api/v1/log_threat",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)

        saved_data = self.fake_db.log_threat.call_args.args[0]

        for field in (
            "screenshot_path",
            "camera_path",
            "audio_path",
            "dump_path",
        ):
            self.assertNotIn(field, saved_data)

        self.fake_db.attach_artifact.assert_not_called()
        self.fake_db.attach_artifact_to_log.assert_not_called()

    def test_database_error_does_not_leak_details(self):
        secret_error = "Sensitive database connection details"

        self.fake_db.log_threat.side_effect = RuntimeError(
            secret_error
        )

        with self.app.test_client() as client:
            response = client.post(
                "/api/v1/log_threat",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 500)
        self.assertNotIn(
            secret_error,
            response.get_data(as_text=True),
        )

        self.fake_socketio.emit.assert_not_called()

    def test_socketio_failure_does_not_fail_incident_registration(self):
        self.fake_db.log_threat.return_value = 42
        self.fake_socketio.emit.side_effect = RuntimeError(
            "Simulated Socket.IO notification failure"
        )

        with self.app.test_client() as client:
            response = client.post(
                "/api/v1/log_threat",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "status": "success",
                "log_id": 42,
            },
        )

        self.fake_db.log_threat.assert_called_once()
        self.fake_socketio.emit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
