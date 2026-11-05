
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


if __name__ == "__main__":
    unittest.main()
