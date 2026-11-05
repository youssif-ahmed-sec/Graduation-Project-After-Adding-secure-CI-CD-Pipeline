import ast
import unittest
from pathlib import Path

from flask import Flask, jsonify, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "server" / "app.py"


class SecurityHeadersTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"add_security_headers", "healthz"}
        ]

        if len(functions) != 2:
            raise AssertionError("Missing required Flask functions")

        cls.app = Flask("security-headers-test")
        namespace = {
            "app": cls.app,
            "request": request,
            "jsonify": jsonify,
        }

        isolated_module = ast.Module(
            body=functions,
            type_ignores=[],
        )

        exec(
            compile(isolated_module, str(APP_PATH), "exec"),
            namespace,
        )

        @cls.app.get("/api/v1/test")
        def api_test():
            return jsonify({"status": "test"})

        @cls.app.get("/evidence/test")
        def evidence_test():
            return "test evidence"

    def test_permissions_policy_on_health_endpoint(self):
        with self.app.test_client() as client:
            response = client.get("/healthz")

        self.assertEqual(
            response.headers.get("Permissions-Policy"),
            "camera=(), microphone=(), geolocation=()",
        )

    def test_api_responses_cannot_be_cached(self):
        with self.app.test_client() as client:
            response = client.get("/api/v1/test")

        self.assertEqual(
            response.headers.get("Cache-Control"),
            "no-store, private",
        )

    def test_evidence_responses_cannot_be_cached(self):
        with self.app.test_client() as client:
            response = client.get("/evidence/test")

        self.assertEqual(
            response.headers.get("Cache-Control"),
            "no-store, private",
        )

    def test_content_type_sniffing_is_disabled(self):
        with self.app.test_client() as client:
            response = client.get("/healthz")

        self.assertEqual(
            response.headers.get("X-Content-Type-Options"),
            "nosniff",
        )

    def test_error_responses_receive_security_headers(self):
        with self.app.test_client() as client:
            response = client.get("/api/v1/not-found")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.headers.get("Cache-Control"),
            "no-store, private",
        )
        self.assertEqual(
            response.headers.get("X-Content-Type-Options"),
            "nosniff",
        )

    def test_csp_header_is_present_and_restrictive(self):
        with self.app.test_client() as client:
            response = client.get("/healthz")

        csp = response.headers.get("Content-Security-Policy")

        self.assertIsNotNone(csp)
        self.assertIn("default-src 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("'unsafe-inline'", csp)
        self.assertNotIn("'unsafe-eval'", csp)

    def test_csp_is_present_on_api_error_responses(self):
        with self.app.test_client() as client:
            response = client.get("/api/v1/not-found")

        self.assertEqual(response.status_code, 404)
        self.assertIn(
            "default-src 'none'",
            response.headers.get("Content-Security-Policy", ""),
        )


if __name__ == "__main__":
    unittest.main()
