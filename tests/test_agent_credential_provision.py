
import ast
import copy
import time
import unittest
from functools import wraps
from pathlib import Path
from unittest.mock import Mock

import jwt
from flask import Flask, g, jsonify, request


APP_FILE = Path(__file__).resolve().parents[1] / "server" / "app.py"
ENDPOINT = "/api/v1/admin/agents/credentials/provision"


class AgentCredentialProvisionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

        self.db = Mock()
        self.db.get_admin_role.return_value = "SuperAdmin"
        self.db.agent_exists.return_value = True
        self.db.create_pending_agent.return_value = True
        self.db.create_pending_agent_credential.return_value = True
        self.db.activate_agent_credential.return_value = True
        self.db.revoke_agent_credential.return_value = True

        self.generate_credential = Mock(
            return_value="test-agent-credential-only"
        )
        self.load_pepper = Mock(return_value="test-pepper")
        self.hash_credential = Mock(
            return_value="a" * 64
        )

        self.jwt_secret = "unit-test-jwt-secret-not-for-production"

        namespace = {
            "app": self.app,
            "db": self.db,
            "jwt": jwt,
            "JWT_SECRET": self.jwt_secret,
            "request": request,
            "jsonify": jsonify,
            "g": g,
            "connected_agents": {},
            "socketio": Mock(),
            "wraps": wraps,
            "generate_agent_credential": self.generate_credential,
            "hash_agent_credential": self.hash_credential,
            "load_agent_credential_pepper": self.load_pepper,
        }

        tree = ast.parse(APP_FILE.read_text(encoding="utf-8"))

        function_names = (
            "admin_required",
            "superadmin_required",
            "provision_agent_credential",
            "approve_agent_endpoint",
            "activate_agent_credential_endpoint",
            "revoke_agent_credential_endpoint",
        )

        functions = []

        for name in function_names:
            matching = [
                node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == name
            ]

            self.assertEqual(len(matching), 1, name)

            node = copy.deepcopy(matching[0])

            if name in (
                "approve_agent_endpoint",
                "provision_agent_credential",
                "activate_agent_credential_endpoint",
                "revoke_agent_credential_endpoint",
            ):
                node.decorator_list = [
                    ast.Name(
                        id="superadmin_required",
                        ctx=ast.Load(),
                    )
                ]
            else:
                node.decorator_list = []

            functions.append(node)

        isolated_module = ast.Module(
            body=functions,
            type_ignores=[],
        )

        ast.fix_missing_locations(isolated_module)

        exec(
            compile(isolated_module, str(APP_FILE), "exec"),
            namespace,
        )
        self.namespace = namespace
        self.app.add_url_rule(
            "/api/v1/admin/agents/approve",
            view_func=namespace["approve_agent_endpoint"],
            methods=["POST"],
        )
        self.app.add_url_rule(
            ENDPOINT,
            view_func=namespace["provision_agent_credential"],
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/v1/admin/agents/credentials/activate",
            view_func=namespace["activate_agent_credential_endpoint"],
            methods=["POST"],
        )

        self.app.add_url_rule(
            "/api/v1/admin/agents/credentials/revoke",
            view_func=namespace["revoke_agent_credential_endpoint"],
            methods=["POST"],
        )

        self.client = self.app.test_client()

    def headers(self, role="SuperAdmin", mfa=True):
        self.db.get_admin_role.return_value = role
        now = int(time.time())

        token = jwt.encode(
            {
                "user": "test-admin",
                "token_type": "access",
                "mfa_verified": mfa,
                "iat": now - 1,
                "exp": now + 300,
            },
            self.jwt_secret,
            algorithm="HS256",
        )

        return {"X-Admin-Token": token}

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "agent-a"},
        )

        self.assertEqual(response.status_code, 401)
        self.db.create_pending_agent_credential.assert_not_called()

    def test_regular_admin_cannot_provision(self):
        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "agent-a"},
            headers=self.headers(role="Admin"),
        )

        self.assertEqual(response.status_code, 403)
        self.generate_credential.assert_not_called()

    def test_mfa_is_required(self):
        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "agent-a"},
            headers=self.headers(mfa=False),
        )

        self.assertEqual(response.status_code, 401)
        self.generate_credential.assert_not_called()

    def test_superadmin_creates_pending_credential(self):
        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json["credential_status"],
            "pending",
        )
        self.assertEqual(
            response.json["credential"],
            "test-agent-credential-only",
        )
        self.assertEqual(
            response.headers["Cache-Control"],
            "no-store, private",
        )

        self.db.create_pending_agent_credential.assert_called_once_with(
            "agent-a",
            "a" * 64,
        )

    def test_existing_credential_cannot_be_overwritten(self):
        self.db.create_pending_agent_credential.return_value = False

        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 409)
        self.assertNotIn("credential", response.json)

    def test_unknown_agent_is_rejected(self):
        self.db.agent_exists.return_value = False

        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "unknown-agent"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 404)
        self.generate_credential.assert_not_called()

    def test_invalid_agent_id_is_rejected(self):
        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "  agent-a  "},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.generate_credential.assert_not_called()

    def test_database_failure_does_not_expose_credential(self):
        self.db.create_pending_agent_credential.side_effect = (
            RuntimeError("sensitive database details")
        )

        response = self.client.post(
            ENDPOINT,
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("credential", response.json)
        self.assertNotIn(
            "sensitive database details",
            response.get_data(as_text=True),
        )

    def test_database_failure_does_not_log_sensitive_details(self):
        self.db.create_pending_agent_credential.side_effect = (
            RuntimeError("sensitive database details")
        )

        with self.assertLogs(self.app.logger, level="ERROR") as captured:
            response = self.client.post(
                ENDPOINT,
                json={"agent_id": "agent-a"},
                headers=self.headers(),
            )

        self.assertEqual(response.status_code, 503)

        logged_text = "\n".join(captured.output)

        self.assertIn(
            "Agent credential provisioning failed",
            logged_text,
        )

        self.assertNotIn(
            "sensitive database details",
            logged_text,
        )

    def test_superadmin_can_activate_pending_credential(self):
        response = self.client.post(
            "/api/v1/admin/agents/credentials/activate",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["credential_status"], "active"
        )
        self.db.activate_agent_credential.assert_called_once_with(
            "agent-a"
        )

    def test_regular_admin_cannot_activate_credential(self):
        response = self.client.post(
            "/api/v1/admin/agents/credentials/activate",
            json={"agent_id": "agent-a"},
            headers=self.headers(role="Admin"),
        )

        self.assertEqual(response.status_code, 403)
        self.db.activate_agent_credential.assert_not_called()

    def test_revoked_credential_cannot_be_activated(self):
        self.db.activate_agent_credential.return_value = False

        response = self.client.post(
            "/api/v1/admin/agents/credentials/activate",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 409)

    def test_superadmin_can_revoke_credential(self):
        response = self.client.post(
            "/api/v1/admin/agents/credentials/revoke",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["credential_status"], "revoked"
        )
        self.db.revoke_agent_credential.assert_called_once_with(
            "agent-a"
        )

    def test_regular_admin_cannot_revoke_credential(self):
        response = self.client.post(
            "/api/v1/admin/agents/credentials/revoke",
            json={"agent_id": "agent-a"},
            headers=self.headers(role="Admin"),
        )

        self.assertEqual(response.status_code, 403)
        self.db.revoke_agent_credential.assert_not_called()

    def test_repeated_revocation_is_rejected(self):
        self.db.revoke_agent_credential.return_value = False

        response = self.client.post(
            "/api/v1/admin/agents/credentials/revoke",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 409)

    def test_activation_database_failure_fails_closed(self):
        self.db.activate_agent_credential.side_effect = (
            RuntimeError("sensitive database details")
        )

        response = self.client.post(
            "/api/v1/admin/agents/credentials/activate",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "sensitive database details",
            response.get_data(as_text=True),
        )

    def test_revocation_database_failure_fails_closed(self):
        self.db.revoke_agent_credential.side_effect = (
            RuntimeError("sensitive database details")
        )

        response = self.client.post(
            "/api/v1/admin/agents/credentials/revoke",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "sensitive database details",
            response.get_data(as_text=True),
        )

    def test_superadmin_can_approve_agent(self):
        self.db.create_pending_agent.return_value = True

        response = self.client.post(
            "/api/v1/admin/agents/approve",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 201)
        self.db.create_pending_agent.assert_called_once_with(
            "agent-a"
        )

    def test_regular_admin_cannot_approve_agent(self):
        response = self.client.post(
            "/api/v1/admin/agents/approve",
            json={"agent_id": "agent-a"},
            headers=self.headers(role="Admin"),
        )

        self.assertEqual(response.status_code, 403)
        self.db.create_pending_agent.assert_not_called()

    def test_approval_requires_authentication(self):
        response = self.client.post(
            "/api/v1/admin/agents/approve",
            json={"agent_id": "agent-a"},
        )

        self.assertEqual(response.status_code, 401)
        self.db.create_pending_agent.assert_not_called()

    def test_approval_rejects_unverified_mfa(self):
        token = jwt.encode(
            {
                "user": "test-superadmin",
                "token_type": "access",
                "mfa_verified": False,
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            },
            self.jwt_secret,
            algorithm="HS256",
        )

        response = self.client.post(
            "/api/v1/admin/agents/approve",
            json={"agent_id": "agent-a"},
            headers={"X-Admin-Token": token},
        )

        self.assertEqual(response.status_code, 401)
        self.db.create_pending_agent.assert_not_called()

    def test_revocation_disconnects_active_agent_sessions(self):
        self.db.revoke_agent_credential.return_value = True

        self.namespace["connected_agents"].update({
            "sid-1": "agent-a",
            "sid-2": "agent-b",
            "sid-3": "agent-a",
        })

        response = self.client.post(
            "/api/v1/admin/agents/credentials/revoke",
            json={"agent_id": "agent-a"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)

        disconnect_mock = self.namespace["socketio"].server.disconnect

        disconnected = {
            call.args[0]
            for call in disconnect_mock.call_args_list
        }

        self.assertEqual(disconnected, {"sid-1", "sid-3"})
        self.assertEqual(disconnect_mock.call_count, 2)

        for call in disconnect_mock.call_args_list:
            self.assertEqual(call.kwargs.get("namespace"), "/")

if __name__ == "__main__":
    unittest.main()
