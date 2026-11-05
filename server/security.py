import hmac
import os
import hashlib
import time
import json
import secrets

class SecurityManager:

    def __init__(self):

        self.secret_key = self._load_secret_key().encode()



    def _load_secret_key(self):
        secret = os.environ.get("AGENT_SECRET_KEY")

        if not secret or len(secret) < 32:
            raise RuntimeError(
                "AGENT_SECRET_KEY must be configured with at least 32 characters"
            )

        return secret



    def generate_current_token(self):


        current_time = int(time.time())

        time_window = current_time // 300

        message = str(time_window).encode()

        return hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()



    def verify_token(self, provided_token):


        if not provided_token:

            return False



        expected_token = self.generate_current_token()


        return hmac.compare_digest(expected_token, provided_token)

def generate_agent_credential():
    """
    Generate a cryptographically secure, independent agent credential.
    The plaintext credential must be delivered through an approved
    enrollment workflow and must never be logged.
    """
    return secrets.token_urlsafe(32)


def hash_agent_credential(credential, pepper):
    """
    Compute a server-side HMAC fingerprint of an agent credential.
    The pepper must be a separate, securely stored server secret.
    """
    if not isinstance(credential, str) or not credential:
        raise ValueError("Invalid credential")

    if not isinstance(pepper, str) or len(pepper) < 32:
        raise ValueError("Invalid credential hashing key")

    return hmac.new(
        pepper.encode("utf-8"),
        credential.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
