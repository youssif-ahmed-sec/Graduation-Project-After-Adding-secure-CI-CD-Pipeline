import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path

class DBManager:
    def __init__(self):
        self.db_params = {
            "dbname": os.getenv("DB_NAME", "filetrack_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.environ["DB_PASS"],
            "host": os.getenv("DB_HOST", "db"),
            "port": "5432"
        }
        self.setup_environment()
        self.create_tables()

    def setup_environment(self):
        os.makedirs("database", exist_ok=True)
        os.makedirs("evidence", exist_ok=True)

    def _get_connection(self):
        return psycopg2.connect(**self.db_params, cursor_factory=RealDictCursor)

    def _execute_query(self, query, params=(), fetch=None):
        pg_query = query.replace("?", "%s").replace("AUTOINCREMENT", "SERIAL")
        conn = self._get_connection()
        cursor = conn.cursor()
        result = None
        try:
            cursor.execute(pg_query, params)
            if fetch == "all":
                result = [dict(row) for row in cursor.fetchall()]
            elif fetch == "one":
                row = cursor.fetchone()
                result = dict(row) if row else None
            elif fetch == "lastrowid":
                cursor.execute("SELECT LASTVAL()")
                result = cursor.fetchone()['lastval']
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
        return result

    def create_tables(self):
        queries = [
            '''CREATE TABLE IF NOT EXISTS admin_users (
                user_id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'Analyst',
                email TEXT,
                totp_secret TEXT,
                last_login TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                user_id INTEGER,
                hostname TEXT,
                ip_address TEXT,
                mac_address TEXT,
                os_details TEXT,
                status TEXT DEFAULT 'Online',
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS agent_credentials (
                agent_id TEXT PRIMARY KEY REFERENCES agents(agent_id) ON DELETE CASCADE,
                credential_hash TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMPTZ
            )''',
            '''CREATE TABLE IF NOT EXISTS security_policies (
                policy_id SERIAL PRIMARY KEY,
                user_id INTEGER,
                name TEXT NOT NULL,
                security_level TEXT,
                action_type TEXT,
                is_active INTEGER DEFAULT 1
            )''',
            '''CREATE TABLE IF NOT EXISTS honey_files (
                file_id SERIAL PRIMARY KEY,
                agent_id TEXT REFERENCES agents(agent_id),
                policy_id INTEGER,
                file_path TEXT NOT NULL,
                file_type TEXT,
                file_category TEXT DEFAULT 'honey',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS threat_logs (
                log_id SERIAL PRIMARY KEY,
                agent_id TEXT REFERENCES agents(agent_id),
                policy_id INTEGER,
                file_id INTEGER,
                hostname TEXT,
                ip_address TEXT,
                mac_address TEXT,
                os_details TEXT,
                severity_level TEXT,
                action_type TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                file_type TEXT,
                attacker_process TEXT,
                action_status TEXT,
                screenshot_path TEXT,
                camera_path TEXT,
                audio_path TEXT,
                dump_path TEXT,
                file_hash_before TEXT,
                file_hash_after TEXT,
                process_tree TEXT,
                ai_context TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS response_policies (
                level TEXT PRIMARY KEY,
                actions_json TEXT NOT NULL
            )''',
            '''CREATE TABLE IF NOT EXISTS admin_audit_logs (
                audit_id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )'''
        ]
        for q in queries:
            self._execute_query(q)

        if not self._execute_query("SELECT * FROM response_policies LIMIT 1", fetch="one"):
            defaults = {
                "LOW": json.dumps(["Calculate Hash", "Log Events", "Notify Admin"]),
                "MEDIUM": json.dumps(["Calculate Hash", "Log Events", "Notify Admin", "Take Screenshot"]),
                "HIGH": json.dumps(["Calculate Hash", "Log Events", "Notify Admin", "Take Screenshot", "Set Read-Only"]),
                "CRITICAL": json.dumps(["Calculate Hash", "Log Events", "Notify Admin", "Take Screenshot", "Restrict File Access", "Auto Revert", "Record Camera & Mic"])
            }
            for lvl, acts in defaults.items():
                self._execute_query("INSERT INTO response_policies (level, actions_json) VALUES (%s, %s)", (lvl, acts))

        self._execute_query("ALTER TABLE honey_files ADD COLUMN IF NOT EXISTS file_category TEXT DEFAULT 'honey'")

    def get_all_admins(self):
        return self._execute_query("SELECT user_id, username, role, last_login FROM admin_users", fetch="all")

    def add_admin(self, username, password, role):
        hashed = generate_password_hash(password)
        try:
            self._execute_query('INSERT INTO admin_users (username, password_hash, role) VALUES (%s, %s, %s)', (username, hashed, role))
            return True
        except: return False

    def update_admin_password(self, username, new_password):
        hashed = generate_password_hash(new_password)
        self._execute_query("UPDATE admin_users SET password_hash = %s WHERE username = %s", (hashed, username))

    def delete_admin(self, username):
        if username != 'admin':
            self._execute_query("DELETE FROM admin_users WHERE username = %s", (username,))

    def verify_admin(self, username, password):
        row = self._execute_query("SELECT password_hash, role FROM admin_users WHERE username = %s", (username,), fetch="one")
        if row and check_password_hash(row['password_hash'], password):
            self._execute_query("UPDATE admin_users SET last_login = CURRENT_TIMESTAMP WHERE username = %s", (username,))
            return row
        return False

    def get_admin_totp_secret(self, username):
        row = self._execute_query("SELECT totp_secret FROM admin_users WHERE username = %s", (username,), fetch="one")
        return row['totp_secret'] if row and 'totp_secret' in row else None

    def set_admin_totp_secret(self, username, secret):
        self._execute_query("UPDATE admin_users SET totp_secret = %s WHERE username = %s", (secret, username))

    def update_setting(self, key, value):
        self._execute_query('INSERT INTO system_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value', (key, str(value)))

    def get_setting(self, key):
        row = self._execute_query('SELECT value FROM system_settings WHERE key = %s', (key,), fetch="one")
        return row['value'] if row else None

    def get_agent_credential(self, agent_id):
        """
        Fetch credential metadata for a specific registered agent.
        This method must not return a plaintext credential.
        """
        if not isinstance(agent_id, str) or not agent_id.strip():
            return None

        query = """
            SELECT agent_id, credential_hash, is_active, revoked_at
            FROM agent_credentials
            WHERE agent_id = %s
            LIMIT 1
        """

        return self._execute_query(
            query,
            (agent_id,),
            fetch="one"
        )

    def register_agent(self, agent_id, hostname, ip, mac, os_info, user_id=None):
        query = '''INSERT INTO agents (agent_id, user_id, hostname, ip_address, mac_address, os_details, status, last_heartbeat)
                   VALUES (%s, %s, %s, %s, %s, %s, 'Online', CURRENT_TIMESTAMP)
                   ON CONFLICT (agent_id) DO UPDATE SET last_heartbeat = CURRENT_TIMESTAMP, status = 'Online', hostname = EXCLUDED.hostname, ip_address = EXCLUDED.ip_address'''
        self._execute_query(query, (agent_id, user_id, hostname, ip, mac, os_info))

    def update_heartbeat(self, agent_id):
        self._execute_query("UPDATE agents SET last_heartbeat = CURRENT_TIMESTAMP, status = 'Online' WHERE agent_id = %s", (agent_id,))

    def get_all_agents(self):
        query = "SELECT agent_id, hostname, ip_address, mac_address, os_details, CASE WHEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_heartbeat)) > 30 THEN 'Offline' ELSE 'Online' END as status, last_heartbeat FROM agents"
        return self._execute_query(query, fetch="all")

    def log_threat(self, log_data):
        agent_id = log_data.get('agent_id')
        file_path = log_data.get('file_path', '')
        if file_path:
            file_name = file_path.replace('\\', '/').split('/')[-1]
            hf = self._execute_query("SELECT file_type, file_id, policy_id FROM honey_files WHERE agent_id = %s AND file_path ILIKE %s", (agent_id, f"%{file_name}%"), fetch="one")
            if hf:
                log_data.update({"severity_level": hf['file_type'], "file_id": hf['file_id'], "policy_id": hf['policy_id']})

        cols = ', '.join(log_data.keys())
        p = ', '.join(['%s' for _ in log_data])
        query = f"INSERT INTO threat_logs ({cols}) VALUES ({p}) RETURNING log_id"

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, list(log_data.values()))
        last_id = cursor.fetchone()['log_id']
        conn.commit()
        conn.close()
        return last_id

    def get_all_threats(self):
        query = """
            SELECT
                t.log_id, t.agent_id, t.policy_id, t.file_id, t.severity_level,
                t.action_type, t.timestamp, t.file_path, t.file_type,
                t.attacker_process, t.action_status, t.screenshot_path,
                t.camera_path, t.audio_path, t.dump_path, t.file_hash_before,
                t.file_hash_after, t.process_tree, t.ai_context,
                a.hostname, a.ip_address, a.mac_address, a.os_details
            FROM threat_logs t
            LEFT JOIN agents a ON t.agent_id = a.agent_id
            ORDER BY t.timestamp DESC
        """
        return self._execute_query(query, fetch="all")

    def clear_all_threats(self):
        self._execute_query("DELETE FROM threat_logs")

    def update_ai_analysis(self, log_id, ai_text):
        self._execute_query("UPDATE threat_logs SET ai_context = %s WHERE log_id = %s", (ai_text, log_id))


    def attach_artifact(self, agent_id, file_path, artifact_type):
        row = self._execute_query(
            """
            SELECT log_id, screenshot_path, camera_path,
                   audio_path, dump_path
            FROM threat_logs
            WHERE agent_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (agent_id,),
            fetch="one"
        )
        if not row:
            return False
        column_map = {
            "screenshot": "screenshot_path",
            "camera": "camera_path",
            "audio": "audio_path",
            "dump": "dump_path",
        }
        if artifact_type not in column_map:
            raise ValueError("Unsupported artifact type")
        col = column_map[artifact_type]
        existing_files = [
            name.strip()
            for name in (row[col] or "").split(",")
            if name.strip()
        ]
        if file_path not in existing_files:
            existing_files.append(file_path)

        self._execute_query(
            f"UPDATE threat_logs SET {col} = %s WHERE log_id = %s",
            (",".join(existing_files), row["log_id"])
        )
        return True

    def incident_exists_for_agent(self, log_id, agent_id):
        """Check whether an incident belongs to the supplied agent."""
        if type(log_id) is not int or log_id <= 0:
            return False

        if not agent_id:
            return False

        row = self._execute_query(
            """
            SELECT log_id
            FROM threat_logs
            WHERE log_id = %s AND agent_id = %s
            LIMIT 1
            """,
            (log_id, agent_id),
            fetch="one",
        )

        return row is not None

    def attach_artifact_to_log(self, log_id, agent_id, file_path, artifact_type):
        """Attach evidence to a specific incident atomically."""
        column_map = {
            "screenshot": "screenshot_path",
            "camera": "camera_path",
            "audio": "audio_path",
            "dump": "dump_path",
        }

        if artifact_type not in column_map:
            raise ValueError("Unsupported artifact type")

        if type(log_id) is not int or log_id <= 0:
            raise ValueError("Invalid log_id")

        if not agent_id or not file_path:
            raise ValueError("Missing agent or evidence filename")

        column = column_map[artifact_type]

        conn = self._get_connection()
        cursor = None

        try:
            cursor = conn.cursor()

            cursor.execute(
                f"""
                SELECT {column}
                FROM threat_logs
                WHERE log_id = %s AND agent_id = %s
                FOR UPDATE
                """,
                (log_id, agent_id),
            )

            row = cursor.fetchone()

            if row is None:
                conn.rollback()
                return False

            existing = [
                name.strip()
                for name in (row[column] or "").split(",")
                if name.strip()
            ]

            if file_path not in existing:
                existing.append(file_path)

                cursor.execute(
                    f"""
                    UPDATE threat_logs
                    SET {column} = %s
                    WHERE log_id = %s AND agent_id = %s
                    """,
                    (",".join(existing), log_id, agent_id),
                )

            conn.commit()
            return True

        except Exception:
            conn.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()
            conn.close()

    def save_policy(self, level, actions_list):
        self._execute_query('INSERT INTO response_policies (level, actions_json) VALUES (%s, %s) ON CONFLICT (level) DO UPDATE SET actions_json = EXCLUDED.actions_json', (level, json.dumps(actions_list)))

    def get_policy(self, level):
        row = self._execute_query("SELECT actions_json FROM response_policies WHERE level = %s", (level,), fetch="one")
        return json.loads(row['actions_json']) if row else []

    def get_all_policies(self):
        rows = self._execute_query("SELECT level, actions_json FROM response_policies", fetch="all")
        return {r['level']: json.loads(r['actions_json']) for r in rows}

    def add_honeyfile(self, agent_id, file_path, level, category="honey"):
        self._execute_query('INSERT INTO honey_files (agent_id, file_path, file_type, file_category) VALUES (%s, %s, %s, %s)', (agent_id, file_path, level, category))

    def get_all_honeyfiles(self):
        rows = self._execute_query("SELECT file_id as id, file_path as path, file_type as level, agent_id, file_category as category FROM honey_files", fetch="all")
        for r in rows:
            r['name'] = r['path'].replace('\\', '/').split("/")[-1]
            if 'category' not in r or not r['category']: r['category'] = 'honey'
        return rows

    def delete_honeyfile(self, agent_id, file_path):
        row = self._execute_query("SELECT file_id FROM honey_files WHERE agent_id = %s AND file_path = %s", (agent_id, file_path), fetch="one")
        if row:
            self._execute_query("UPDATE threat_logs SET file_id = NULL WHERE file_id = %s", (row['file_id'],))
            self._execute_query("DELETE FROM honey_files WHERE file_id = %s", (row['file_id'],))

    def get_incident_report(self, log_id, admin_user="Admin"):
        log = self._execute_query("SELECT * FROM threat_logs WHERE log_id = %s", (log_id,), fetch="one")
        if not log: return None
        agent = self._execute_query("SELECT * FROM agents WHERE agent_id = %s", (log['agent_id'],), fetch="one")
        base = Path("evidence").resolve()
        def parse_files(value):
            if not value:
                return []

            safe_paths = []

            for raw_name in value.split(","):
                name = raw_name.strip()

                if not name:
                    continue


                # Accept filenames only, not paths.
                if (
                    name in (".", "..")
                    or "/" in name
                    or "\\" in name
                    or ":" in name
                    or "\x00" in name
                ):
                    continue

                candidate = Path(name)

                if candidate.is_absolute() or candidate.name != name:
                    continue
                original_path = base / candidate
                if original_path.is_symlink():
                    continue
                resolved = (base / candidate).resolve()

                if not resolved.is_relative_to(base):
                    continue

                safe_paths.append(str(resolved))

            return safe_paths

        def prepare_report_images(value):
            import base64
            import io
            from PIL import Image, UnidentifiedImageError

            images = []
            max_size = 5 * 1024 * 1024  # 5 MB per image

            for file_path in parse_files(value)[:10]:
                path = Path(file_path)

                try:
                    # Do not follow evidence symlinks.
                    if path.is_symlink() or not path.is_file():
                        continue

                    if path.stat().st_size > max_size:
                        continue

                    with path.open("rb") as f:
                        image_bytes = f.read(max_size + 1)

                    if len(image_bytes) > max_size:
                        continue

                    # Verify actual image content, not just extension.
                    with Image.open(io.BytesIO(image_bytes)) as img:
                        if img.format not in ("PNG", "JPEG"):
                            continue

                        if img.width * img.height > 20_000_000:
                            continue

                        img.verify()
                        mime_type = (
                            "image/png"
                            if img.format == "PNG"
                            else "image/jpeg"
                        )

                    encoded = base64.b64encode(
                        image_bytes
                    ).decode("ascii")

                    images.append({
                        "filename": path.name,
                        "data_uri": f"data:{mime_type};base64,{encoded}",
                    })

                except (OSError, ValueError, UnidentifiedImageError):
                    continue

            return images

        dump_snippets = []
        if log.get('dump_path'):
            dump_files = parse_files(log['dump_path'])
            for d_file in dump_files:
                if os.path.exists(d_file):
                    try:
                        with open(d_file, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read(2001)

                        dump_snippets.append({
                            "filename": os.path.basename(d_file),
                            "content": (
                                content[:2000]
                                + (
                                    "\n... [TRUNCATED FOR PDF REPORT]"
                                    if len(content) > 2000
                                    else ""
                                )
                            ),
                        })
                    except:
                        dump_snippets.append({"filename": os.path.basename(d_file), "content": "[Error reading memory dump]"})

        return {
            "metadata": {"report_id": f"FT-REP-{log_id}", "date_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "examiner": admin_user},
            "host_info": agent or {},
            "incident": log,
            "forensics": {
                "attacker_process": log.get('attacker_process', 'Unknown'),
                "process_list": json.loads(log['process_tree']) if log.get('process_tree') else [],
                "hash_before": log.get('file_hash_before', 'N/A') or 'N/A',
                "hash_after": log.get('file_hash_after', 'N/A') or 'N/A'
            },
            "artifacts": {
                "screenshots": prepare_report_images(log.get('screenshot_path')),
                "camera": prepare_report_images(log.get('camera_path')),
                "audio": (log.get('audio_path') or "").split(','),
                "dump_snippets": dump_snippets
            },
            "ai_report": json.loads(log['ai_context']) if log.get('ai_context') and str(log['ai_context']).strip().startswith('{') else {"executive_summary": log.get('ai_context', 'Analysis pending or not available.')}
        }

    def log_admin_action(self, username, action, details=""):
        self._execute_query(
            "INSERT INTO admin_audit_logs (username, action, details) VALUES (%s, %s, %s)",
            (username, action, details)
        )

    def get_admin_logs(self):
        return self._execute_query("SELECT * FROM admin_audit_logs ORDER BY timestamp DESC", fetch="all")