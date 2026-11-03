
import getpass
import sys

from psycopg2 import sql
from werkzeug.security import generate_password_hash
from db_manager import DBManager


def main():
    db = DBManager()

    username = input("Enter first admin username: ").strip()

    if not username or len(username) > 64:
        print("Invalid username.")
        sys.exit(1)

    password = getpass.getpass("Enter admin password: ")
    confirm = getpass.getpass("Confirm admin password: ")

    if len(password) < 16:
        print("ERROR: Password must be at least 16 characters.")
        sys.exit(1)

    if password != confirm:
        print("ERROR: Password confirmation does not match.")
        sys.exit(1)

    password_hash = generate_password_hash(password)
    for field_name, value in [
    ("username", username),
    ("password_hash", password_hash),
    ]:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            print(f"ERROR: Invalid Unicode encoding in {field_name}.")
            sys.exit(1)

    conn = db._get_connection()
    try:
        with conn:
            with conn.cursor() as cursor:
                # Prevent two bootstrap processes from running simultaneously.
                cursor.execute(
                    "LOCK TABLE admin_users IN EXCLUSIVE MODE"
                )

                cursor.execute("SELECT COUNT(*) AS count FROM admin_users")
                if cursor.fetchone()["count"] != 0:
                    raise RuntimeError(
                        "Bootstrap refused: admin accounts already exist."
                    )

                cursor.execute(
                    """
                    INSERT INTO admin_users
                        (username, password_hash, role)
                    VALUES (%s, %s, %s)
                    """,
                    (username, password_hash, "SuperAdmin")
                )

        print("First SuperAdmin created successfully.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
