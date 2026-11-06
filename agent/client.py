import requests, json, socket, platform, uuid, time, os, threading, sys, winreg
import subprocess, hashlib
import psutil
import socketio
import os

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

os.chdir(app_dir)

from modules.watcher import start_watcher
from modules.response_engine import ResponseEngine


def add_to_startup():
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "FileTrack_Agent"

        if getattr(sys, 'frozen', False):
            executable_path = sys.executable
        else:
            python_hidden = sys.executable.replace("python.exe", "pythonw.exe")
            executable_path = f'"{python_hidden}" "{os.path.abspath(__file__)}"'

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, executable_path)
        winreg.CloseKey(key)

        print(f"[+] Persistence established: Agent will run on startup.")
        return True
    except Exception as e:
        print(f"[-] Persistence failed: {e}")
        return False

class FileTrackClient:
    def __init__(self):
        self.config = self.load_config()

        self.base_url = f"https://{self.config['server_ip']}:{self.config['server_port']}/api/v1"
        self.ws_url = f"https://{self.config['server_ip']}:{self.config['server_port']}"

        self.agent_id = self.get_unique_device_id()
        print(f"[*] Assigned Unique Agent ID: {self.agent_id}")
        self.active_observers = {}

        self.engine = ResponseEngine()

        self.sio = socketio.Client(
            ssl_verify=True,
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=2,
            reconnection_delay_max=10
        )
        self.setup_handlers()

    def load_config(self):
        try:
            with open('config.json', 'r') as f: return json.load(f)
        except: sys.exit("[!] config.json missing")

    def list_directory(self, path="."):
        import string
        import ctypes

        try:
            if path == "/" or path == "This PC" or path == "":
                drives_list = []
                bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drives_list.append({
                            "name": f"{letter}:/",
                            "is_dir": True,
                            "size": 0,
                            "abs_path": f"{letter}:/"
                        })
                    bitmask >>= 1
                return {"type": "ls_result", "path": "This PC", "items": drives_list}

            if not os.path.exists(path):
                return {"error": "Not found"}

            items = []
            for i in os.listdir(path):
                full_path = os.path.join(path, i)
                try:
                    is_dir = os.path.isdir(full_path)
                    size = os.path.getsize(full_path) if not is_dir else 0
                    items.append({
                        "name": i,
                        "is_dir": is_dir,
                        "size": size,
                        "abs_path": os.path.abspath(full_path)
                    })
                except: continue

            return {"type": "ls_result", "path": os.path.abspath(path), "items": items}
        except Exception as e:
            return {"error": str(e)}

    def get_running_processes(self):
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username']):
            try:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "username": proc.info['username'] or "N/A"
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {"type": "process_list", "processes": processes}

    def collect_metadata(self):
        ver = platform.version()
        try:
            build_number = int(ver.split('.')[-1])
        except: build_number = 0

        if build_number >= 22000: os_display = "Windows 11"
        elif build_number >= 10240: os_display = "Windows 10"
        else: os_display = f"{platform.system()} {platform.release()}"

        local_ip = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except: pass

        mac = ':'.join(hex(uuid.getnode()).replace('0x', '').upper().zfill(12)[i:i+2] for i in range(0,12,2))

        return {
            "hostname": socket.gethostname(),
            "os_version": os_display,
            "mac_address": mac,
            "ip_address": local_ip
        }

    def get_enrolled_agent_headers(self):
        """
        Return authentication headers for an enrolled agent.

        Never fall back to the legacy shared token.
        """
        credential = os.environ.get("FILETRACK_AGENT_CREDENTIAL")

        if (
            not isinstance(credential, str)
            or not credential
            or credential != credential.strip()
        ):
            raise RuntimeError(
                "Agent credential is missing or invalid"
            )

        return {
            "Authorization": f"Bearer {credential}",
            "X-Agent-ID": self.agent_id,
        }

    def register(self):
        try:
            response = requests.post(
                f"{self.base_url}/register",
                json={
                    "agent_id": self.agent_id,
                    "metadata": self.collect_metadata(),
                },
                headers=self.get_enrolled_agent_headers(),
                verify=True,
                timeout=10,
            )

            return response.status_code == 200

        except (requests.RequestException, RuntimeError):
            return False

    def setup_handlers(self):
        @self.sio.event
        def connect():
            print(f"[+] Connected to Server via Secure WebSockets!")

        @self.sio.event
        def disconnect():
            print("[-] Disconnected from server. Auto-reconnecting...")

        @self.sio.on('force_disconnect')
        def on_force_disconnect(data):
            print("\n[!!!] Admin sent Kill Command. Shutting down securely...")
            with open(".shutdown_signal", "w") as f: f.write("shutdown")
            self.sio.disconnect()
            os._exit(0)

        @self.sio.on('execute_task')
        def on_execute_task(data):
            cmd = data.get("command")
            path = data.get("path", ".")
            task_id = data.get("task_id", "UNKNOWN")
            abs_target_path = os.path.abspath(path)

            print(f"\n[*] Instant Task Received: {cmd} on {abs_target_path}")

            result = None
            status = "success"

            try:
                if cmd == "LS":
                    result = self.list_directory(path)
                elif cmd == "PS":
                    result = self.get_running_processes()

                elif cmd == "ISOLATE_NETWORK":
                    self.engine.isolate_network()
                    result = {"msg": "Network isolated successfully (C2 Allowed)."}
                elif cmd == "RESTORE_NETWORK":
                    self.engine.restore_network()
                    result = {"msg": "Network connection restored."}
                elif cmd == "ISOLATE_USB":
                    self.engine.isolate_usb()
                    result = {"msg": "USB Ports locked down."}
                elif cmd == "RESTORE_USB":
                    self.engine.restore_usb()
                    result = {"msg": "USB Ports unlocked."}

                elif cmd == "START_MONITOR":
                    active_responses = data.get("active_responses", ["verify_sha256", "take_screenshot", "set_read_only", "notify_admin"])
                    self.active_observers[abs_target_path] = start_watcher(abs_target_path, self, active_responses)
                    result = {"msg": f"Watcher activated on {abs_target_path}"}
                elif cmd == "STOP_MONITOR":
                    if abs_target_path in self.active_observers:
                        self.active_observers[abs_target_path].stop()
                        self.active_observers[abs_target_path].join()
                        del self.active_observers[abs_target_path]
                    result = {"msg": f"Watcher deactivated on {abs_target_path}"}
                else:
                    status = "fail"
                    result = {"error": "Unknown command"}
            except Exception as e:
                status = "fail"
                result = {"error": str(e)}
                print(f"[-] Task execution error: {e}")

            self.sio.emit('task_response', {
                "agent_id": self.agent_id,
                "task_id": task_id,
                "status": status,
                "data": result
            })

        @self.sio.on('execute_cmd')
        def on_execute_cmd(data):
            print("[-] SECURITY: Remote shell execution is disabled.")

            self.sio.emit('cmd_result', {
                "agent_id": self.agent_id,
                "output": "[SECURITY] Remote shell execution is disabled."
            })

    def connect_to_server(self):
        while True:
            try:
                headers = self.get_enrolled_agent_headers()

                credential = headers["Authorization"].removeprefix(
                    "Bearer "
                )

                print("[*] Initiating authenticated WebSocket handshake...")

                self.sio.connect(
                    self.ws_url,
                    auth={
                        "agent_id": self.agent_id,
                        "credential": credential,
                    },
                    transports=["websocket"],
                )

                self.sio.wait()

            except Exception:
                # Do not print connection exceptions that might
                # contain authentication details.
                print(
                    "[-] WebSocket connection unavailable. "
                    "Retrying in 5 seconds..."
                )

            time.sleep(5)

    def get_unique_device_id(self):
        try:
            uuid_output = subprocess.check_output(
                ["wmic", "csproduct", "get", "uuid"],
                stderr=subprocess.DEVNULL,
                timeout=10
            )

            uuid_val = uuid_output.decode(
                "utf-8", errors="replace"
            ).splitlines()[1].strip()

            serial_output = subprocess.check_output(
                ["wmic", "baseboard", "get", "serialnumber"],
                stderr=subprocess.DEVNULL,
                timeout=10
            )

            serial_val = serial_output.decode(
                "utf-8", errors="replace"
            ).splitlines()[1].strip()

            combined_id = f"{uuid_val}_{serial_val}"
        except Exception:
            import uuid
            combined_id = str(uuid.getnode())

        short_hash = hashlib.sha256(combined_id.encode()).hexdigest()[:16].upper()
        return f"AGENT_{short_hash}"

if __name__ == "__main__":
    c = FileTrackClient()

    print("[*] Agent started. Checking network...")

    if os.getenv("FILETRACK_AUTO_START", "false").lower() == "true":
        add_to_startup()

    while not c.register():
        print("[-] HTTP Registration failed. Retrying in 5 seconds...")
        time.sleep(5)
    print("[+] HTTP Registration successful.")

    c.connect_to_server()