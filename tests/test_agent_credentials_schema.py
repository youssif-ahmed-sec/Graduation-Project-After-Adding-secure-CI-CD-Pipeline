
import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_MANAGER = ROOT / "server" / "db_manager.py"


class TestAgentCredentialsSchema(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = DB_MANAGER.read_text(encoding="utf-8")
        tree = ast.parse(source)

        manager = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DBManager"
        )

        create_tables = next(
            node for node in manager.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_tables"
        )

        # Extract SQL string literals without importing DBManager
        # or opening a database connection.
        sql_strings = [
            node.value
            for node in ast.walk(create_tables)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ]

        cls.schema = "\n".join(sql_strings)

    def test_agent_credentials_table_has_agent_identity_binding(self):
        match = re.search(
            r"CREATE TABLE IF NOT EXISTS agent_credentials\s*\((.*?)\)",
            self.schema,
            flags=re.IGNORECASE | re.DOTALL,
        )

        self.assertIsNotNone(
            match,
            "agent_credentials table definition is missing",
        )

        self.assertRegex(
            self.schema,
            r"agent_id\s+TEXT\s+PRIMARY KEY\s+"
            r"REFERENCES\s+agents\s*\(\s*agent_id\s*\)",
        )

    def test_credentials_default_to_inactive_and_support_revocation(self):
        self.assertRegex(
            self.schema,
            r"is_active\s+BOOLEAN\s+NOT NULL\s+DEFAULT\s+FALSE",
        )

        self.assertRegex(
            self.schema,
            r"credential_hash\s+TEXT\s+NOT NULL",
        )

        self.assertRegex(
            self.schema,
            r"revoked_at\s+TIMESTAMPTZ",
        )

class TestAgentCredentialLookup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from unittest.mock import MagicMock

        source = DB_MANAGER.read_text(encoding="utf-8")
        tree = ast.parse(source)

        manager = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DBManager"
        )

        method = next(
            node for node in manager.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "get_agent_credential"
        )

        # Test only the method without importing DBManager
        # or opening a PostgreSQL connection.
        module = ast.Module(body=[method], type_ignores=[])
        ast.fix_missing_locations(module)

        namespace = {}
        exec(compile(module, "<credential-lookup-test>", "exec"), namespace)

        cls.lookup = staticmethod(namespace["get_agent_credential"])
        cls.MagicMock = MagicMock

    def test_returns_existing_credential(self):
        db = self.MagicMock()
        expected = {
            "agent_id": "agent-a",
            "credential_hash": "test-hash",
            "is_active": True,
            "revoked_at": None,
        }
        db._execute_query.return_value = expected

        result = self.lookup(db, "agent-a")

        self.assertEqual(result, expected)
        db._execute_query.assert_called_once()

        args, kwargs = db._execute_query.call_args

        self.assertIn("FROM agent_credentials", args[0])
        self.assertEqual(args[1], ("agent-a",))
        self.assertEqual(kwargs["fetch"], "one")

    def test_rejects_invalid_agent_ids(self):
        for agent_id in (None, "", "   ", 123, [], {}):
            with self.subTest(agent_id=agent_id):
                db = self.MagicMock()

                self.assertIsNone(self.lookup(db, agent_id))
                db._execute_query.assert_not_called()

    def test_returns_none_for_missing_credential(self):
        db = self.MagicMock()
        db._execute_query.return_value = None

        result = self.lookup(db, "unknown-agent")

        self.assertIsNone(result)
        db._execute_query.assert_called_once()


class TestPendingAgentCredential(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from unittest.mock import MagicMock

        source = DB_MANAGER.read_text(encoding="utf-8")
        tree = ast.parse(source)

        manager = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DBManager"
        )

        method = next(
            node for node in manager.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_pending_agent_credential"
        )

        module = ast.Module(body=[method], type_ignores=[])
        ast.fix_missing_locations(module)

        namespace = {}
        exec(
            compile(module, "<pending-credential-test>", "exec"),
            namespace,
        )

        cls.create_pending = staticmethod(
            namespace["create_pending_agent_credential"]
        )
        cls.MagicMock = MagicMock

    def test_creates_inactive_credential(self):
        db = self.MagicMock()
        db._execute_query.return_value = {"agent_id": "agent-a"}

        result = self.create_pending(db, "agent-a", "a" * 64)

        self.assertTrue(result)

        args, kwargs = db._execute_query.call_args

        self.assertIn("INSERT INTO agent_credentials", args[0])
        self.assertIn("FALSE", args[0])
        self.assertEqual(args[1], ("agent-a", "a" * 64))
        self.assertEqual(kwargs["fetch"], "one")

    def test_does_not_replace_existing_credential(self):
        db = self.MagicMock()
        db._execute_query.return_value = None

        result = self.create_pending(db, "agent-a", "b" * 64)

        self.assertFalse(result)

        query = db._execute_query.call_args.args[0]

        self.assertIn("ON CONFLICT (agent_id) DO NOTHING", query)
        self.assertNotIn("DO UPDATE", query.upper())

    def test_rejects_invalid_agent_ids(self):
        for agent_id in (None, "", "   ", 123):
            with self.subTest(agent_id=agent_id):
                db = self.MagicMock()

                with self.assertRaises(ValueError):
                    self.create_pending(db, agent_id, "c" * 64)

                db._execute_query.assert_not_called()

    def test_rejects_invalid_credential_hash(self):
        for value in (None, "", "short", "z" * 64, 123):
            with self.subTest(value=value):
                db = self.MagicMock()

                with self.assertRaises(ValueError):
                    self.create_pending(db, "agent-a", value)

                db._execute_query.assert_not_called()

if __name__ == "__main__":
    unittest.main()
