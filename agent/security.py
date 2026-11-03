import hmac
import hashlib
import time
import os


class SecurityManager:
    def __init__(self):
        self.secret_key = self._load_secret_key().encode("utf-8")

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
        message = str(time_window).encode("utf-8")

        return hmac.new(
            self.secret_key,
            message,
            hashlib.sha256
        ).hexdigest()