import ast
import unittest
from pathlib import Path


APP_FILE = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "app.py"
)


class SocketIOCorsPolicyTests(unittest.TestCase):
    def test_socketio_does_not_allow_all_origins(self):
        tree = ast.parse(
            APP_FILE.read_text(encoding="utf-8")
        )

        socketio_calls = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "SocketIO"
            ):
                socketio_calls.append(node)

        self.assertEqual(len(socketio_calls), 1)

        call = socketio_calls[0]

        cors_argument = next(
            (
                keyword.value
                for keyword in call.keywords
                if keyword.arg == "cors_allowed_origins"
            ),
            None,
        )

        self.assertIsNotNone(
            cors_argument,
            "Socket.IO CORS configuration must be explicit",
        )

        self.assertIsInstance(
            cors_argument,
            ast.Constant,
        )

        self.assertIsNone(
            cors_argument.value,
            "Socket.IO must use same-origin restrictions",
        )


if __name__ == "__main__":
    unittest.main()
