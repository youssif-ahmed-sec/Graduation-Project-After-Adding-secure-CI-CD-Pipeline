from flask import g
import ast
import unittest
from pathlib import Path


class TestEvidencePathSafety(unittest.TestCase):

    def test_evidence_paths_reject_unsafe_names(self):
        source = Path("server/db_manager.py").read_text(
            encoding="utf-8"
        )

        tree = ast.parse(source)

        db_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DBManager"
        )

        report_method = next(
            node for node in db_class.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "get_incident_report"
        )

        parser = next(
            node for node in report_method.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "parse_files"
        )

        # Execute only the isolated parser, not the server.
        namespace = {
            "Path": Path,
            "base": Path("evidence").resolve(),
        }
        exec(
            compile(
                ast.Module(body=[parser], type_ignores=[]),
                "<evidence-parser-test>",
                "exec",
            ),
            namespace,
        )

        parse_files = namespace["parse_files"]

        unsafe_names = [
            "../secret.txt",
            "..\\secret.txt",
            "/etc/passwd",
            "C:\\Windows\\win.ini",
            "folder/file.txt",
            "folder\\file.txt",
            ".",
            "..",
        ]

        for name in unsafe_names:
            with self.subTest(name=name):
                self.assertEqual(parse_files(name), [])

        result = parse_files("screenshot.png")
        self.assertEqual(len(result), 1)
        self.assertEqual(Path(result[0]).name, "screenshot.png")

    def test_evidence_download_requires_admin_authentication(self):
        source = Path("server/app.py").read_text(
            encoding="utf-8"
        )

        tree = ast.parse(source)

        endpoint = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "serve_evidence"
        )

        decorators = [
            node.id
            for node in endpoint.decorator_list
            if isinstance(node, ast.Name)
        ]

        self.assertIn("admin_required", decorators)

    def test_admin_required_rejects_missing_token(self):
        import ast
        from functools import wraps

        from flask import Flask, jsonify, request

        source = Path("server/app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        decorator_node = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "admin_required"
        )

        test_app = Flask(__name__)

        namespace = {
            "wraps": wraps,
            "request": request,
            "jsonify": jsonify,
        }

        exec(
            compile(
                ast.Module(body=[decorator_node], type_ignores=[]),
                "<admin-auth-test>",
                "exec",
            ),
            namespace,
        )

        @test_app.route("/test-protected")
        @namespace["admin_required"]
        def protected():
            return jsonify({"secret": "should-not-be-visible"})

        with test_app.test_client() as client:
            response = client.get("/test-protected")

        self.assertEqual(response.status_code, 401)
        self.assertNotIn(b"should-not-be-visible", response.data)

    def test_admin_required_rejects_invalid_tokens(self):
        import jwt
        from datetime import datetime, timedelta, timezone
        from functools import wraps
        from flask import Flask, jsonify, request

        source = Path("server/app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        decorator_node = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "admin_required"
        )

        test_app = Flask(__name__)
        test_secret = "filetrack-isolated-jwt-test-secret-32bytes-minimum"

        namespace = {
            "wraps": wraps,
            "request": request,
            "jsonify": jsonify,
            "jwt": jwt,
            "JWT_SECRET": test_secret,
        }

        exec(
            compile(
                ast.Module(body=[decorator_node], type_ignores=[]),
                "<admin-auth-test>",
                "exec",
            ),
            namespace,
        )

        @test_app.route("/test-protected")
        @namespace["admin_required"]
        def protected():
            return jsonify({"secret": "should-not-be-visible"})

        now = datetime.now(timezone.utc)

        cases = {
            "invalid_signature": jwt.encode(
                {
                    "user": "test-admin",
                    "token_type": "access",
                    "mfa_verified": True,
                    "iat": now,
                    "exp": now + timedelta(minutes=5),
                },
                "filetrack-different-jwt-test-secret-32bytes-minimum",
                algorithm="HS256",
            ),
            "expired_token": jwt.encode(
                {
                    "user": "test-admin",
                    "token_type": "access",
                    "mfa_verified": True,
                    "iat": now,
                    "exp": now - timedelta(minutes=5),
                },
                test_secret,
                algorithm="HS256",
            ),
            "mfa_not_verified": jwt.encode(
                {
                    "user": "test-admin",
                    "token_type": "access",
                    "mfa_verified": False,
                    "iat": now,
                    "exp": now + timedelta(minutes=5),
                },
                test_secret,
                algorithm="HS256",
            ),
            "wrong_token_type": jwt.encode(
                {
                    "user": "test-admin",
                    "token_type": "pre_mfa",
                    "mfa_verified": True,
                    "iat": now,
                    "exp": now + timedelta(minutes=5),
                },
                test_secret,
                algorithm="HS256",
            ),
        }

        with test_app.test_client() as client:
            for case_name, token in cases.items():
                with self.subTest(case=case_name):
                    response = client.get(
                        "/test-protected",
                        headers={"X-Admin-Token": token},
                    )

                    self.assertEqual(response.status_code, 401)
                    self.assertNotIn(
                        b"should-not-be-visible",
                        response.data,
                    )
    def test_admin_required_enforces_required_jwt_claims(self):
        import jwt
        from datetime import datetime, timedelta, timezone
        from functools import wraps
        from flask import Flask, jsonify, request

        source = Path("server/app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        decorator_node = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "admin_required"
        )

        test_app = Flask(__name__)
        test_secret = "filetrack-isolated-jwt-test-secret-32bytes-minimum"

        namespace = {
            "wraps": wraps,
            "g": g,
            "request": request,
            "jsonify": jsonify,
            "jwt": jwt,
            "JWT_SECRET": test_secret,
        }

        exec(
            compile(
                ast.Module(body=[decorator_node], type_ignores=[]),
                "<admin-required-test>",
                "exec",
            ),
            namespace,
        )

        @test_app.route("/test-protected")
        @namespace["admin_required"]
        def protected():
            return jsonify({
                "status": "ok",
                "admin_user": g.admin_user,
            })

        now = datetime.now(timezone.utc)

        valid_payload = {
            "user": "test-admin",
            "token_type": "access",
            "mfa_verified": True,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }

        test_cases = [
            ("valid_token", valid_payload, 200),
            (
                "missing_exp",
                {k: v for k, v in valid_payload.items() if k != "exp"},
                401,
            ),
            (
                "missing_iat",
                {k: v for k, v in valid_payload.items() if k != "iat"},
                401,
            ),
        ]

        with test_app.test_client() as client:
            for case_name, payload, expected_status in test_cases:
                with self.subTest(case=case_name):
                    token = jwt.encode(
                        payload,
                        test_secret,
                        algorithm="HS256",
                    )

                    response = client.get(
                        "/test-protected",
                        headers={"X-Admin-Token": token},
                    )

                if case_name == "valid_token":
                    self.assertEqual(
                        response.get_json()["admin_user"],
                        "test-admin",
                    )

    def test_evidence_exclusive_creation_prevents_overwrite(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_path = Path(temp_dir) / "screenshot.png"

            # Simulate an existing evidence artifact.
            evidence_path.write_bytes(b"original-evidence")

            # Use the same exclusive file mode as upload_artifact().
            with self.assertRaises(FileExistsError):
                with open(evidence_path, "xb") as destination:
                    destination.write(b"modified-evidence")

            # The original artifact must remain unchanged.
            self.assertEqual(
                evidence_path.read_bytes(),
                b"original-evidence",
            )

    def test_upload_request_size_limit(self):
        from io import BytesIO
        from werkzeug.test import EnvironBuilder
        from flask import Flask, jsonify, request
        from werkzeug.exceptions import RequestEntityTooLarge

        source = Path("server/app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        configured_limit = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "config"
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "MAX_CONTENT_LENGTH"
                ):
                    configured_limit = ast.literal_eval(
                        node.value
                    ) if isinstance(node.value, ast.Constant) else eval(
                        compile(
                            ast.Expression(node.value),
                            "<config-test>",
                            "eval",
                        ),
                        {"__builtins__": {}},
                    )

        self.assertEqual(configured_limit, 25 * 1024 * 1024)

        test_app = Flask(__name__)
        test_app.config["MAX_CONTENT_LENGTH"] = configured_limit

        @test_app.post("/test-upload")
        def test_upload():
            request.get_data()
            return jsonify({"status": "accepted"})


        oversized_length = configured_limit + 1

        builder = EnvironBuilder(
            method="POST",
            path="/test-upload",
            input_stream=BytesIO(b"x"),
            content_type="application/octet-stream",
        )

        try:
            environ = builder.get_environ()

            # Override the WSGI environment after EnvironBuilder
            # to simulate a request larger than the configured limit.
            environ["CONTENT_LENGTH"] = str(oversized_length)

            with test_app.request_context(environ):
                response = test_app.full_dispatch_request()

            self.assertEqual(response.status_code, 413)

        finally:
            builder.close()
        self.assertEqual(response.status_code, 413)

    def test_atomic_evidence_publish(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = Path(temp_dir)
            final_path = evidence_dir / "screenshot.png"
            temp_path = None

            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=".upload-",
                    suffix=".tmp",
                    dir=evidence_dir,
                    delete=False,
                ) as destination:
                    temp_path = destination.name

                    destination.write(b"complete-evidence")
                    destination.flush()
                    os.fsync(destination.fileno())

                    # Final evidence must not appear before publication.
                    self.assertFalse(final_path.exists())

                os.link(temp_path, final_path)

                self.assertEqual(
                    final_path.read_bytes(),
                    b"complete-evidence",
                )

                # Publishing the same filename again must fail.
                with self.assertRaises(FileExistsError):
                    os.link(temp_path, final_path)

                # Failed publication must not change existing evidence.
                self.assertEqual(
                    final_path.read_bytes(),
                    b"complete-evidence",
                )

            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

            self.assertFalse(Path(temp_path).exists())

    def test_admin_access_token_issuer_includes_required_claims(self):
        source = Path("server/app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        verify_2fa = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "verify_2fa"
        )

        access_token_payloads = []

        for node in ast.walk(verify_2fa):
            if not isinstance(node, ast.Call):
                continue

            if not (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "jwt"
                and node.func.attr == "encode"
            ):
                continue

            if not node.args or not isinstance(node.args[0], ast.Dict):
                continue

            payload = node.args[0]
            keys = {
                key.value
                for key in payload.keys
                if isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            }

            if "token_type" in keys:
                access_token_payloads.append(keys)

        self.assertEqual(len(access_token_payloads), 1)
        self.assertIn("iat", access_token_payloads[0])
        self.assertIn("exp", access_token_payloads[0])
        self.assertIn("mfa_verified", access_token_payloads[0])

    def test_attach_artifact_preserves_existing_evidence(self):
        from unittest.mock import Mock

        source = Path("server/db_manager.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)

        db_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DBManager"
        )

        attach_method = next(
            node for node in db_class.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "attach_artifact"
        )

        namespace = {}

        exec(
            compile(
                ast.Module(body=[attach_method], type_ignores=[]),
                "<attach-artifact-test>",
                "exec",
            ),
            namespace,
        )

        class FakeDB:
            attach_artifact = namespace["attach_artifact"]

            def __init__(self, row):
                self.row = row
                self.queries = []

            def _execute_query(self, query, params=(), fetch=None):
                self.queries.append((query, params, fetch))
                return self.row if fetch == "one" else None

        row = {
            "log_id": 42,
            "screenshot_path": "first.png,second.png",
            "camera_path": None,
            "audio_path": None,
            "dump_path": None,
        }

        db = FakeDB(row)

        self.assertTrue(
            db.attach_artifact("agent-test", "third.png", "screenshot")
        )

        update_query, update_params, _ = db.queries[-1]

        self.assertIn("UPDATE threat_logs", update_query)
        self.assertEqual(
            update_params,
            ("first.png,second.png,third.png", 42),
        )

        # An existing filename must not be added twice.
        db.queries.clear()
        self.assertTrue(
            db.attach_artifact("agent-test", "second.png", "screenshot")
        )

        _, duplicate_params, _ = db.queries[-1]
        self.assertEqual(
            duplicate_params,
            ("first.png,second.png", 42),
        )

        # No incident means the artifact was not linked.
        missing_db = FakeDB(None)
        self.assertFalse(
            missing_db.attach_artifact(
                "agent-test", "third.png", "screenshot"
            )
        )
        self.assertEqual(len(missing_db.queries), 1)

    def test_upload_artifact_database_outcomes(self):
        import io
        import os
        import tempfile
        import logging
        from unittest.mock import Mock
        from flask import Flask, jsonify, request
        from werkzeug.utils import secure_filename

        source = Path("server/app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        upload_node = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "upload_artifact"
        )

        test_app = Flask(__name__)
        test_app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

        fake_db = Mock()

        namespace = {
            "app": test_app,
            "request": request,
            "jsonify": jsonify,
            "secure_filename": secure_filename,
            "verify_agent": lambda req: True,
            "tempfile": tempfile,
            "os": os,
            "db": fake_db,
        }

        exec(
            compile(
                ast.Module(body=[upload_node], type_ignores=[]),
                "<upload-artifact-test>",
                "exec",
            ),
            namespace,
        )

        test_app.add_url_rule(
            "/api/v1/upload_artifact",
            view_func=namespace["upload_artifact"],
            methods=["POST"],
        )

        cases = [
            ("success", True, 200),
            ("missing_incident", False, 409),
            ("database_failure", RuntimeError("Test database failure"), 500),
        ]

        for case_name, db_result, expected_status in cases:
            with self.subTest(case=case_name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    namespace["EVIDENCE_FOLDER"] = temp_dir

                    fake_db.reset_mock()
                    fake_db.incident_exists_for_agent.return_value = True

                    if isinstance(db_result, Exception):
                        fake_db.attach_artifact_to_log.side_effect = db_result
                    else:
                        fake_db.attach_artifact_to_log.side_effect = None
                        fake_db.attach_artifact_to_log.return_value = db_result

                    filename = f"{case_name}.png"
                    file_content = b"fake-evidence-content"

                    with test_app.test_client() as client:
                        response = client.post(
                            "/api/v1/upload_artifact",
                            data={
                                "agent_id": "test-agent",
                                "log_id": "42",
                                "file": (
                                    io.BytesIO(file_content),
                                    filename,
                                ),
                            },
                            content_type="multipart/form-data",
                        )

                    self.assertEqual(
                        response.status_code,
                        expected_status,
                    )

                    saved_file = Path(temp_dir) / filename

                    self.assertTrue(saved_file.exists())
                    self.assertEqual(
                        saved_file.read_bytes(),
                        file_content,
                    )

                    # Temporary upload files must be removed.
                    self.assertFalse(
                        list(Path(temp_dir).glob(".upload-*.tmp"))
                    )

                    fake_db.attach_artifact_to_log.assert_called_once_with(
                        42,
                        "test-agent",
                        filename,
                        "screenshot",
                    )

        invalid_log_ids = [
            ("missing", None),
            ("local_id", "LOG_123"),
            ("zero", "0"),
            ("negative", "-1"),
            ("letters", "abc"),
        ]

        for case_name, invalid_id in invalid_log_ids:
            with self.subTest(invalid_log_id=case_name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    namespace["EVIDENCE_FOLDER"] = temp_dir
                    fake_db.reset_mock()

                    filename = f"invalid_{case_name}.png"
                    data = {
                        "agent_id": "test-agent",
                        "file": (
                            io.BytesIO(b"fake-evidence-content"),
                            filename,
                        ),
                    }

                    if invalid_id is not None:
                        data["log_id"] = invalid_id

                    with test_app.test_client() as client:
                        response = client.post(
                            "/api/v1/upload_artifact",
                            data=data,
                            content_type="multipart/form-data",
                        )

                    self.assertEqual(response.status_code, 400)
                    self.assertFalse(
                        (Path(temp_dir) / filename).exists()
                    )
                    fake_db.attach_artifact_to_log.assert_not_called()

        validation_cases = [
            ("incident_not_found", False, 409),
            (
                "database_error",
                RuntimeError("Simulated validation failure"),
                500,
            ),
        ]

        for case_name, validation_result, expected_status in validation_cases:
            with self.subTest(validation_case=case_name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    namespace["EVIDENCE_FOLDER"] = temp_dir
                    fake_db.reset_mock()

                    fake_db.incident_exists_for_agent.side_effect = None

                    if isinstance(validation_result, Exception):
                        fake_db.incident_exists_for_agent.side_effect = (
                            validation_result
                        )
                    else:
                        fake_db.incident_exists_for_agent.return_value = (
                            validation_result
                        )

                    filename = f"{case_name}.png"

                    with test_app.test_client() as client:
                        response = client.post(
                            "/api/v1/upload_artifact",
                            data={
                                "agent_id": "test-agent",
                                "log_id": "42",
                                "file": (
                                    io.BytesIO(b"safe-test-evidence"),
                                    filename,
                                ),
                            },
                            content_type="multipart/form-data",
                        )

                    self.assertEqual(
                        response.status_code,
                        expected_status,
                    )

                    fake_db.incident_exists_for_agent.assert_called_once_with(
                        42,
                        "test-agent",
                    )

                    fake_db.attach_artifact_to_log.assert_not_called()

                    self.assertFalse(
                        (Path(temp_dir) / filename).exists()
                    )

                    self.assertEqual(
                        list(Path(temp_dir).iterdir()),
                        [],
                    )


if __name__ == "__main__":
    unittest.main()
