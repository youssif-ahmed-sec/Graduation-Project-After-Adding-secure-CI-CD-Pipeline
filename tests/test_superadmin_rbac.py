
import ast
import datetime
import unittest
from functools import wraps
from pathlib import Path
from unittest.mock import MagicMock

import jwt
from flask import Flask, g, jsonify, request


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "server" / "app.py"


class TestSuperAdminRBAC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        names = {"admin_required", "superadmin_required"}
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in names
        ]

        if len(functions) != 2:
            raise AssertionError("Required decorators not found")

        module = ast.Module(body=functions, type_ignores=[])
        ast.fix_missing_locations(module)

        cls.flask_app = Flask(__name__)
        cls.secret = "test-only-rbac-jwt-secret-not-production"
        cls.db = MagicMock()

        namespace = {
            "wraps": wraps,
            "request": request,
            "jsonify": jsonify,
            "g": g,
            "jwt": jwt,
            "JWT_SECRET": cls.secret,
            "db": cls.db,
            "app": cls.flask_app,
        }

        exec(compile(module, "<rbac-test>", "exec"), namespace)
        cls.protect = staticmethod(namespace["superadmin_required"])

    def setUp(self):
        self.db.reset_mock()
        self.db.get_admin_role.side_effect = None
        self.db.get_admin_role.return_value = "SuperAdmin"

    def make_token(self, role="SuperAdmin", mfa=True):
        now = datetime.datetime.now(datetime.timezone.utc)

        return jwt.encode(
            {
                "user": "test-user",
                "role": role,
                "token_type": "access",
                "mfa_verified": mfa,
                "iat": now,
                "exp": now + datetime.timedelta(minutes=10),
            },
            self.secret,
            algorithm="HS256",
        )

    def call_protected(self, token=None):
        headers = {}
        if token is not None:
            headers["X-Admin-Token"] = token

        with self.flask_app.test_request_context(
            "/protected",
            headers=headers,
        ):
            @self.protect
            def protected():
                return jsonify({"status": "allowed"}), 200

            response, status = protected()
            return response.get_json(), status

    def test_superadmin_is_allowed(self):
        body, status = self.call_protected(self.make_token())

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "allowed")
        self.db.get_admin_role.assert_called_once_with("test-user")

    def test_analyst_is_denied_even_with_superadmin_jwt(self):
        self.db.get_admin_role.return_value = "Analyst"

        body, status = self.call_protected(
            self.make_token(role="SuperAdmin")
        )

        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "Forbidden")

    def test_missing_token_is_denied(self):
        _, status = self.call_protected()

        self.assertEqual(status, 401)
        self.db.get_admin_role.assert_not_called()

    def test_missing_mfa_is_denied(self):
        _, status = self.call_protected(
            self.make_token(mfa=False)
        )

        self.assertEqual(status, 401)
        self.db.get_admin_role.assert_not_called()

    def test_database_failure_is_denied(self):
        self.db.get_admin_role.side_effect = RuntimeError(
            "Simulated database failure"
        )

        body, status = self.call_protected(self.make_token())

        self.assertEqual(status, 503)
        self.assertEqual(
            body["error"],
            "Authorization unavailable",
        )

    def test_sensitive_user_management_requires_superadmin(self):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        sensitive_endpoints = (
            "add_new_admin",
            "change_admin_password",
            "delete_admin_user",
        )

        for endpoint_name in sensitive_endpoints:
            with self.subTest(endpoint=endpoint_name):
                endpoint = next(
                    node for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == endpoint_name
                )

                decorators = [
                    node.id
                    for node in endpoint.decorator_list
                    if isinstance(node, ast.Name)
                ]

                self.assertIn(
                    "superadmin_required",
                    decorators,
                    f"{endpoint_name} must require SuperAdmin",
                )

                self.assertNotIn(
                    "admin_required",
                    decorators,
                    f"{endpoint_name} must not use general admin access",
                )

    def test_emergency_containment_requires_superadmin(self):
        source = APP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        endpoint = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "emergency_containment"
        )

        decorators = [
            node.id
            for node in endpoint.decorator_list
            if isinstance(node, ast.Name)
        ]

        self.assertIn(
            "superadmin_required",
            decorators,
            "Emergency actions must require SuperAdmin authorization",
        )

        self.assertNotIn(
            "admin_required",
            decorators,
            "Emergency actions must not use general admin authorization",
        )


if __name__ == "__main__":
    unittest.main()
