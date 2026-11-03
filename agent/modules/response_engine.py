import os
import subprocess
import time
import psutil
import cv2
from mss import mss
import sounddevice as sd
import scipy.io.wavfile as wav
import json
import threading
import socket

def containment_enabled():
    return os.environ.get(
        "FILETRACK_ALLOW_CONTAINMENT", "false"
    ).lower() == "true"

class ResponseEngine:
    def __init__(self):
        self.evidence_folder = "evidence"
        self.saved_gateway = None
        if not os.path.exists(self.evidence_folder):
            os.makedirs(self.evidence_folder)

    def take_3_screenshots(self, log_id):
        paths = []
        try:
            with mss() as sct:
                for i in range(1, 4):
                    path = os.path.abspath(os.path.join(self.evidence_folder, f"ss_{log_id}_part{i}.png"))
                    sct.shot(output=path)
                    paths.append(path)
                    time.sleep(1)
            return paths
        except:
            return paths

    def deny_all_access(self, filepath):
        if not containment_enabled():
            print("[-] SECURITY: File access containment is disabled.")
            return False
        try:
            subprocess.run(['icacls', filepath, '/deny', 'Everyone:(F)'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("   [+] Containment Active: Access strictly denied for Everyone.")
            return True
        except:
            return False

    def dump_process_memory(self, log_id):
        try:
            processes = []
            for p in psutil.process_iter(['pid', 'name', 'username']):
                processes.append(p.info)
                if len(processes) > 50: break

            path = os.path.abspath(os.path.join(self.evidence_folder, f"procdump_{log_id}.json"))
            with open(path, 'w') as f: json.dump(processes, f)
            return path
        except:
            return None

    def _safe_record_camera(self, path):
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened(): return
            time.sleep(1)
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(path, frame)
                print(f"   [+] Forensic Evidence: Attacker Image Saved.")
            cap.release()
        except: pass

    def record_camera(self, log_id):
        path = os.path.abspath(os.path.join(self.evidence_folder, f"cam_{log_id}.jpg"))
        t = threading.Thread(target=self._safe_record_camera, args=(path,))
        t.start()
        t.join(timeout=4.0)
        return path if os.path.exists(path) else None

    def _safe_record_mic(self, path, duration):
        try:
            fs = 44100
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
            sd.wait()
            wav.write(path, fs, recording)
            print(f"   [+] Forensic Evidence: Ambient Audio Recorded ({duration}s).")
        except: pass

    def record_mic(self, log_id, duration):
        path = os.path.abspath(os.path.join(self.evidence_folder, f"mic_{log_id}.wav"))
        t = threading.Thread(target=self._safe_record_mic, args=(path, duration))
        t.start()
        t.join(timeout=duration + 2)
        return path if os.path.exists(path) else None

    def get_default_gateway(self):
        try:
            output = subprocess.check_output("route print 0.0.0.0", shell=True, text=True)
            for line in output.split('\n'):
                if "0.0.0.0" in line and "Default" not in line and "127.0.0.1" not in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
        except: pass
        return None

    def isolate_network(self):
        if not containment_enabled():
            print("[-] SECURITY: Containment is disabled.")
            return False

        try:
            subprocess.run('netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound', shell=True, capture_output=True)

            server_ip = socket.gethostbyname("filetrack-2026.duckdns.org")
            subprocess.run(f'netsh advfirewall firewall add rule name="Allow_C2_In" dir=in action=allow remoteip={server_ip}', shell=True, capture_output=True)
            subprocess.run(f'netsh advfirewall firewall add rule name="Allow_C2_Out" dir=out action=allow remoteip={server_ip}', shell=True, capture_output=True)
            subprocess.run('netsh advfirewall firewall add rule name="Allow_DNS" dir=out action=allow protocol=UDP remoteport=53', shell=True, capture_output=True)

            subprocess.run('netsh advfirewall firewall add rule name="Allow_SocketIO" dir=out action=allow protocol=TCP remoteport=5000', shell=True, capture_output=True)

            print(f"   [+] FIREWALL CONTAINMENT: Internet Blocked, C2 Allowed.")
            return True
        except Exception as e:
            print(f"   [-] Isolation Failed: {e}")
            return False

    def restore_network(self):
        if not containment_enabled():
            print("[-] SECURITY: Containment is disabled.")
            return False

        try:
            subprocess.run('netsh advfirewall firewall delete rule name="Allow_C2_In"', shell=True, capture_output=True)
            subprocess.run('netsh advfirewall firewall delete rule name="Allow_C2_Out"', shell=True, capture_output=True)
            subprocess.run('netsh advfirewall firewall delete rule name="Allow_DNS"', shell=True, capture_output=True)
            subprocess.run('netsh advfirewall firewall delete rule name="Allow_SocketIO"', shell=True, capture_output=True)
            subprocess.run('netsh advfirewall set allprofiles firewallpolicy blockinbound,allowoutbound', shell=True, capture_output=True)

            print("   [+] FIREWALL LIFTED: Internet Restored cleanly.")
            return True
        except Exception as e:
            return False

    def isolate_usb(self):
        if not containment_enabled():
            print("[-] SECURITY: Containment is disabled.")
            return False

        try:
            subprocess.run(r'reg add HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR /v Start /t REG_DWORD /d 4 /f', shell=True, capture_output=True)
            subprocess.run('powershell -Command "Get-PnpDevice -InstanceId *USBSTOR* -ErrorAction SilentlyContinue | Disable-PnpDevice -Confirm:$false"', shell=True, capture_output=True)

            subprocess.run('powershell -Command "Get-PnpDevice -Class WPD -ErrorAction SilentlyContinue | Disable-PnpDevice -Confirm:$false"', shell=True, capture_output=True)

            print("   [+] Containment Active: USB & Mobile Devices Disabled.")
            return True
        except Exception as e:
            print(f"   [-] USB Isolation Failed: {e}")
            return False

    def restore_usb(self):
        if not containment_enabled():
            print("[-] SECURITY: Containment is disabled.")
            return False

        try:
            subprocess.run(r'reg add HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR /v Start /t REG_DWORD /d 3 /f', shell=True, capture_output=True)
            subprocess.run('powershell -Command "Get-PnpDevice -InstanceId *USBSTOR* -ErrorAction SilentlyContinue | Enable-PnpDevice -Confirm:$false"', shell=True, capture_output=True)

            subprocess.run('powershell -Command "Get-PnpDevice -Class WPD -ErrorAction SilentlyContinue | Enable-PnpDevice -Confirm:$false"', shell=True, capture_output=True)

            print("   [+] Containment Lifted: All USB & Mobile Ports Unlocked.")
            return True
        except Exception as e:
            print(f"   [-] USB Restore Failed: {e}")
            return False

    def execute_dynamic_responses(self, active_responses, filepath):
        log_id = str(int(time.time()))
        evidence_collected = {}

        duration = 10
        for act in active_responses:
            if "record camera" in act and ":" in act:
                try: duration = int(act.split(":")[-1])
                except: pass

        for action in active_responses:
            if "take screenshot" in action:
                paths = self.take_3_screenshots(log_id)
                for i, p in enumerate(paths):
                    evidence_collected[f'screenshot_{i+1}'] = p

            elif "set read only" in action or "restrict file access" in action:
                self.deny_all_access(filepath)

            elif "dump process memory" in action:
                evidence_collected['process_dump'] = self.dump_process_memory(log_id)

            elif "record camera" in action:
                cam_path = self.record_camera(log_id)
                if cam_path: evidence_collected['camera'] = cam_path

                mic_path = self.record_mic(log_id, duration=duration)
                if mic_path: evidence_collected['mic'] = mic_path

            elif "isolate network" in action:
                self.isolate_network()

            elif "isolate usb" in action:
                self.isolate_usb()

        return evidence_collected