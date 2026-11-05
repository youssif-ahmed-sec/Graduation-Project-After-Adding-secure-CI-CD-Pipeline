import ast
import copy
import unittest
import hmac
from pathlib import Path
from unittest.mock import Mock
from flask_socketio import disconnect, emit
from flask import Flask, request
from flask_socketio import SocketIO, join_room


APP_FILE = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "app.py"
)


class AgentSocketIOAuthenticationTests(unittest.TestCase):

    def setUp(self):
        tree = ast.parse(
            APP_FILE.read_text(encoding="utf-8")
        )

        handler_node = copy.deepcopy(
            next(
                node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "handle_connect"
            )
        )
        authorization_node = copy.deepcopy(
            next(
                node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "get_authorized_socket_agent"
            )
        )
        event_nodes = [
            copy.deepcopy(node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in (
                "handle_task_response",
                "handle_cmd_result",
            )
        ]

        for node in event_nodes:
            node.decorator_list = []

        # Use the actual connect handler without importing
        # the production application or initializing its DB.
        handler_node.decorator_list = []

        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-only-key"

        self.socketio = SocketIO(
            self.app,
            async_mode="threading",
            cors_allowed_origins=[],
        )

        self.fake_db = Mock()
        self.connected_agents = {}
        self.admin_sids = set()
        self.session_hashes = {}
        self.credentials = {
            "agent-a": "credential-a",
            "agent-b": "credential-b",
        }

        self.active_agents = {
            "agent-a",
            "agent-b",
        }

        self.fake_auth = Mock(
            side_effect=self.authenticate_agent
        )

        namespace = {
            "request": request,
            "join_room": join_room,
            "socketio": self.socketio,
            "db": self.fake_db,
            "app": self.app,
            "hmac": hmac,
            "disconnect": disconnect,
            "emit": emit,
            "connected_agents": self.connected_agents,
            "authenticated_admin_sids": self.admin_sids,
            "authenticate_registered_agent": self.fake_auth,
            "load_agent_credential_pepper": Mock(
                return_value="test-pepper"
            ),
            "agent_session_credential_hashes": self.session_hashes,
            "hash_agent_credential": Mock(
                side_effect=lambda credential, pepper: (
                    f"test-hash:{credential}"
                )
            ),
        }

        module = ast.Module(
            body=[handler_node, authorization_node, *event_nodes],
            type_ignores=[],
        )

        ast.fix_missing_locations(module)

        exec(
            compile(
                module,
                str(APP_FILE),
                "exec",
            ),
            namespace,
        )
        self.namespace = namespace

        self.socketio.on_event(
            "connect",
            namespace["handle_connect"],
            namespace="/",
        )
        self.socketio.on_event(
            "task_response",
            namespace["handle_task_response"],
            namespace="/",
        )

        self.socketio.on_event(
            "cmd_result",
            namespace["handle_cmd_result"],
            namespace="/",
        )

    def authenticate_agent(
        self,
        agent_id,
        credential,
        db,
        pepper,
    ):
        return (
            agent_id in self.active_agents
            and self.credentials.get(agent_id) == credential
        )

    def connect_agent(self, auth):
        return self.socketio.test_client(
            self.app,
            auth=auth,
            namespace="/",
        )

    def test_valid_active_credential_connects(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })

        try:
            self.assertTrue(client.is_connected())
            self.fake_auth.assert_called_once_with(
                "agent-a",
                "credential-a",
                self.fake_db,
                "test-pepper",
            )

            self.assertEqual(len(self.session_hashes), 1)
            self.assertEqual(
                next(iter(self.session_hashes.values())),
                "test-hash:credential-a",
            )
            self.fake_db.update_heartbeat.assert_called_once_with(
                "agent-a"
            )
            self.assertIn(
                "agent-a",
                self.connected_agents.values(),
            )
        finally:
            if client.is_connected():
                client.disconnect()

    def test_legacy_shared_token_is_rejected(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "token": "legacy-shared-token",
        })

        self.assertFalse(client.is_connected())
        self.fake_db.update_heartbeat.assert_not_called()
        self.assertEqual(self.connected_agents, {})

    def test_agent_cannot_impersonate_another_agent(self):
        client = self.connect_agent({
            "agent_id": "agent-b",
            "credential": "credential-a",
        })

        self.assertFalse(client.is_connected())
        self.fake_db.update_heartbeat.assert_not_called()
        self.assertEqual(self.connected_agents, {})

    def test_revoked_credential_is_rejected(self):
        self.active_agents.remove("agent-a")

        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })

        self.assertFalse(client.is_connected())
        self.fake_db.update_heartbeat.assert_not_called()

    def test_missing_credentials_are_rejected(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
        })

        self.assertFalse(client.is_connected())
        self.fake_auth.assert_not_called()

    def test_database_failure_rejects_connection(self):
        self.fake_auth.side_effect = RuntimeError(
            "Simulated database outage"
        )

        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })

        self.assertFalse(client.is_connected())
        self.assertEqual(self.connected_agents, {})
        self.fake_db.update_heartbeat.assert_not_called()

    def test_active_session_is_authorized(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })

        try:
            self.assertTrue(client.is_connected())

            self.fake_db.get_agent_credential.return_value = {
                "credential_hash": "test-hash:credential-a",
                "is_active": True,
                "revoked_at": None,
            }

            sid = next(iter(self.connected_agents))

            agent_id = self.namespace[
                "get_authorized_socket_agent"
            ](sid)

            self.assertEqual(agent_id, "agent-a")
        finally:
            if client.is_connected():
                client.disconnect()

    def test_revoked_session_is_rejected(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })

        try:
            self.assertTrue(client.is_connected())

            self.fake_db.get_agent_credential.return_value = {
                "credential_hash": "test-hash:credential-a",
                "is_active": False,
                "revoked_at": "2026-11-05",
            }

            sid = next(iter(self.connected_agents))

            self.assertIsNone(
                self.namespace[
                    "get_authorized_socket_agent"
                ](sid)
            )
        finally:
            if client.is_connected():
                client.disconnect()

    def test_rotated_credential_invalidates_old_session(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })

        try:
            self.assertTrue(client.is_connected())

            self.fake_db.get_agent_credential.return_value = {
                "credential_hash": "different-credential-hash",
                "is_active": True,
                "revoked_at": None,
            }

            sid = next(iter(self.connected_agents))

            self.assertIsNone(
                self.namespace[
                    "get_authorized_socket_agent"
                ](sid)
            )
        finally:
            if client.is_connected():
                client.disconnect()

    def test_database_outage_invalidates_session_authorization(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })

        try:
            self.assertTrue(client.is_connected())

            self.fake_db.get_agent_credential.side_effect = (
                RuntimeError("Simulated database outage")
            )

            sid = next(iter(self.connected_agents))

            self.assertIsNone(
                self.namespace[
                    "get_authorized_socket_agent"
                ](sid)
            )
        finally:
            if client.is_connected():
                client.disconnect()

    def test_revoked_agent_cannot_send_task_response(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })
        self.assertTrue(client.is_connected())

        try:
            self.fake_db.get_agent_credential.return_value = {
                "credential_hash": "test-hash:credential-a",
                "is_active": False,
                "revoked_at": "2026-11-05",
            }

            self.socketio.emit = Mock()

            client.emit(
                "task_response",
                {
                    "agent_id": "agent-b",
                    "output": "unauthorized-result",
                },
            )

            self.assertFalse(client.is_connected())
            self.socketio.emit.assert_not_called()

        finally:
            if client.is_connected():
                client.disconnect()

    def test_revoked_agent_cannot_send_cmd_result(self):
        client = self.connect_agent({
            "agent_id": "agent-a",
            "credential": "credential-a",
        })
        self.assertTrue(client.is_connected())

        try:
            self.fake_db.get_agent_credential.return_value = {
                "credential_hash": "test-hash:credential-a",
                "is_active": False,
                "revoked_at": "2026-11-05",
            }

            self.socketio.emit = Mock()

            client.emit(
                "cmd_result",
                {
                    "agent_id": "agent-b",
                    "output": "unauthorized-result",
                },
            )

            self.assertFalse(client.is_connected())
            self.socketio.emit.assert_not_called()

        finally:
            if client.is_connected():
                client.disconnect()


if __name__ == "__main__":
    unittest.main()