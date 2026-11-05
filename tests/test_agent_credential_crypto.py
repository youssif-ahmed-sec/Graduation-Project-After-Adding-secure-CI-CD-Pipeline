
import ast
import hashlib
import hmac
import re
import secrets
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECURITY_FILE = ROOT / "server" / "security.py"


class TestAgentCredentialCrypto(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        source = SECURITY_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        functions = {}
        for node in tree.body:
            if (
                isinstance(node, ast.FunctionDef)
                and node.name in (
                    "generate_agent_credential",
                    "hash_agent_credential",
                )
            ):
                functions[node.name] = node

        required = {
            "generate_agent_credential",
            "hash_agent_credential",
        }
        if not required.issubset(functions):
            raise AssertionError("Credential functions are missing")

        module = ast.Module(
            body=[functions[name] for name in sorted(required)],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)

        namespace = {
            "secrets": secrets,
            "hmac": hmac,
            "hashlib": hashlib,
        }

        exec(
            compile(module, "<credential-crypto-test>", "exec"),
            namespace,
        )

        cls.generate = staticmethod(
            namespace["generate_agent_credential"]
        )
        cls.hash_credential = staticmethod(
            namespace["hash_agent_credential"]
        )

    def test_generates_unique_credentials(self):
        credentials = [self.generate() for _ in range(100)]

        self.assertEqual(len(credentials), len(set(credentials)))

        for credential in credentials:
            self.assertIsInstance(credential, str)
            self.assertGreaterEqual(len(credential), 40)
            self.assertRegex(credential, r"^[A-Za-z0-9_-]+$")

    def test_hash_is_deterministic(self):
        pepper = "p" * 32
        credential = "test-agent-credential"

        first = self.hash_credential(credential, pepper)
        second = self.hash_credential(credential, pepper)

        self.assertEqual(first, second)
        self.assertRegex(first, r"^[a-f0-9]{64}$")

    def test_hash_changes_with_credential_or_pepper(self):
        pepper_a = "a" * 32
        pepper_b = "b" * 32

        first = self.hash_credential("credential-a", pepper_a)
        second = self.hash_credential("credential-b", pepper_a)
        third = self.hash_credential("credential-a", pepper_b)

        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)

    def test_rejects_invalid_inputs(self):
        invalid_credentials = (None, "", 123, [], {})

        for credential in invalid_credentials:
            with self.subTest(credential=credential):
                with self.assertRaises(ValueError):
                    self.hash_credential(credential, "p" * 32)

        invalid_peppers = (None, "", "short", 123, [], {})

        for pepper in invalid_peppers:
            with self.subTest(pepper=pepper):
                with self.assertRaises(ValueError):
                    self.hash_credential("valid-credential", pepper)

class TestAgentCredentialVerification(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import ast
        import hmac
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1]
            / "server"
            / "security.py"
        ).read_text(encoding="utf-8")

        tree = ast.parse(source)

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "hash_agent_credential",
                "verify_agent_credential",
            }
        ]

        module = ast.Module(
            body=functions,
            type_ignores=[],
        )
        ast.fix_missing_locations(module)

        namespace = {
            "hmac": hmac,
            "hashlib": __import__("hashlib"),
        }

        exec(
            compile(module, "<credential-verification-test>", "exec"),
            namespace,
        )

        cls.hash_credential = staticmethod(
            namespace["hash_agent_credential"]
        )
        cls.verify = staticmethod(
            namespace["verify_agent_credential"]
        )

        cls.pepper = "test-only-pepper-32-characters-minimum"

    def test_valid_credential_is_accepted(self):
        credential = "agent-secret-test-value"

        stored_hash = self.hash_credential(
            credential,
            self.pepper,
        )

        self.assertTrue(
            self.verify(credential, stored_hash, self.pepper)
        )

    def test_wrong_credential_is_rejected(self):
        stored_hash = self.hash_credential(
            "correct-agent-secret",
            self.pepper,
        )

        self.assertFalse(
            self.verify(
                "wrong-agent-secret",
                stored_hash,
                self.pepper,
            )
        )

    def test_invalid_hash_is_rejected(self):
        invalid_hashes = (
            None,
            "",
            "invalid",
            "g" * 64,
            "A" * 64,
            123,
        )

        for stored_hash in invalid_hashes:
            with self.subTest(stored_hash=stored_hash):
                self.assertFalse(
                    self.verify(
                        "agent-secret",
                        stored_hash,
                        self.pepper,
                    )
                )

    def test_invalid_credentials_are_rejected(self):
        stored_hash = self.hash_credential(
            "valid-agent-secret",
            self.pepper,
        )

        for credential in (None, "", 123, [], {}):
            with self.subTest(credential=credential):
                self.assertFalse(
                    self.verify(
                        credential,
                        stored_hash,
                        self.pepper,
                    )
                )

    def test_wrong_pepper_is_rejected(self):
        credential = "agent-secret-test-value"

        stored_hash = self.hash_credential(
            credential,
            self.pepper,
        )

        self.assertFalse(
            self.verify(
                credential,
                stored_hash,
                "different-test-pepper-32-chars-minimum",
            )
        )

