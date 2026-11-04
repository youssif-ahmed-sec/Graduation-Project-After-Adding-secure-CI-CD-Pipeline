import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_MANAGER_PATH = PROJECT_ROOT / "server" / "db_manager.py"


def load_attach_method():
    """Load only the method without connecting to PostgreSQL."""
    source = DB_MANAGER_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)

    db_class = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef)
        and node.name == "DBManager"
    )

    method = next(
        node for node in db_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "attach_artifact_to_log"
    )

    isolated_module = ast.Module(
        body=[method],
        type_ignores=[],
    )

    namespace = {}
    exec(
        compile(
            ast.fix_missing_locations(isolated_module),
            str(DB_MANAGER_PATH),
            "exec",
        ),
        namespace,
    )

    return namespace["attach_artifact_to_log"]


class TestAtomicEvidenceAssociation(unittest.TestCase):

    def setUp(self):
        self.method = load_attach_method()

        self.connection = MagicMock()
        self.cursor = MagicMock()

        self.connection.cursor.return_value = self.cursor

        self.db = SimpleNamespace(
            _get_connection=MagicMock(
                return_value=self.connection
            )
        )

    def attach(self, log_id=42, agent_id="agent-1",
               filename="ss_test.png", artifact_type="screenshot"):
        return self.method(
            self.db,
            log_id,
            agent_id,
            filename,
            artifact_type,
        )

    def test_attaches_to_specific_incident(self):
        self.cursor.fetchone.return_value = {
            "screenshot_path": "old.png"
        }

        result = self.attach()

        self.assertTrue(result)
        self.assertEqual(self.cursor.execute.call_count, 2)

        select_args = self.cursor.execute.call_args_list[0]
        self.assertIn("FOR UPDATE", select_args.args[0])
        self.assertEqual(
            select_args.args[1],
            (42, "agent-1"),
        )

        update_args = self.cursor.execute.call_args_list[1]
        self.assertEqual(
            update_args.args[1],
            ("old.png,ss_test.png", 42, "agent-1"),
        )

        self.connection.commit.assert_called_once()

    def test_rejects_missing_or_wrong_incident(self):
        self.cursor.fetchone.return_value = None

        result = self.attach()

        self.assertFalse(result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_does_not_duplicate_evidence(self):
        self.cursor.fetchone.return_value = {
            "screenshot_path": "ss_test.png"
        }

        result = self.attach()

        self.assertTrue(result)
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.commit.assert_called_once()

    def test_rolls_back_on_database_error(self):
        self.cursor.execute.side_effect = RuntimeError(
            "Simulated database failure"
        )

        with self.assertRaises(RuntimeError):
            self.attach()

        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_rejects_invalid_log_id(self):
        for invalid_id in (-1, 0, "42", None, True):
            with self.subTest(log_id=invalid_id):
                with self.assertRaises(ValueError):
                    self.attach(log_id=invalid_id)

        self.db._get_connection.assert_not_called()

    def test_rejects_invalid_artifact_type(self):
        with self.assertRaises(ValueError):
            self.attach(artifact_type="invalid_column")

        self.db._get_connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()