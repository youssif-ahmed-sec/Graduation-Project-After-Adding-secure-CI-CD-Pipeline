
import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask, request


APP_FILE = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "app.py"
)


class TestRegisteredAgentRESTAuth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "verify_registered_agent_request"
        )

        module = ast.Module(
            body=[function],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)

        cls.flask_app = Flask(__name__)

        cls.authenticate = MagicMock(return_value=True)
        cls.load_pepper = MagicMock(
            return_value="test-only-pepper-32-characters-minimum"
        )
        cls.db = MagicMock()

        namespace = {
            "db": cls.db,
            "app": cls.flask_app,
            "authenticate_registered_agent": cls.authenticate,
            "load_agent_credential_pepper": cls.load_pepper,
        }

        exec(
            compile(module, "<rest-auth-test>", "exec"),
            namespace,
        )

        cls.verify_request = staticmethod(
            namespace["verify_registered_agent_request"]
        )

    def setUp(self):
        self.authenticate.reset_mock()
        self.load_pepper.reset_mock()
        self.authenticate.return_value = True
        self.authenticate.side_effect = None
        self.load_pepper.side_effect = None

    def call_helper(self, headers=None):
        with self.flask_app.test_request_context(
            "/api/v1/heartbeat",
            method="POST",
            headers=headers or {},
        ):
            return self.verify_request(request)

    def test_valid_agent_is_authenticated(self):
        result = self.call_helper({
            "Authorization": "Bearer test-agent-credential",
            "X-Agent-ID": "agent-001",
        })

        self.assertEqual(result, "agent-001")

        self.authenticate.assert_called_once_with(
            "agent-001",
            "test-agent-credential",
            self.db,
            "test-only-pepper-32-characters-minimum",
        )

    def test_missing_authorization_is_rejected(self):
        result = self.call_helper({
            "X-Agent-ID": "agent-001",
        })

        self.assertIsNone(result)
        self.authenticate.assert_not_called()

    def test_missing_agent_id_is_rejected(self):
        result = self.call_helper({
            "Authorization": "Bearer test-agent-credential",
        })

        self.assertIsNone(result)
        self.authenticate.assert_not_called()

    def test_invalid_bearer_headers_are_rejected(self):
        invalid_headers = (
            "Basic credential",
            "Bearer",
            "Bearer ",
            "Bearer  credential",
            "Bearer credential ",
        )

        for authorization in invalid_headers:
            with self.subTest(authorization=authorization):
                self.authenticate.reset_mock()

                result = self.call_helper({
                    "Authorization": authorization,
                    "X-Agent-ID": "agent-001",
                })

                self.assertIsNone(result)
                self.authenticate.assert_not_called()

    def test_failed_authentication_is_rejected(self):
        self.authenticate.return_value = False

        result = self.call_helper({
            "Authorization": "Bearer wrong-credential",
            "X-Agent-ID": "agent-001",
        })

        self.assertIsNone(result)

    def test_database_failure_is_rejected(self):
        self.authenticate.side_effect = RuntimeError(
            "Simulated database failure"
        )

        result = self.call_helper({
            "Authorization": "Bearer test-agent-credential",
            "X-Agent-ID": "agent-001",
        })

        self.assertIsNone(result)

    def test_missing_pepper_is_rejected(self):
        self.load_pepper.side_effect = RuntimeError(
            "Simulated missing pepper"
        )

        result = self.call_helper({
            "Authorization": "Bearer test-agent-credential",
            "X-Agent-ID": "agent-001",
        })

        self.assertIsNone(result)
        self.authenticate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