class TestAgentCredentialAuthentication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import ast
        import hmac
        import hashlib
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1]
            / "server"
            / "security.py"
        ).read_text(encoding="utf-8")

        tree = ast.parse(source)

        names = {
            "hash_agent_credential",
            "verify_agent_credential",
            "authenticate_agent_credential",
        }

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in names
        ]

        module = ast.Module(body=functions, type_ignores=[])
        ast.fix_missing_locations(module)

        namespace = {
            "hmac": hmac,
            "hashlib": hashlib,
        }

        exec(
            compile(module, "<agent-auth-test>", "exec"),
            namespace,
        )

        cls.hash_credential = staticmethod(
            namespace["hash_agent_credential"]
        )
        cls.authenticate = staticmethod(
            namespace["authenticate_agent_credential"]
        )

        cls.pepper = "test-only-pepper-32-characters-minimum"
        cls.credential = "example-agent-secret"

    def make_record(self, agent_id="agent-001",
                    is_active=True, revoked_at=None):
        return {
            "agent_id": agent_id,
            "credential_hash": self.hash_credential(
                self.credential,
                self.pepper,
            ),
            "is_active": is_active,
            "revoked_at": revoked_at,
        }

    def test_valid_active_agent_is_authenticated(self):
        self.assertTrue(
            self.authenticate(
                "agent-001",
                self.credential,
                self.make_record(),
                self.pepper,
            )
        )

    def test_agent_identity_mismatch_is_rejected(self):
        self.assertFalse(
            self.authenticate(
                "agent-002",
                self.credential,
                self.make_record(agent_id="agent-001"),
                self.pepper,
            )
        )

    def test_inactive_agent_is_rejected(self):
        self.assertFalse(
            self.authenticate(
                "agent-001",
                self.credential,
                self.make_record(is_active=False),
                self.pepper,
            )
        )

    def test_revoked_agent_is_rejected(self):
        self.assertFalse(
            self.authenticate(
                "agent-001",
                self.credential,
                self.make_record(revoked_at="2026-01-01"),
                self.pepper,
            )
        )

    def test_wrong_secret_is_rejected(self):
        self.assertFalse(
            self.authenticate(
                "agent-001",
                "wrong-secret",
                self.make_record(),
                self.pepper,
            )
        )

    def test_invalid_records_are_rejected(self):
        for record in (None, {}, [], "invalid"):
            with self.subTest(record=record):
                self.assertFalse(
                    self.authenticate(
                        "agent-001",
                        self.credential,
                        record,
                        self.pepper,
                    )
                )

