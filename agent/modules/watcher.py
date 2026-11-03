import time
import requests
import os
import hashlib
import psutil
import subprocess
import win32file
import win32con
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from modules.response_engine import ResponseEngine

last_alert_time = {}
protected_state = {}
executor = ResponseEngine()

DEBOUNCE_TIME = 5.0

def calculate_file_hash(filepath):
    hasher = hashlib.sha256()
    try:
        if not os.path.exists(filepath): return "Deleted"
        with open(filepath, 'rb') as afile:
            buf = afile.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(65536)
        return hasher.hexdigest()
    except Exception:
        return "Hash unavailable (Lock Active)"

def get_process_context(filepath):
    try:
        abs_target = os.path.abspath(filepath)
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for file in (proc.open_files() or []):
                    if abs_target == os.path.abspath(file.path):
                        pid = proc.pid
                        process_tree = []
                        current_proc = proc
                        while current_proc:
                            try:
                                p_info = {
                                    "pid": current_proc.pid,
                                    "name": current_proc.name(),
                                    "cmdline": " ".join(current_proc.cmdline()) if current_proc.cmdline() else "N/A"
                                }
                                process_tree.append(p_info)
                                current_proc = current_proc.parent()
                            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                                break
                        return pid, process_tree
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                continue
    except Exception as e:
        print(f"[-] Critical Error in process context collection: {e}")
    return None, []

class HoneyFileHandler(FileSystemEventHandler):
    def __init__(self, agent_instance, active_responses, target_file):
        self.agent = agent_instance
        self.active_responses = [str(r).lower().replace("_", " ").strip() for r in active_responses]
        self.target_file = target_file
        self.is_reverting = False

    def on_modified(self, event):
        if not event.is_directory: self.process("EDITED", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory: self.process("DELETED", event.src_path)

    def on_moved(self, event):
        if not event.is_directory: self.process("RENAMED_OR_CUT", event.src_path, dest_path=event.dest_path)

    def on_created(self, event):
        if not event.is_directory: self.process("COPIED_OR_CREATED", event.src_path)

    def process(self, action, path, dest_path=None):
        global last_alert_time, protected_state

        abs_path = os.path.abspath(path)

        if abs_path != self.target_file and action != "RENAMED_OR_CUT": return
        if self.is_reverting: return

        current_time = time.time()

        if abs_path in last_alert_time and (current_time - last_alert_time[abs_path]) < DEBOUNCE_TIME:
            return

        last_alert_time[abs_path] = current_time

        print(f"\n[!] THREAT DETECTED: {action} on {abs_path}")
        if dest_path:
            print(f"   [>] Moved/Renamed to: {dest_path}")

        self.is_reverting = True

        attacker_pid, process_tree = get_process_context(abs_path)
        log_id = f"LOG_{int(current_time)}"

        hash_before = protected_state.get(self.target_file, {}).get("original_hash", "N/A")

        hash_after = "Not Enabled in Policy"
        if "calculate hash" in self.active_responses:
            hash_after = calculate_file_hash(abs_path)
            print(f"   [+] Dynamic Forensics: Captured Attack Hash -> {hash_after}")

        action_status = f"Handled Event: {action}"

        if "auto revert" in self.active_responses and self.target_file in protected_state:
            try:
                subprocess.run(['icacls', self.target_file, '/reset'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if action == "EDITED" or action == "DELETED":
                    with open(self.target_file, 'wb') as f:
                        f.write(protected_state[self.target_file]["original_content"])
                    action_status = "Reverted & Recovered"
                    print("   [!] File successfully recovered to original state.")

                elif action == "RENAMED_OR_CUT":
                    with open(self.target_file, 'wb') as f:
                        f.write(protected_state[self.target_file]["original_content"])
                    if dest_path and os.path.exists(dest_path):
                        os.remove(dest_path)
                    action_status = "Reverted Rename/Cut & Deleted Stolen Copy"
                    print("   [!] File Restored to original path and stolen copy wiped.")

            except Exception as e:
                print(f"   [-] Mitigation Failed: {e}")
                action_status = f"Revert Failed: {e}"
        else:
            action_status = f"Skipped Revert (Not in Policy)"

        filtered_responses = self.active_responses.copy()

        if action == "COPIED_OR_CREATED":
            filtered_responses = [r for r in filtered_responses if r not in ["isolate network", "isolate usb"]]
            print("   [*] Notice: Hard Containment (Network/USB) skipped for non-destructive event (Copy).")

        print(f"[*] Executing Playbook Actions from Dashboard...")
        evidence = executor.execute_dynamic_responses(filtered_responses, self.target_file)

        for ev_type, ev_path in evidence.items():
            if ev_path and os.path.exists(ev_path):
                try:
                    with open(ev_path, 'rb') as f:
                        files = {'file': f}
                        data = {'agent_id': self.agent.agent_id, 'type': ev_type, 'log_id': log_id}
                        upload_url = f"{self.agent.base_url}/upload_artifact"
                        headers = {"Authorization": self.agent.get_secure_headers()["Authorization"]}

                        requests.post(upload_url, files=files, data=data, headers=headers, verify=True, timeout=120)
                except Exception as e:
                    print(f"   [-] Failed to upload artifact {ev_type}: {e}")

        if "log events" in self.active_responses or "notify admin" in self.active_responses:
            alert_payload = {
                "agent_id": self.agent.agent_id,
                "log_id": log_id,
                "action_type": action,
                "file_path": abs_path,
                "hash_before": hash_before,
                "hash_after": hash_after,
                "action_status": action_status,
                "severity_level": "Dynamic Policy Triggered",
                "attacker_pid": attacker_pid,
                "process_tree": process_tree,
                "evidence_paths": evidence,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            try:
                requests.post(f"{self.agent.base_url}/log_threat",
                              json=alert_payload, headers=self.agent.get_secure_headers(), verify=True, timeout=60)
                print("   [+] Threat Log successfully dispatched to centralized C2.")
            except: pass

        time.sleep(1)
        last_alert_time[abs_path] = time.time()
        self.is_reverting = False

def start_watcher(path, agent_instance, active_responses):
    abs_path = os.path.abspath(path)
    target_dir = os.path.dirname(abs_path) if os.path.isfile(path) or "." in os.path.basename(path) else abs_path

    if not os.path.exists(target_dir): os.makedirs(target_dir, exist_ok=True)
    if not os.path.exists(abs_path):
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write("CONFIDENTIAL_FILE_DO_NOT_TOUCH\n")

    try:
        with open(abs_path, 'rb') as f:
            content = f.read()
        protected_state[abs_path] = {
            "original_content": content,
            "original_hash": calculate_file_hash(abs_path),
            "file_handle": None
        }
    except: pass

    try:
        handle = win32file.CreateFile(
            abs_path,
            win32con.GENERIC_READ | win32con.GENERIC_WRITE,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            0,
            None
        )
        protected_state[abs_path]["file_handle"] = handle
        print("   [+] Kernel File Lock Active: Prevention Layer Initialized.")
    except Exception as e:
        print(f"   [-] Could not apply Kernel Lock: {e}")

    event_handler = HoneyFileHandler(agent_instance, active_responses, abs_path)
    observer = Observer()
    observer.schedule(event_handler, target_dir, recursive=False)
    observer.start()
    print(f"[+] Secure Dynamic Watcher active on: {target_dir}")
    return observer