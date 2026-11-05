
import ast
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock


DB_FILE = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "db_manager.py"
)


class AgentCredentialDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(DB_FILE.read_text(encoding="utf-8"))

        manager = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DBManager"
        )

        method_names = (
            "create_pending_agent_credential",
            "activate_agent_credential",
            "revoke_agent_credential",
        )

        methods = [
            copy.deepcopy(node)
            for node in manager.body
            if isinstance(node, ast.FunctionDef)
            and node.name in method_names
        ]

        isolated_class = ast.ClassDef(
            name="IsolatedDBManager",
            bases=[],
            keywords=[],
            body=methods,
            decorator_list=[],
        )

        module = ast.Module(
            body=[isolated_class],
            type_ignores=[],
        )

        ast.fix_missing_locations(module)

        namespace = {}

        exec(
            compile(module, str(DB_FILE), "exec"),
            namespace,
        )

        cls.manager_class = namespace["IsolatedDBManager"]

    def setUp(self):
        self.manager = self.manager_class()
        self.manager._execute_query = Mock()

    def test_pending_credential_cannot_overwrite_existing(self):
        self.manager._execute_query.return_value = None

        created = self.manager.create_pending_agent_credential(
            "agent-a",
            "a" * 64,
        )

        self.assertFalse(created)

        query = self.manager._execute_query.call_args.args[0]
        self.assertIn("ON CONFLICT (agent_id) DO NOTHING", query)
        self.assertIn("is_active", query)

    def test_pending_credential_starts_inactive(self):
        self.manager._execute_query.return_value = {
            "agent_id": "agent-a"
        }

        created = self.manager.create_pending_agent_credential(
            "agent-a",
            "a" * 64,
        )

        self.assertTrue(created)

        query = self.manager._execute_query.call_args.args[0]
        self.assertIn("FALSE", query)

    def test_revoked_credential_cannot_be_activated(self):
        self.manager._execute_query.return_value = None

        activated = self.manager.activate_agent_credential(
            "agent-a"
        )

        self.assertFalse(activated)

        query = self.manager._execute_query.call_args.args[0]

        self.assertIn("revoked_at IS NULL", query)
        self.assertIn("is_active = FALSE", query)

    def test_activation_success_requires_updated_record(self):
        self.manager._execute_query.return_value = {
            "agent_id": "agent-a"
        }

        activated = self.manager.activate_agent_credential(
            "agent-a"
        )

        self.assertTrue(activated)

    def test_revocation_marks_credential_inactive(self):
        self.manager._execute_query.return_value = {
            "agent_id": "agent-a"
        }

        revoked = self.manager.revoke_agent_credential(
            "agent-a"
        )

        self.assertTrue(revoked)

        query = self.manager._execute_query.call_args.args[0]

        self.assertIn("is_active = FALSE", query)
        self.assertIn("revoked_at = CURRENT_TIMESTAMP", query)

    def test_repeated_revocation_is_rejected(self):
        self.manager._execute_query.return_value = None

        revoked = self.manager.revoke_agent_credential(
            "agent-a"
        )

        self.assertFalse(revoked)

        query = self.manager._execute_query.call_args.args[0]
        self.assertIn("revoked_at IS NULL", query)


if __name__ == "__main__":
    unittest.main()