class TestRegisteredAgentAuthentication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import ast
        import hashlib
        import hmac
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1]
            / "server"
            / "security.py"
        ).read_text(encoding="utf-8")

        tree = ast.parse(source)

        names = {
            "hash_agent_credential",
            "verify_agent_credential",
            "authenticate_agent_credential",
            "authenticate_registered_agent",
        }

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in names
        ]

        module = ast.Module(body=functions, type_ignores=[])
        ast.fix_missing_locations(module)

        namespace = {
            "hmac": hmac,
            "hashlib": hashlib,
        }

        exec(
            compile(module, "<registered-agent-test>", "exec"),
            namespace,
        )

        cls.hash_credential = staticmethod(
            namespace["hash_agent_credential"]
        )
        cls.authenticate = staticmethod(
            namespace["authenticate_registered_agent"]
        )

        cls.pepper = "test-only-pepper-32-characters-minimum"
        cls.credential = "test-agent-credential"

    def make_record(self, agent_id="agent-001",
                    active=True, revoked_at=None):
        return {
            "agent_id": agent_id,
            "credential_hash": self.hash_credential(
                self.credential,
                self.pepper,
            ),
            "is_active": active,
            "revoked_at": revoked_at,
        }

    def test_registered_agent_is_authenticated(self):
        from unittest.mock import MagicMock

        db = MagicMock()
        db.get_agent_credential.return_value = self.make_record()

        result = self.authenticate(
            "agent-001", self.credential, db, self.pepper
        )

        self.assertTrue(result)
        db.get_agent_credential.assert_called_once_with("agent-001")

    def test_unknown_agent_is_rejected(self):
        from unittest.mock import MagicMock

        db = MagicMock()
        db.get_agent_credential.return_value = None

        self.assertFalse(
            self.authenticate(
                "unknown-agent", self.credential, db, self.pepper
            )
        )

    def test_revoked_agent_is_rejected(self):
        from unittest.mock import MagicMock

        db = MagicMock()
        db.get_agent_credential.return_value = self.make_record(
            revoked_at="2026-01-01"
        )

        self.assertFalse(
            self.authenticate(
                "agent-001", self.credential, db, self.pepper
            )
        )

    def test_inactive_agent_is_rejected(self):
        from unittest.mock import MagicMock

        db = MagicMock()
        db.get_agent_credential.return_value = self.make_record(
            active=False
        )

        self.assertFalse(
            self.authenticate(
                "agent-001", self.credential, db, self.pepper
            )
        )

    def test_database_failure_propagates(self):
        from unittest.mock import MagicMock

        db = MagicMock()
        db.get_agent_credential.side_effect = RuntimeError(
            "Simulated database failure"
        )

        with self.assertRaises(RuntimeError):
            self.authenticate(
                "agent-001", self.credential, db, self.pepper
            )

    def test_invalid_inputs_do_not_query_database(self):
        from unittest.mock import MagicMock

        for agent_id, credential in (
            (None, self.credential),
            ("", self.credential),
            (" agent-001", self.credential),
            ("agent-001", None),
            ("agent-001", ""),
        ):
            with self.subTest(agent_id=agent_id):
                db = MagicMock()

                self.assertFalse(
                    self.authenticate(
                        agent_id, credential, db, self.pepper
                    )
                )

                db.get_agent_credential.assert_not_called()

class TestAgentCredentialPepper(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import ast
        import os
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1]
            / "server"
            / "security.py"
        ).read_text(encoding="utf-8")

        tree = ast.parse(source)

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "load_agent_credential_pepper"
        )

        module = ast.Module(
            body=[function],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)

        namespace = {"os": os}

        exec(
            compile(module, "<pepper-test>", "exec"),
            namespace,
        )

        cls.load_pepper = staticmethod(
            namespace["load_agent_credential_pepper"]
        )

    def test_valid_pepper_is_loaded(self):
        from unittest.mock import patch

        pepper = "test-only-pepper-32-characters-minimum"

        with patch.dict(
            "os.environ",
            {"AGENT_CREDENTIAL_PEPPER": pepper},
        ):
            self.assertEqual(self.load_pepper(), pepper)

    def test_missing_pepper_is_rejected(self):
        from unittest.mock import patch

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                self.load_pepper()

    def test_short_pepper_is_rejected(self):
        from unittest.mock import patch

        with patch.dict(
            "os.environ",
            {"AGENT_CREDENTIAL_PEPPER": "short"},
        ):
            with self.assertRaises(RuntimeError):
                self.load_pepper()

    def test_exactly_32_characters_is_accepted(self):
        from unittest.mock import patch

        pepper = "A" * 32

        with patch.dict(
            "os.environ",
            {"AGENT_CREDENTIAL_PEPPER": pepper},
        ):
            self.assertEqual(self.load_pepper(), pepper)

if __name__ == "__main__":
    unittest.main()
