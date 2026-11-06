
import os
import unittest
import uuid

from server.db_manager import DBManager
from server.security import (
    generate_agent_credential,
    hash_agent_credential,
    authenticate_registered_agent,
)


class PostgresAgentEnrollmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("FILETRACK_RUN_PG_INTEGRATION") != "1":
            raise unittest.SkipTest(
                "PostgreSQL integration tests are opt-in"
            )

        # Prevent accidental access to project/production DBs.
        if (
            os.getenv("DB_NAME") != "filetrack_enrollment_test"
            or os.getenv("DB_HOST") != "127.0.0.1"
            or os.getenv("DB_PORT") != "55432"
        ):
            raise RuntimeError(
                "Refusing to run against a non-test database"
            )

        cls.db = DBManager()

    def setUp(self):
        self.agent_id = "integration-" + uuid.uuid4().hex
        self.pepper = "integration-test-pepper-" + ("x" * 32)

    def tearDown(self):
        # agent_credentials has ON DELETE CASCADE.
        self.db._execute_query(
            "DELETE FROM agents WHERE agent_id = %s",
            (self.agent_id,),
        )

    def test_complete_agent_credential_lifecycle(self):
        # 1. Approve agent.
        self.assertTrue(
            self.db.create_pending_agent(self.agent_id)
        )

        self.assertTrue(
            self.db.agent_exists(self.agent_id)
        )

        row = self.db._execute_query(
            """
            SELECT status, last_heartbeat
            FROM agents
            WHERE agent_id = %s
            """,
            (self.agent_id,),
            fetch="one",
        )

        self.assertEqual(row["status"], "Pending")
        self.assertIsNone(row["last_heartbeat"])

        # Duplicate approval must not overwrite agent.
        self.assertFalse(
            self.db.create_pending_agent(self.agent_id)
        )

        # 2. Provision unique pending credential.
        credential = generate_agent_credential()
        credential_hash = hash_agent_credential(
            credential,
            self.pepper,
        )

        self.assertTrue(
            self.db.create_pending_agent_credential(
                self.agent_id,
                credential_hash,
            )
        )

        stored = self.db.get_agent_credential(self.agent_id)

        self.assertEqual(
            stored["credential_hash"],
            credential_hash,
        )
        self.assertNotEqual(
            stored["credential_hash"],
            credential,
        )
        self.assertFalse(stored["is_active"])
        self.assertIsNone(stored["revoked_at"])

        # Pending credentials must not authenticate.
        self.assertFalse(
            authenticate_registered_agent(
                self.agent_id,
                credential,
                self.db,
                self.pepper,
            )
        )

        # Cannot overwrite existing credential.
        self.assertFalse(
            self.db.create_pending_agent_credential(
                self.agent_id,
                credential_hash,
            )
        )

        # 3. Activate credential.
        self.assertTrue(
            self.db.activate_agent_credential(self.agent_id)
        )

        self.assertFalse(
            self.db.activate_agent_credential(self.agent_id)
        )

        # 4. Verify authenticated identity.
        self.assertTrue(
            authenticate_registered_agent(
                self.agent_id,
                credential,
                self.db,
                self.pepper,
            )
        )

        self.assertFalse(
            authenticate_registered_agent(
                self.agent_id,
                "incorrect-credential",
                self.db,
                self.pepper,
            )
        )

        self.assertFalse(
            authenticate_registered_agent(
                "another-agent",
                credential,
                self.db,
                self.pepper,
            )
        )

        # 5. Revoke credential.
        self.assertTrue(
            self.db.revoke_agent_credential(self.agent_id)
        )

        revoked = self.db.get_agent_credential(self.agent_id)

        self.assertFalse(revoked["is_active"])
        self.assertIsNotNone(revoked["revoked_at"])

        self.assertFalse(
            authenticate_registered_agent(
                self.agent_id,
                credential,
                self.db,
                self.pepper,
            )
        )

        # Revoked credentials cannot be reactivated.
        self.assertFalse(
            self.db.activate_agent_credential(self.agent_id)
        )

        self.assertFalse(
            self.db.revoke_agent_credential(self.agent_id)
        )


if __name__ == "__main__":
    unittest.main()
