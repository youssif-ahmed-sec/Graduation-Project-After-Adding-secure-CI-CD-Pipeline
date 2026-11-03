from gevent import monkey
monkey.patch_all()

import os
import json
import time
from flask import Flask, request, jsonify, send_from_directory, render_template, make_response
from flask_socketio import SocketIO, emit, join_room, disconnect
from werkzeug.utils import secure_filename
from security import SecurityManager
from db_manager import DBManager
import urllib3
import jwt
import datetime
from functools import wraps
import pdfkit
import sys
import threading
from PIL import Image
import pyotp

from google import genai
from google.genai import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
security = SecurityManager()
db = DBManager()

socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")
connected_agents = {}
authenticated_admin_sids = set()

JWT_SECRET = os.environ.get("JWT_SECRET_KEY")

if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must be configured with at least 32 characters"
    )
EVIDENCE_FOLDER = os.path.join(os.getcwd(), 'evidence')
os.makedirs(EVIDENCE_FOLDER, exist_ok=True)

active_tasks = {}
file_explorer_results = {}

def get_initial_config():
    try:
        saved = db.get_setting("mic_duration")
        return {"mic_duration": int(saved) if saved else 10}
    except:
        return {"mic_duration": 10}

GLOBAL_CONFIG = get_initial_config()


def verify_agent(req):
    h = req.headers.get('Authorization')
    if not h or not h.startswith("Bearer "): return False
    return security.verify_token(h.split(" ")[1])

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Admin-Token')

        if not token:
            return jsonify({"error": "No token"}), 401

        try:
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=["HS256"]
            )

            if (
                payload.get("token_type") != "access"
                or payload.get("mfa_verified") is not True
                or not payload.get("user")
            ):
                return jsonify({"error": "Access denied: MFA required"}), 401

        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid or expired token"}), 401

        return f(*args, **kwargs)

    return decorated

def get_username_from_token(req):
    try:
        token = req.headers.get('X-Admin-Token')
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])['user']
    except:
        return "Unknown"

@socketio.on('connect')
def handle_connect(auth):
    if not auth or 'token' not in auth:
        print("[-] WSS Connection Rejected: Missing Auth Data")
        return False

    if auth.get('is_admin'):
        try:
            payload = jwt.decode(
                auth['token'],
                JWT_SECRET,
                algorithms=["HS256"]
            )

            if (
                payload.get("token_type") != "access"
                or payload.get("mfa_verified") is not True
                or not payload.get("user")
            ):
                return False
            authenticated_admin_sids.add(request.sid)
            join_room('admins_room')
            print("[+] Admin Dashboard connected to Real-Time Feed")
            return True

        except jwt.InvalidTokenError:
            return False

    if 'agent_id' not in auth or not security.verify_token(auth['token']):
        return False

    agent_id = auth['agent_id']
    join_room(agent_id)
    connected_agents[request.sid] = agent_id
    db.update_heartbeat(agent_id)

    socketio.emit('agent_status_update', {'agent_id': agent_id, 'status': 'Online'}, room='admins_room')
    print(f"[+] Agent {agent_id} connected via Secure WebSocket (WSS)")
    return True

@socketio.on('disconnect')
def handle_disconnect():
    agent_id = connected_agents.pop(request.sid, None)
    authenticated_admin_sids.discard(request.sid)
    if agent_id:
        socketio.emit('agent_status_update', {'agent_id': agent_id, 'status': 'Offline'}, room='admins_room')
        print(f"[*] Agent {agent_id} disconnected from WSS")

@socketio.on('task_response')
def handle_task_response(data):
    agent_id = connected_agents.get(request.sid)

    if not agent_id:
        disconnect()
        return

    if not isinstance(data, dict):
        return

    safe_data = {
        **data,
        "agent_id": agent_id
    }

    socketio.emit(
        'new_task_result',
        safe_data,
        room='admins_room'
    )

@socketio.on('send_command_to_agent')
def handle_admin_cmd(data):
    if request.sid not in authenticated_admin_sids:
        disconnect()
        return

    emit(
        'command_rejected',
        {
            'error': 'Remote shell execution is disabled for security.'
        },
        to=request.sid
    )

@socketio.on('cmd_result')
def handle_cmd_result(data):
    agent_id = connected_agents.get(request.sid)

    if not agent_id:
        disconnect()
        return

    if not isinstance(data, dict):
        return

    safe_data = {
        **data,
        "agent_id": agent_id
    }

    emit(
        'update_admin_terminal',
        safe_data,
        room='admins_room'
    )

