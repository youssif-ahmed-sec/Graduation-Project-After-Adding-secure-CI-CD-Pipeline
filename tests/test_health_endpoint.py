
import ast
import unittest
from pathlib import Path

from flask import Flask, jsonify


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "server" / "app.py"


class HealthEndpointTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)

        health_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "healthz"
        )

        isolated_module = ast.Module(
            body=[health_function],
            type_ignores=[],
        )

        cls.app = Flask("health-test")

        namespace = {
            "app": cls.app,
            "jsonify": jsonify,
        }

        exec(
            compile(isolated_module, str(APP_PATH), "exec"),
            namespace,
        )

    def test_health_endpoint_returns_http_200(self):
        with self.app.test_client() as client:
            response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_returns_expected_json(self):
        with self.app.test_client() as client:
            response = client.get("/healthz")

        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_health_endpoint_does_not_expose_sensitive_details(self):
        with self.app.test_client() as client:
            response = client.get("/healthz")

        body = response.get_json()

        self.assertNotIn("db_password", body)
        self.assertNotIn("jwt_secret", body)
        self.assertNotIn("agent_secret", body)


if __name__ == "__main__":
    unittest.main()
