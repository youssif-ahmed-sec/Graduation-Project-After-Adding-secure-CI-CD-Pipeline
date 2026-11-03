
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE_FILE = ROOT / "agent" / "modules" / "response_engine.py"
CLIENT_FILE = ROOT / "agent" / "client.py"
SERVER_FILE = ROOT / "server" / "app.py"


class TestAgentSafety(unittest.TestCase):

    def test_containment_methods_have_safety_gate(self):
        tree = ast.parse(ENGINE_FILE.read_text(encoding="utf-8"))

        engine = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ResponseEngine"
        )

        protected_methods = {
            "deny_all_access",
            "isolate_network",
            "restore_network",
            "isolate_usb",
            "restore_usb",
        }

        for method in engine.body:
            if not isinstance(method, ast.FunctionDef):
                continue

            if method.name not in protected_methods:
                continue

            with self.subTest(method=method.name):
                self.assertTrue(
                    method.body
                    and isinstance(method.body[0], ast.If)
                    and ast.unparse(method.body[0].test)
                    == "not containment_enabled()",
                    f"{method.name} must start with a safety gate",
                )

    def test_client_has_no_icacls_reset(self):
        source = CLIENT_FILE.read_text(encoding="utf-8")
        self.assertNotIn("icacls", source.lower())

    def test_remote_shell_execution_is_disabled(self):
        tree = ast.parse(CLIENT_FILE.read_text(encoding="utf-8"))

        handlers = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "on_execute_cmd"
        ]

        self.assertEqual(
            len(handlers), 1,
            "Expected exactly one remote-shell rejection handler"
        )

        handler = handlers[0]
        forbidden = {"run", "Popen", "check_output", "check_call", "call", "system", "exec", "eval"}

        for node in ast.walk(handler):
            if isinstance(node, ast.Call):
                function_name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else None
                )

                self.assertNotIn(
                    function_name,
                    forbidden,
                    f"Forbidden execution call found: {function_name}"
                )

    def test_server_does_not_emit_remote_shell_command(self):
        tree = ast.parse(SERVER_FILE.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if not isinstance(node.func, ast.Attribute):
                continue

            if node.func.attr != "emit" or not node.args:
                continue

            event = node.args[0]

            self.assertFalse(
                isinstance(event, ast.Constant)
                and event.value == "execute_cmd",
                "SECURITY: Server must not emit execute_cmd"
            )


if __name__ == "__main__":
    unittest.main()