def analyze_screenshot_task(image_filename, log_id):
    try:
        print(f"[*] Starting Advanced AI analysis for {image_filename} (Log ID: {log_id})", file=sys.stderr)
        image_path = os.path.join(EVIDENCE_FOLDER, image_filename)
        if not os.path.exists(image_path): return

        api_key = db.get_setting("ai_api_key")
        ai_model_name = db.get_setting("ai_model") or "gemini-2.5-flash"

        if not api_key:
            db.update_ai_analysis(log_id, '{"executive_summary": "System Alert: AI API Key not configured."}')
            return

        client = genai.Client(api_key=api_key)
        img = Image.open(image_path)

        prompt = """
        You are an elite Senior Digital Forensics and Incident Response (DFIR) Analyst.
        Analyze this screenshot captured by an EDR agent exactly at the moment a critical security policy was violated.
        Extract IOCs (Indicators of Compromise) and analyze the attacker's behavior based ONLY on what is visible.
        CRITICAL RULES:
        1. Output MUST be strictly in ENGLISH.
        2. Output MUST be a valid JSON object ONLY. Do NOT wrap it in markdown blocks.
        Required JSON Schema:
        {
            "threat_classification": "e.g., Ransomware Execution",
            "mitre_tactics": ["List of 1 or 2 mapped MITRE tactics"],
            "visible_indicators": ["List of suspicious commands/paths"],
            "executive_summary": "A concise, 2-sentence technical summary.",
            "recommended_containment": "One immediate technical action."
        }
        """

        config = types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.8,
            response_mime_type="application/json"
        )

        max_retries = 3
        ai_result = ""

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=ai_model_name,
                    contents=[prompt, img],
                    config=config
                )
                ai_result = response.text.strip()
                break
            except Exception as api_err:
                err_msg = str(api_err)
                if "503" in err_msg or "429" in err_msg:
                    wait_time = 2 ** (attempt + 1)
                    print(f"[-] AI overloaded (503). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})", file=sys.stderr)
                    time.sleep(wait_time)
                    if attempt == max_retries - 1:
                        db.update_ai_analysis(log_id, '{"executive_summary": "AI Analysis Pending: Google API is currently overloaded. Manual review recommended."}')
                        return
                else:
                    raise api_err

        backticks = "`" * 3
        if ai_result.startswith(backticks + "json"): ai_result = ai_result[7:]
        if ai_result.endswith(backticks): ai_result = ai_result[:-3]

        ai_result = ai_result.strip()

        db.update_ai_analysis(log_id, ai_result)
        socketio.emit('ai_analysis_ready', {'log_id': log_id}, room='admins_room')
        print(f"[+] Advanced AI Analysis completed for log_id: {log_id}", file=sys.stderr)

    except Exception as e:
        print(f"[-] AI Analysis Error: {str(e)}", file=sys.stderr)

