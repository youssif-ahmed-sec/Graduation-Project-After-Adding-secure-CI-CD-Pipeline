"""
views/forensics.py - Professional EDR Forensics Lab (Polished UI)
"""
import customtkinter as ctk
import json
import requests
import threading
from PIL import Image
import io
import os
from ui.theme import Colors, Fonts, Dims
import urllib3
import webbrowser
from tkinter import filedialog, messagebox
import socketio

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class ForensicsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.all_threats = []
        self.current_alert = None
        self.loaded_images = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=340, fg_color=Colors.SECONDARY_BG, corner_radius=12)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="CASE HISTORY", font=Fonts.H3, text_color=Colors.ACCENT_BLUE).pack(anchor="w", padx=20, pady=(20, 10))

        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="🔍 Filter Case ID, IP...", height=38, corner_radius=8, fg_color=Colors.PANEL_BG, border_color=Colors.BORDER)
        self.search_entry.pack(fill="x", padx=15, pady=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.filter_incidents)

        self.list_container = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True, padx=5, pady=5)

        self.viewer = ctk.CTkFrame(self, fg_color="transparent")
        self.viewer.grid(row=0, column=1, sticky="nsew")

        self.toolbar = ctk.CTkFrame(self.viewer, fg_color="transparent")
        self.toolbar.pack(fill="x", pady=(0, 15))

        self.title_lbl = ctk.CTkLabel(self.toolbar, text="Investigation Lab", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY)
        self.title_lbl.pack(side="left")

        self.isolate_usb_btn = ctk.CTkButton(self.toolbar, text="🔌 Isolate USB", width=120, height=36, fg_color=Colors.CRITICAL, state="disabled", command=lambda: self.toggle_isolation("USB", self.isolate_usb_btn))
        self.isolate_usb_btn.pack(side="right", padx=5)

        self.isolate_net_btn = ctk.CTkButton(self.toolbar, text="🌐 Isolate Network", width=130, height=36, fg_color=Colors.CRITICAL, state="disabled", command=lambda: self.toggle_isolation("NETWORK", self.isolate_net_btn))
        self.isolate_net_btn.pack(side="right", padx=5)

        self.export_btn = ctk.CTkButton(self.toolbar, text="📥 PDF Report", width=110, height=36, fg_color=Colors.SUCCESS, state="disabled", command=self.export_report)
        self.export_btn.pack(side="right", padx=5)

        self.tab_ctrl = ctk.CTkTabview(self.viewer, fg_color=Colors.PANEL_BG, corner_radius=12, segmented_button_selected_color=Colors.ACCENT_BLUE)
        self.tab_ctrl.pack(fill="both", expand=True)

        self.tab_ctrl.add("AI Analysis 🤖")
        self.tab_ctrl.add("Evidence Artifcats")
        self.tab_ctrl.add("Process Tree")
        self.tab_ctrl.add("Metadata (JSON)")

        self.setup_ai_tab()
        self.setup_evidence_tab()
        self.setup_process_table_tab()
        self.setup_json_tab()

        self.load_evidence_list()

        self.sio = socketio.Client(ssl_verify=False)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)

    def _setup_websocket_events(self):
        @self.sio.event
        def connect(): print("[+] Forensics connected to WSS Feed!")
        @self.sio.on('new_threat_alert')
        def on_new_threat(data): self.after(0, self.load_evidence_list)
        @self.sio.on('ai_analysis_ready')
        def on_ai_ready(data):
            ready_log_id = data.get('log_id')
            if self.current_alert and self.current_alert.get('log_id') == ready_log_id:
                self.after(0, lambda: self.refresh_specific_incident(ready_log_id))
            else: self.after(0, self.load_evidence_list)

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected:
                    self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except: pass
        threading.Thread(target=_attempt, daemon=True).start()

    def refresh_specific_incident(self, log_id):
        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.get(f"{SERVER_URL}/api/v1/admin/threats", headers={"X-Admin-Token": token}, verify=False, timeout=10)
                if res.status_code == 200:
                    self.all_threats = res.json().get("data", [])
                    for alert in self.all_threats:
                        if alert.get('log_id') == log_id:
                            self.after(0, lambda d=alert: self.display_forensics(d))
                            break
            except: pass
        threading.Thread(target=task, daemon=True).start()

    def filter_incidents(self, event=None):
        query = self.search_entry.get().lower()
        filtered = [t for t in self.all_threats if query in str(t.get('agent_id')).lower() or query in str(t.get('log_id')).lower()]
        self.render_sidebar_list(filtered)

    def load_evidence_list(self):
        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.get(f"{SERVER_URL}/api/v1/admin/threats", headers={"X-Admin-Token": token}, verify=False, timeout=10)
                if res.status_code == 200:
                    self.all_threats = res.json().get("data", [])
                    if self.winfo_exists(): self.after(0, lambda: self.render_sidebar_list(self.all_threats))
            except: pass
        threading.Thread(target=task, daemon=True).start()

    def render_sidebar_list(self, data):
        for widget in self.list_container.winfo_children(): widget.destroy()
        if not data:
            ctk.CTkLabel(self.list_container, text="No cases recorded.", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(pady=30)
            return

        for alert in data:
            log_id = str(alert.get('log_id', '???')).zfill(4)
            severity = alert.get('severity_level', 'LOW').upper()
            color = Colors.CRITICAL if severity in ["CRITICAL", "HIGH"] else (Colors.WARNING if severity == "MEDIUM" else Colors.SUCCESS)

            btn = ctk.CTkButton(
                self.list_container,
                text=f"CASE #{log_id} | {alert.get('agent_id')}\nLevel: {severity}",
                font=Fonts.META, fg_color=Colors.PANEL_BG, border_width=1, border_color=Colors.BORDER,
                anchor="w", hover_color=Colors.PRIMARY_BG, text_color=color, height=60, corner_radius=8,
                command=lambda d=alert: self.display_forensics(d)
            )
            btn.pack(fill="x", padx=10, pady=5)

    def display_forensics(self, alert_data):
        self.current_alert = alert_data
        self.export_btn.configure(state="normal")

        self.isolate_net_btn.configure(state="normal", text="🌐 Isolate Network", fg_color=Colors.CRITICAL)
        self.isolate_usb_btn.configure(state="normal", text="🔌 Isolate USB", fg_color=Colors.CRITICAL)

        log_id = str(alert_data.get('log_id', '???')).zfill(4)
        self.title_lbl.configure(text=f"Case Study: INC-{log_id}  ➜  {alert_data.get('agent_id')}")

        self.update_ai_view(alert_data)
        self.update_evidence_view(alert_data)
        self.update_process_table(alert_data)

        self.json_textbox.configure(state="normal")
        self.json_textbox.delete("0.0", "end")
        self.json_textbox.insert("0.0", json.dumps(alert_data, indent=4))
        self.json_textbox.configure(state="disabled")

    def setup_ai_tab(self):
        tab = self.tab_ctrl.tab("AI Analysis 🤖")
        self.ai_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.ai_scroll.pack(fill="both", expand=True, padx=20, pady=10)

    def create_ai_card(self, title, content, color):
        card = ctk.CTkFrame(self.ai_scroll, fg_color=Colors.PRIMARY_BG, corner_radius=10, border_width=1, border_color=Colors.BORDER)
        card.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(card, text=title, font=("Roboto", 14, "bold"), text_color=color).pack(anchor="w", padx=20, pady=(15, 5))

        content_str = "\n".join([f"• {item}" for item in content]) if isinstance(content, list) else str(content)
        ctk.CTkLabel(card, text=content_str, font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY, justify="left", wraplength=700).pack(anchor="w", padx=20, pady=(0, 20))

    def update_ai_view(self, alert_data):
        for w in self.ai_scroll.winfo_children(): w.destroy()
        ai_data_raw = alert_data.get('ai_context')

        if not ai_data_raw:
            ctk.CTkLabel(self.ai_scroll, text="AI Expert is analyzing evidence... Please wait.", text_color=Colors.TEXT_SECONDARY, font=Fonts.H3).pack(pady=60)
            return

        try:
            cleaned = str(ai_data_raw).strip()
            ai_json = json.loads(cleaned[cleaned.find('{'):cleaned.rfind('}')+1])
            self.create_ai_card("🚨 Threat Intelligence", ai_json.get("threat_classification", "Unidentified"), Colors.CRITICAL)
            self.create_ai_card("🎯 MITRE Framework Tactics", ai_json.get("mitre_tactics", []), Colors.WARNING)
            self.create_ai_card("📋 Forensic Summary", ai_json.get("executive_summary", "No details."), Colors.ACCENT_BLUE)
            self.create_ai_card("🛡️ Mitigation Strategy", ai_json.get("recommended_containment", "Isolate host immediately."), Colors.SUCCESS)
        except:
            raw_box = ctk.CTkTextbox(self.ai_scroll, height=300, fg_color=Colors.PRIMARY_BG); raw_box.pack(fill="x", pady=10)
            raw_box.insert("0.0", str(ai_data_raw)); raw_box.configure(state="disabled")

    def setup_evidence_tab(self):
        tab = self.tab_ctrl.tab("Evidence Artifcats")
        self.evidence_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.evidence_scroll.pack(fill="both", expand=True, padx=20, pady=20)

    def update_evidence_view(self, alert_data):
        for w in self.evidence_scroll.winfo_children(): w.destroy()
        self.create_evidence_block("System Screenshot", alert_data.get('screenshot_path'), is_image=True)
        if alert_data.get('severity_level', '').upper() == 'CRITICAL':
            self.create_evidence_block("Webcam Intel", alert_data.get('camera_path'), is_image=True)
            self.create_evidence_block("Microphone Audio", alert_data.get('audio_path'), is_image=False, icon="🎙️")

    def create_evidence_block(self, title, filename, is_image=True, icon="🖼️"):
        card = ctk.CTkFrame(self.evidence_scroll, fg_color=Colors.PRIMARY_BG, corner_radius=12)
        card.pack(fill="x", pady=12, padx=5)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(header, text=f"{icon} {title}", font=Fonts.H3, text_color=Colors.ACCENT_BLUE).pack(side="left")

        if not filename or str(filename).lower() == "none":
            ctk.CTkLabel(card, text="Artifact not available for this case.", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(pady=20)
            return

        files = [f.strip() for f in filename.split(',')]
        for f in files:
            if not f: continue
            ctk.CTkButton(header, text="Download", width=85, height=28, fg_color=Colors.PANEL_BG, command=lambda fn=f: self.download_artifact(fn)).pack(side="right")

            if is_image:
                lbl = ctk.CTkLabel(card, text="Loading encrypted evidence...")
                lbl.pack(pady=10)
                self.fetch_and_show_image(f, lbl)
            else:
                audio_f = ctk.CTkFrame(card, fg_color=Colors.SECONDARY_BG, corner_radius=8, height=60)
                audio_f.pack(fill="x", padx=20, pady=15)
                audio_f.pack_propagate(False)
                ctk.CTkLabel(audio_f, text="▶ ılıılıılı Audio Playback", font=("Arial", 16), text_color=Colors.SUCCESS).pack(side="left", padx=15)

    def fetch_and_show_image(self, filename, label_widget):
        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.get(f"{SERVER_URL}/evidence/{filename}", headers={"X-Admin-Token": token}, verify=False, timeout=15)
                if res.status_code == 200:
                    img_data = Image.open(io.BytesIO(res.content))
                    w, h = img_data.size
                    new_w = 680
                    new_h = int(new_w / (w / h))
                    img_tk = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(new_w, new_h))
                    if self.winfo_exists(): self.after(0, lambda: label_widget.configure(text="", image=img_tk) if label_widget.winfo_exists() else None)
            except: pass
        threading.Thread(target=task, daemon=True).start()

    def setup_process_table_tab(self):
        tab = self.tab_ctrl.tab("Process Tree")
        self.dump_frame = ctk.CTkFrame(tab, fg_color=Colors.PANEL_BG, height=60, corner_radius=10)
        self.dump_frame.pack(fill="x", padx=20, pady=20)

        self.proc_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.proc_scroll.pack(fill="both", expand=True, padx=20)

    def update_process_table(self, alert_data):
        for w in self.dump_frame.winfo_children(): w.destroy()
        dump_file = alert_data.get('dump_path')
        if dump_file:
            ctk.CTkLabel(self.dump_frame, text="🧠 Volatile Memory Dump Ready", font=Fonts.BODY, text_color=Colors.SUCCESS).pack(side="left", padx=20)
            ctk.CTkButton(self.dump_frame, text="Download Dump", fg_color=Colors.ACCENT_BLUE, command=lambda: self.download_artifact(dump_file)).pack(side="right", padx=20)

        for w in self.proc_scroll.winfo_children(): w.destroy()
        try:
            tree = json.loads(alert_data.get('process_tree', '[]'))
            for p in tree:
                row = ctk.CTkFrame(self.proc_scroll, fg_color=Colors.PANEL_BG, height=40, corner_radius=6)
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=f"PID: {p.get('pid')}", width=80, font=Fonts.MONO).pack(side="left", padx=10)
                ctk.CTkLabel(row, text=p.get('name'), font=Fonts.H3, text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=10)
                ctk.CTkLabel(row, text=f"User: {p.get('username', 'SYSTEM')}", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(side="right", padx=20)
        except: pass

    def setup_json_tab(self):
        tab = self.tab_ctrl.tab("Metadata (JSON)")
        self.json_textbox = ctk.CTkTextbox(tab, font=Fonts.MONO, fg_color=Colors.PRIMARY_BG, text_color=Colors.SUCCESS)
        self.json_textbox.pack(fill="both", expand=True, padx=15, pady=15)

    def download_artifact(self, filename): webbrowser.open(f"{SERVER_URL}/evidence/{filename}")

    def toggle_isolation(self, iso_type, btn):
        if not self.current_alert: return
        agent_id = self.current_alert.get('agent_id')

        current_text = btn.cget("text")
        is_restoring = "Restore" in current_text

        if iso_type == "NETWORK":
            action_cmd = "RESTORE_NETWORK" if is_restoring else "ISOLATE_NETWORK"
        else:
            action_cmd = "RESTORE_USB" if is_restoring else "ISOLATE_USB"

        btn.configure(state="disabled", text="⏳ Wait...")

        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                headers = {"X-Admin-Token": token, "Content-Type": "application/json"}
                payload = {"agent_id": agent_id, "action": action_cmd}

                res = requests.post(f"{SERVER_URL}/api/v1/admin/emergency_action", json=payload, headers=headers, verify=False, timeout=10)

                if res.status_code == 200:
                    if is_restoring:
                        new_text = "🌐 Isolate Network" if iso_type=="NETWORK" else "🔌 Isolate USB"
                        new_color = Colors.CRITICAL
                    else:
                        new_text = "✅ Restore Network" if iso_type=="NETWORK" else "✅ Restore USB"
                        new_color = Colors.SUCCESS

                    self.after(0, lambda: btn.configure(text=new_text, fg_color=new_color, state="normal"))
                else:
                    self.after(0, lambda: btn.configure(text=current_text, state="normal"))
                    self.after(0, lambda: messagebox.showerror("Action Failed", f"Server returned {res.status_code}"))
            except Exception as e:
                self.after(0, lambda: btn.configure(text=current_text, state="normal"))
                self.after(0, lambda: messagebox.showerror("Connection Error", f"Failed to send command.\nError: {str(e)}"))

        threading.Thread(target=task, daemon=True).start()

    def export_report(self):
        if not self.current_alert: return
        log_id = self.current_alert.get('log_id')
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"FORENSIC_REPORT_{log_id}.pdf")
        if not save_path: return
        self.export_btn.configure(text="⏳ Generating...")
        def task():
            try:
                res = requests.get(f"{SERVER_URL}/api/v1/admin/generate_report/{log_id}", headers={"X-Admin-Token": getattr(self.winfo_toplevel(), 'session_token', '')}, verify=False)
                if res.status_code == 200:
                    with open(save_path, 'wb') as f: f.write(res.content)
                    self.after(0, lambda: messagebox.showinfo("Done", "Forensic Report Saved."))
            except: pass
            finally: self.after(0, lambda: self.export_btn.configure(text="📥 PDF Report"))
        threading.Thread(target=task, daemon=True).start()