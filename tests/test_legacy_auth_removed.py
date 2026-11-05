import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LegacyAuthRemovalTests(unittest.TestCase):

    def test_legacy_agent_security_module_removed(self):
        self.assertFalse(
            (ROOT / "agent" / "security.py").exists()
        )

    def test_legacy_auth_symbols_removed(self):
        files = [
            "agent/client.py",
            "server/app.py",
            "server/security.py",
            "docker-compose.yml",
            ".github/workflows/dast-zap.yml",
            "infra/k8s/server.yaml",
        ]

        forbidden = [
            "get_secure_headers",
            "generate_current_token",
            "verify_token",
            "SecurityManager",
            "AGENT_SECRET_KEY",
        ]

        for filename in files:
            content = (
                ROOT / filename
            ).read_text(encoding="utf-8")

            for symbol in forbidden:
                with self.subTest(
                    file=filename,
                    symbol=symbol
                ):
                    self.assertNotIn(symbol, content)

    def test_agent_credential_authentication_preserved(self):
        client = (
            ROOT / "agent/client.py"
        ).read_text(encoding="utf-8")

        server = (
            ROOT / "server/security.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "FILETRACK_AGENT_CREDENTIAL",
            client
        )
        self.assertIn(
            "authenticate_registered_agent",
            server
        )
        self.assertIn(
            "AGENT_CREDENTIAL_PEPPER",
            server
        )
    def test_server_retains_new_agent_auth_imports(self):
        import ast

        app_file = ROOT / "server" / "app.py"
        tree = ast.parse(app_file.read_text(encoding="utf-8"))

        required = {
            "generate_agent_credential",
            "hash_agent_credential",
            "authenticate_registered_agent",
            "load_agent_credential_pepper",
        }

        imported = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "security":
                imported.update(alias.name for alias in node.names)

        self.assertTrue(
            required.issubset(imported),
            f"Missing security imports: {required - imported}",
        )

if __name__ == "__main__":
    unittest.main()