@app.route('/api/v1/register', methods=['POST'])
def register_agent():
    if not verify_agent(request): return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json()
    metadata = data.get('metadata', {})
    try:
        db.register_agent(
            data.get('agent_id', 'UNKNOWN'),
            metadata.get('hostname', 'Unknown'),
            request.remote_addr,
            metadata.get('mac_address', 'Unknown'),
            metadata.get('os_version', 'Unknown')
        )
        return jsonify({"status": "success"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/v1/heartbeat', methods=['POST'])
def receive_heartbeat():
    if not verify_agent(request): return jsonify({"error": "Unauthorized"}), 403
    agent_id = request.get_json().get('agent_id')
    if agent_id:
        db.update_heartbeat(agent_id)
        task = active_tasks.pop(agent_id, None)
        return jsonify({"status": "success", "task": task}), 200
    return jsonify({"error": "Invalid Data"}), 400

@app.route('/api/v1/report_files', methods=['POST'])
def report_files():
    if not verify_agent(request): return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json()
    if data.get('agent_id') and data.get('data'):
        file_explorer_results[data.get('agent_id')] = data.get('data')
        return jsonify({"status": "success"}), 200
    return jsonify({"error": "Missing data"}), 400

@app.route('/api/v1/log_threat', methods=['POST'])
def log_threat():
    if not verify_agent(request): return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json()

    now = time.time()
    recent_ss, recent_cam, recent_aud, recent_dmp = [], [], [], []
    for fname in os.listdir(EVIDENCE_FOLDER):
        fpath = os.path.join(EVIDENCE_FOLDER, fname)
        if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) < 60:
            fn = fname.lower()
            if fn.startswith('cam_'): recent_cam.append(fname)
            elif fn.startswith('mic_'): recent_aud.append(fname)
            elif fn.startswith('procdump_'): recent_dmp.append(fname)
            elif fn.startswith('ss_'): recent_ss.append(fname)

    db_data = {
        "agent_id": data.get("agent_id"),
        "action_type": data.get("action_type"),
        "file_path": data.get("file_path"),
        "severity_level": data.get("severity_level", "High"),
        "attacker_process": f"PID: {data.get('attacker_pid', 'Unknown')} | {data.get('attacker_name', '')}",
        "process_tree": json.dumps(data.get("process_tree")) if data.get("process_tree") else None,
        "screenshot_path": ",".join(recent_ss) if recent_ss else None,
        "camera_path": ",".join(recent_cam) if recent_cam else None,
        "audio_path": ",".join(recent_aud) if recent_aud else None,
        "dump_path": ",".join(recent_dmp) if recent_dmp else None,
        "file_hash_before": data.get("hash_before"),
        "file_hash_after": data.get("hash_after"),
        "action_status": data.get("action_status", "Logged")
    }

    try:
        log_id = db.log_threat({k: v for k, v in db_data.items() if v is not None})
        db_data['log_id'] = log_id

        socketio.emit('new_threat_alert', db_data, room='admins_room')

        if recent_ss:
            threading.Thread(target=analyze_screenshot_task, args=(recent_ss[0], log_id)).start()
        return jsonify({"status": "success"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/v1/upload_artifact', methods=['POST'])
def upload_artifact():
    if not verify_agent(request): return jsonify({"error": "Unauthorized"}), 403
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400

    file = request.files['file']
    agent_id = request.form.get('agent_id', 'unknown')
    filename = secure_filename(file.filename)
    save_path = os.path.join(EVIDENCE_FOLDER, filename)
    file.save(save_path)

    fn_l = filename.lower()
    a_type = "screenshot"
    if fn_l.startswith("cam_"): a_type = "camera"
    elif fn_l.startswith("mic_"): a_type = "audio"
    elif fn_l.startswith("procdump_"): a_type = "dump"

    db.attach_artifact(agent_id, filename, a_type)
    return jsonify({"message": "Saved", "file": filename}), 200

@app.route('/evidence/<filename>')
def serve_evidence(filename):
    return send_from_directory(EVIDENCE_FOLDER, filename)


@app.route('/api/v1/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    admin_data = db.verify_admin(username, password)
    if not admin_data:
        return jsonify({"error": "Invalid credentials"}), 401

    totp_secret = db.get_admin_totp_secret(username)
    is_first_time = False

    if not totp_secret:
        totp_secret = pyotp.random_base32()
        db.set_admin_totp_secret(username, totp_secret)
        is_first_time = True

    admin_role = admin_data.get('role', 'SuperAdmin') if isinstance(admin_data, dict) else 'SuperAdmin'

    temp_token = jwt.encode({
        'temp_user': username,
        'role': admin_role,
        'token_type': 'mfa_challenge',
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    }, JWT_SECRET, algorithm="HS256")

    return jsonify({
        "status": "requires_2fa",
        "temp_token": temp_token,
        "is_first_time": is_first_time,
        "totp_secret": totp_secret if is_first_time else None
    }), 200

@app.route('/api/v1/admin/verify_2fa', methods=['POST'])
def verify_2fa():
    data = request.get_json()
    temp_token = data.get('temp_token')
    otp_code = data.get('otp_code')

    try:
        decoded = jwt.decode(temp_token, JWT_SECRET, algorithms=["HS256"])
        if decoded.get("token_type") != "mfa_challenge":
            return jsonify({"error": "Invalid MFA challenge token"}), 401
        username = decoded['temp_user']
        role = decoded['role']
    except:
        return jsonify({"error": "Session expired or invalid. Please login again."}), 401

    totp_secret = db.get_admin_totp_secret(username)
    if not totp_secret:
        return jsonify({"error": "2FA Secret not found"}), 400

    totp = pyotp.TOTP(totp_secret)
    if totp.verify(otp_code):
        token = jwt.encode({
            'user': username,
            'role': role,
            'token_type': 'access',
            'mfa_verified': True,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
        }, JWT_SECRET, algorithm="HS256")

        return jsonify({"status": "success", "token": token}), 200
    else:
        return jsonify({"error": "Invalid 2FA Code. Access Denied."}), 401

@app.route('/api/v1/admin/audit_logs', methods=['GET'])
@admin_required
def get_audit_logs():
    token = request.headers.get('X-Admin-Token')
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if decoded.get('role') != 'SuperAdmin':
            return jsonify({"error": "Access Denied: SuperAdmin only"}), 403
        return jsonify({"status": "success", "data": db.get_admin_logs()}), 200
    except:
        return jsonify({"error": "Token decoding failed"}), 401

@app.route('/api/v1/admin/agents', methods=['GET'])
@admin_required
def get_agents():
    db_agents = db.get_all_agents()
    active_wss_agents = list(connected_agents.values())

    for agent in db_agents:
        if agent['agent_id'] in active_wss_agents:
            agent['status'] = 'Online'

    return jsonify({"status": "success", "data": db_agents}), 200

@app.route('/api/v1/admin/threats', methods=['GET'])
@admin_required
def get_threats(): return jsonify({"status": "success", "data": db.get_all_threats()}), 200

@app.route('/api/v1/admin/threats', methods=['DELETE'])
@admin_required
def clear_all_threats():
    try:
        for filename in os.listdir(EVIDENCE_FOLDER):
            file_path = os.path.join(EVIDENCE_FOLDER, filename)
            if os.path.isfile(file_path): os.remove(file_path)
    except: pass
    db.clear_all_threats()

    username = get_username_from_token(request)
    db.log_admin_action(username, "Cleared All Threats", "Deleted all threat logs and forensic evidence")

    return jsonify({"status": "success"}), 200

@app.route('/api/v1/admin/set_task', methods=['POST'])
@admin_required
def set_task():
    data = request.get_json()
    if data.get('agent_id') and data.get('task'):
        socketio.emit('execute_task', data.get('task'), room=data.get('agent_id'))
        active_tasks[data.get('agent_id')] = data.get('task')
        return jsonify({"status": "task_queued"}), 200
    return jsonify({"error": "Missing parameters"}), 400

@app.route('/api/v1/admin/get_browse_results/<agent_id>', methods=['GET'])
@admin_required
def get_browse_results(agent_id):
    result = file_explorer_results.pop(agent_id, None)
    if result: return jsonify({"status": "success", "data": result}), 200
    return jsonify({"status": "pending"}), 202

@app.route('/api/v1/admin/policies', methods=['GET'])
@admin_required
def get_policies():
    res_data = db.get_all_policies()
    res_data['mic_duration'] = GLOBAL_CONFIG['mic_duration']
    return jsonify({"status": "success", "data": res_data}), 200

@app.route('/api/v1/admin/policies', methods=['POST'])
@admin_required
def save_policies():
    data = request.get_json()
    if 'mic_duration' in data:
        GLOBAL_CONFIG['mic_duration'] = int(data['mic_duration'])
        db.update_setting("mic_duration", str(data['mic_duration']))
    for level, actions in data.items():
        if level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]: db.save_policy(level, actions)

    username = get_username_from_token(request)
    db.log_admin_action(username, "Updated Policies", "Modified system response policies and settings")

    return jsonify({"status": "success"}), 200

@app.route('/api/v1/admin/honeyfiles', methods=['POST'])
@admin_required
def add_honeyfile():
    data = request.get_json()
    target = data.get('agent_id')
    file_path = data.get('path')
    level = data.get('level', 'Medium')
    category = data.get('category', 'honey')

    monitored_events = data.get('events', ['modify', 'delete', 'move'])

    ui_actions = db.get_policy(level.upper())
    agent_actions = []

    for act in ui_actions:
        clean_act = str(act).lower().replace("-", " ").strip()
        if "record camera" in clean_act or "record media" in clean_act or "record_media" in clean_act:
            agent_actions.append(f"record camera:{GLOBAL_CONFIG['mic_duration']}")
        else:
            agent_actions.append(clean_act)

    task_payload = {
        "command": "START_MONITOR",
        "path": file_path,
        "category": category,
        "active_responses": agent_actions,
        "monitored_events": monitored_events
    }

    if target == "ALL":
        for agent in db.get_all_agents():
            db.add_honeyfile(agent['agent_id'], file_path, level, category)
            socketio.emit('execute_task', task_payload, room=agent['agent_id'])
            active_tasks[agent['agent_id']] = task_payload
    else:
        db.add_honeyfile(target, file_path, level, category)
        socketio.emit('execute_task', task_payload, room=target)
        active_tasks[target] = task_payload

    username = get_username_from_token(request)
    file_type_str = "Real File (FIM)" if category == "real" else "Honeyfile (Decoy)"
    db.log_admin_action(username, f"Monitored {file_type_str}", f"Target: {target} | Path: {file_path} | Level: {level}")

    return jsonify({"status": "success"}), 200

@app.route('/api/v1/admin/honeyfiles', methods=['GET'])
@admin_required
def get_all_honeyfiles(): return jsonify({"status": "success", "data": db.get_all_honeyfiles()}), 200

@app.route('/api/v1/admin/honeyfiles', methods=['DELETE'])
@admin_required
def delete_honeyfile():
    data = request.get_json()
    agent_id = data.get('agent_id')
    path = data.get('path')
    db.delete_honeyfile(agent_id, path)

    task_payload = {"command": "STOP_MONITOR", "path": path}
    socketio.emit('execute_task', task_payload, room=agent_id)
    active_tasks[agent_id] = task_payload

    username = get_username_from_token(request)
    db.log_admin_action(username, "Deleted File from Monitor", f"Target: {agent_id} | Path: {path}")

    return jsonify({"status": "success"}), 200

@app.route('/api/v1/admin/users', methods=['GET'])
@admin_required
def get_admin_users(): return jsonify({"status": "success", "data": db.get_all_admins()}), 200

@app.route('/api/v1/admin/users', methods=['POST'])
@admin_required
def add_new_admin():
    data = request.get_json()
    if db.add_admin(data.get('username'), data.get('password'), data.get('role')):
        username = get_username_from_token(request)
        db.log_admin_action(username, "Created Admin", f"Username: {data.get('username')} | Role: {data.get('role')}")
        return jsonify({"status": "success"}), 201
    return jsonify({"error": "User exists"}), 400

@app.route('/api/v1/admin/users/password', methods=['PUT'])
@admin_required
def change_admin_password():
    data = request.get_json()
    db.update_admin_password(data.get('username'), data.get('new_password'))

    username = get_username_from_token(request)
    db.log_admin_action(username, "Changed Password", f"Target User: {data.get('username')}")

    return jsonify({"status": "success"}), 200

@app.route('/api/v1/admin/users/<target_username>', methods=['DELETE'])
@admin_required
def delete_admin_user(target_username):
    if target_username == 'admin': return jsonify({"error": "Access Denied"}), 403
    db.delete_admin(target_username)

    username = get_username_from_token(request)
    db.log_admin_action(username, "Deleted Admin", f"Target User: {target_username}")

    return jsonify({"status": "success"}), 200

@app.route('/api/v1/admin/ai_settings', methods=['GET'])
@admin_required
def get_ai_settings():
    return jsonify({
        "api_key": db.get_setting("ai_api_key") or "",
        "model": db.get_setting("ai_model") or "gemini-2.5-flash"
    }), 200

@app.route('/api/v1/admin/ai_settings', methods=['POST'])
@admin_required
def save_ai_settings():
    data = request.get_json()
    db.update_setting("ai_api_key", data.get("api_key", ""))
    db.update_setting("ai_model", data.get("model", "gemini-2.5-flash"))

    username = get_username_from_token(request)
    db.log_admin_action(username, "Updated AI Settings", "Modified Gemini AI Configuration")

    return jsonify({"status": "success"}), 200

@app.route('/api/v1/admin/generate_report/<int:log_id>', methods=['GET'])
@admin_required
def generate_pdf_report(log_id):
    token = request.headers.get('X-Admin-Token')
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        admin_user = decoded.get('user', 'Admin')
    except:
        admin_user = 'System'

    report_data = db.get_incident_report(log_id, admin_user)
    if not report_data: return jsonify({"error": "Threat log not found"}), 404

    html_content = render_template('report.html', data=report_data)
    options = {'page-size': 'A4', 'margin-top': '0.75in', 'margin-right': '0.75in', 'margin-bottom': '0.75in', 'margin-left': '0.75in', 'encoding': "UTF-8", 'enable-local-file-access': True}

    try:
        pdf_bytes = pdfkit.from_string(html_content, False, options=options)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={report_data["metadata"]["report_id"]}.pdf'
        return response
    except Exception as e:
        return jsonify({"error": f"PDF Generation failed: {str(e)}"}), 500
@app.route('/api/v1/admin/emergency_action', methods=['POST'])
@admin_required
def emergency_containment():

    data = request.get_json()
    agent_id = data.get('agent_id')
    action_type = data.get('action')

    valid_actions = ["ISOLATE_NETWORK", "RESTORE_NETWORK", "ISOLATE_USB", "RESTORE_USB"]
    if action_type not in valid_actions:
        return jsonify({"error": "Invalid emergency action"}), 400

    task_payload = {
        "command": action_type,
        "task_id": f"EMERGENCY_{int(time.time())}"
    }

    socketio.emit('execute_task', task_payload, room=agent_id)

    username = get_username_from_token(request)
    db.log_admin_action(username, f"Emergency Action: {action_type}", f"Target: {agent_id}")

    return jsonify({"status": "success", "msg": f"Command {action_type} sent to {agent_id}"}), 200
if __name__ == '__main__':
    print("[*] FileTrack Server starting...")
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False
    )