
import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask, g, jsonify, request


APP_FILE = Path(__file__).resolve().parents[1] / "server" / "app.py"


class TestAISettingsSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        cls.functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_ai_settings_write_requires_superadmin(self):
        function = self.functions["save_ai_settings"]

        decorators = [
            node.id
            for node in function.decorator_list
            if isinstance(node, ast.Name)
        ]

        self.assertIn("superadmin_required", decorators)
        self.assertNotIn("admin_required", decorators)

    def test_ai_settings_read_does_not_return_api_key(self):
        function = self.functions["get_ai_settings"]

        source = ast.unparse(function)

        self.assertIn("api_key_configured", source)
        self.assertNotIn('"api_key":', source)
        self.assertNotIn("'api_key':", source)

    def test_model_update_preserves_existing_api_key(self):
        function = self.functions["save_ai_settings"]

        function.decorator_list = []
        module = ast.Module(body=[function], type_ignores=[])
        ast.fix_missing_locations(module)

        app = Flask(__name__)
        db = MagicMock()

        namespace = {
            "request": request,
            "jsonify": jsonify,
            "g": g,
            "db": db,
        }

        exec(compile(module, "<ai-settings-test>", "exec"), namespace)

        with app.test_request_context(
            "/api/v1/admin/ai_settings",
            method="POST",
            json={"model": "gemini-test-model"},
        ):
            g.admin_user = "test-superadmin"

            response, status = namespace["save_ai_settings"]()

        self.assertEqual(status, 200)
        self.assertEqual(response.get_json()["status"], "success")

        db.update_setting.assert_called_once_with(
            "ai_model",
            "gemini-test-model",
        )


if __name__ == "__main__":
    unittest.main()
