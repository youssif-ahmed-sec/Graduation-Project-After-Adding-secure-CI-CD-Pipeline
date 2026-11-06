
import ast
import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch


CLIENT_FILE = (
    Path(__file__).resolve().parents[1]
    / "agent"
    / "client.py"
)


class AgentClientCredentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(
            CLIENT_FILE.read_text(encoding="utf-8")
        )

        client_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "FileTrackClient"
        )

        method = copy.deepcopy(
            next(
                node for node in client_class.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "get_enrolled_agent_headers"
            )
        )

        isolated_class = ast.ClassDef(
            name="IsolatedAgentClient",
            bases=[],
            keywords=[],
            body=[method],
            decorator_list=[],
        )

        module = ast.Module(
            body=[isolated_class],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)

        namespace = {"os": os}
        exec(
            compile(module, str(CLIENT_FILE), "exec"),
            namespace,
        )

        cls.client_class = namespace["IsolatedAgentClient"]

    def setUp(self):
        self.client = self.client_class()
        self.client.agent_id = "agent-a"

    def test_enrolled_credential_headers(self):
        with patch.dict(
            os.environ,
            {"FILETRACK_AGENT_CREDENTIAL": "test-secret"},
        ):
            headers = self.client.get_enrolled_agent_headers()

        self.assertEqual(
            headers["Authorization"],
            "Bearer test-secret",
        )
        self.assertEqual(headers["X-Agent-ID"], "agent-a")
        self.assertNotIn("Content-Type", headers)

    def test_missing_credential_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                self.client.get_enrolled_agent_headers()

    def test_empty_credential_is_rejected(self):
        with patch.dict(
            os.environ,
            {"FILETRACK_AGENT_CREDENTIAL": ""},
        ):
            with self.assertRaises(RuntimeError):
                self.client.get_enrolled_agent_headers()

    def test_credential_with_surrounding_spaces_is_rejected(self):
        with patch.dict(
            os.environ,
            {"FILETRACK_AGENT_CREDENTIAL": " test-secret "},
        ):
            with self.assertRaises(RuntimeError):
                self.client.get_enrolled_agent_headers()


if __name__ == "__main__":
    unittest.main()
