import hmac
import os
import hashlib
import time
import json
import secrets


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

def verify_agent_credential(credential, stored_hash, pepper):
    """
    Verify an agent credential against its stored HMAC fingerprint.

    Credential activation and revocation must be checked
    separately using the database record.
    """
    if not isinstance(credential, str) or not credential:
        return False

    if not isinstance(stored_hash, str) or len(stored_hash) != 64:
        return False

    if any(c not in "0123456789abcdef" for c in stored_hash):
        return False

    try:
        calculated_hash = hash_agent_credential(credential, pepper)
    except ValueError:
        return False

    return hmac.compare_digest(calculated_hash, stored_hash)

def authenticate_agent_credential(
    agent_id,
    credential,
    credential_record,
    pepper
):
    """
    Authenticate an agent using its identity, credential,
    and current database credential state.

    The credential record must come from a trusted
    database lookup for this specific agent_id.
    """
    if (
        not isinstance(agent_id, str)
        or not agent_id
        or agent_id != agent_id.strip()
    ):
        return False

    if not isinstance(credential_record, dict):
        return False

    if credential_record.get("agent_id") != agent_id:
        return False

    if credential_record.get("is_active") is not True:
        return False

    if credential_record.get("revoked_at") is not None:
        return False

    return verify_agent_credential(
        credential,
        credential_record.get("credential_hash"),
        pepper
    )

def authenticate_registered_agent(
    agent_id,
    credential,
    db,
    pepper
):
    """
    Authenticate a registered agent using its current
    credential record from the trusted database.

    Database failures must propagate to the caller
    so authentication fails closed.
    """
    if (
        not isinstance(agent_id, str)
        or not agent_id
        or agent_id != agent_id.strip()
    ):
        return False

    if not isinstance(credential, str) or not credential:
        return False

    record = db.get_agent_credential(agent_id)

    if record is None:
        return False

    return authenticate_agent_credential(
        agent_id,
        credential,
        record,
        pepper
    )

def load_agent_credential_pepper():
    """
    Load the server-only credential hashing secret.

    This secret must never be sent to an agent,
    included in API responses, or committed to Git.
    """
    pepper = os.environ.get("AGENT_CREDENTIAL_PEPPER")

    if not isinstance(pepper, str) or len(pepper) < 32:
        raise RuntimeError(
            "AGENT_CREDENTIAL_PEPPER must be configured "
            "with at least 32 characters"
        )

    return pepper
