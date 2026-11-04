
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

from flask import Flask, jsonify, make_response, request, g

class TestPDFEndpoint(unittest.TestCase):

    def test_pdf_endpoint_outcomes(self):
        source = Path("server/app.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)

        function_node = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "generate_pdf_report"
        )

        # Remove route decorators only in this isolated test.
        function_node.decorator_list = []

        test_app = Flask(__name__)
        @test_app.before_request
        def set_test_admin():
            g.admin_user = "test-admin"
        fake_db = Mock()
        fake_jwt = Mock()
        fake_jwt.decode.return_value = {"user": "test-admin"}
        fake_renderer = Mock()

        report_data = {
            "metadata": {"report_id": "FT-REP-42"}
        }

        namespace = {
            "request": request,
            "g": g,
            "jsonify": jsonify,
            "make_response": make_response,
            "jwt": fake_jwt,
            "JWT_SECRET": "test-only-secret",
            "db": fake_db,
            "app": test_app,
            "render_template": Mock(
                return_value="<h1>Fake Incident Report</h1>"
            ),
            "render_pdf": fake_renderer,
        }

        exec(
            compile(
                ast.Module(
                    body=[function_node],
                    type_ignores=[],
                ),
                "<pdf-endpoint-test>",
                "exec",
            ),
            namespace,
        )

        test_app.add_url_rule(
            "/api/v1/admin/generate_report/<int:log_id>",
            view_func=namespace["generate_pdf_report"],
            methods=["GET"],
        )

        headers = {"X-Admin-Token": "fake-test-token"}

        with test_app.test_client() as client:

            # 1. Successful report generation.
            fake_db.get_incident_report.return_value = report_data
            fake_renderer.side_effect = None
            fake_renderer.return_value = b"%PDF-1.7\nfake-pdf"

            response = client.get(
                "/api/v1/admin/generate_report/42",
                headers=headers,
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "application/pdf")
            self.assertTrue(response.data.startswith(b"%PDF-"))
            self.assertIn(
                "FT-REP-42.pdf",
                response.headers["Content-Disposition"],
            )
            fake_db.get_incident_report.assert_called_with(
                42, "test-admin"
            )

            # 2. Incident does not exist.
            fake_db.get_incident_report.return_value = None
            fake_renderer.reset_mock()

            response = client.get(
                "/api/v1/admin/generate_report/999",
                headers=headers,
            )

            self.assertEqual(response.status_code, 404)
            fake_renderer.assert_not_called()

            # 3. PDF renderer failure.
            fake_db.get_incident_report.return_value = report_data
            fake_renderer.side_effect = RuntimeError(
                "Sensitive internal test error"
            )

            response = client.get(
                "/api/v1/admin/generate_report/42",
                headers=headers,
            )

            self.assertEqual(response.status_code, 500)
            self.assertNotIn(
                b"Sensitive internal test error",
                response.data,
            )


if __name__ == "__main__":
    unittest.main()
