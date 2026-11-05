
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


if __name__ == "__main__":
    unittest.main()
