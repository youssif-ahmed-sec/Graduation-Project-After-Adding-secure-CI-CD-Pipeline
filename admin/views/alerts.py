"""
views/alerts.py
Security Incidents & Alerts View - Enterprise Forensic UI (WSS Enabled).
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts, Dims
import requests
import threading
import urllib3
import socketio
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class IncidentDetailsDialog(ctk.CTkToplevel):
    def __init__(self, master, log_data):
        super().__init__(master)
        self.title(f"Forensic Report: {log_data.get('log_id', 'Unknown')}")
        self.geometry("750x650")
        self.configure(fg_color=Colors.PRIMARY_BG)
        self.attributes("-topmost", True)
        self.grab_set()

        header = ctk.CTkFrame(self, fg_color=Colors.PANEL_BG, corner_radius=0, height=80)
        header.pack(fill="x")

        title_f = ctk.CTkFrame(header, fg_color="transparent")
        title_f.place(relx=0.05, rely=0.5, anchor="w")
        ctk.CTkLabel(title_f, text="INCIDENT INVESTIGATION", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_f, text=f"Log Reference: #{log_data.get('log_id')}", font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY).pack(anchor="w")

        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        summary = ctk.CTkFrame(content, fg_color=Colors.PANEL_BG, corner_radius=10)
        summary.pack(fill="x", pady=(0, 15))

        self.add_stat(summary, "Timestamp", log_data.get('timestamp', 'N/A'), 0)
        self.add_stat(summary, "Host Identity", log_data.get('agent_id', 'N/A'), 1)
        self.add_stat(summary, "Event Type", log_data.get('action_type', 'N/A'), 2)

        integrity = ctk.CTkFrame(content, fg_color=Colors.PANEL_BG, corner_radius=10)
        integrity.pack(fill="x", pady=15)
        ctk.CTkLabel(integrity, text="🛡️ INTEGRITY ANALYSIS (SHA-256)", font=Fonts.H3, text_color=Colors.ACCENT_BLUE).pack(anchor="w", padx=20, pady=(15, 10))

        h_before = log_data.get('file_hash_before', 'N/A')
        h_after = log_data.get('file_hash_after', 'N/A')
        is_tampered = h_before != h_after and h_after != 'N/A'

        self.add_hash_box(integrity, "Original Baseline Hash", h_before, Colors.TEXT_SECONDARY)
        self.add_hash_box(integrity, "Post-Incident Hash", h_after, Colors.CRITICAL if is_tampered else Colors.SUCCESS)

        status_val = log_data.get('action_status', 'Logged')
        is_healed = "Reverted" in status_val or "Restored" in status_val

        resp_card = ctk.CTkFrame(content, fg_color=("#D1E7DD", "#113322") if is_healed else ("#FFF3CD", "#332211"), corner_radius=10)
        resp_card.pack(fill="x", pady=15)

        status_text = "AUTO-HEALED: FILE INTEGRITY RESTORED ✅" if is_healed else f"STATUS: {status_val.upper()}"
        ctk.CTkLabel(resp_card, text=status_text, font=Fonts.H3, text_color=Colors.SUCCESS if is_healed else Colors.WARNING).pack(pady=20)

        ctk.CTkButton(self, text="Close Case File", fg_color=Colors.ACCENT_BLUE, height=40, command=self.destroy).pack(pady=20)

    def add_stat(self, parent, label, value, idx):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row, text=f"{label}:", font=Fonts.META, text_color=Colors.TEXT_SECONDARY, width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=str(value), font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left")

    def add_hash_box(self, parent, label, value, color):
        ctk.CTkLabel(parent, text=label, font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(5, 0))
        box = ctk.CTkEntry(parent, fg_color=Colors.PRIMARY_BG, border_width=1, border_color=Colors.BORDER, font=Fonts.MONO, text_color=color, height=35)
        box.pack(fill="x", padx=20, pady=(2, 10))
        box.insert(0, value)
        box.configure(state="readonly")

class AlertsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.threats_data = []

        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", pady=(0, 20))

        title_f = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        title_f.pack(side="left")
        ctk.CTkLabel(title_f, text="Security Incidents", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_f, text="Real-time threat detection and forensic log analysis", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w")

        self.sync_btn = ctk.CTkButton(self.top_frame, text="🔄 Refresh Logs", width=130, height=36, corner_radius=Dims.CORNER_RADIUS, fg_color=Colors.PANEL_BG, text_color=Colors.TEXT_PRIMARY, hover_color=Colors.BORDER, command=self.refresh_list)
        self.sync_btn.pack(side="right", pady=5)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self.refresh_list()

        self.sio = socketio.Client(ssl_verify=True)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)

    def _setup_websocket_events(self):
        @self.sio.event
        def connect(): print("[+] Alerts View connected to WSS Feed!")
        @self.sio.on('new_threat_alert')
        def on_new_threat(data): self.after(0, self.refresh_list)
        @self.sio.on('ai_analysis_ready')
        def on_ai_ready(data): self.after(0, self.refresh_list)

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected:
                    self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except: pass
        threading.Thread(target=_attempt, daemon=True).start()

    def refresh_list(self):
        if not self.winfo_exists(): return
        self.sync_btn.configure(state="disabled", text="⏳ Syncing...")
        token = getattr(self.winfo_toplevel(), 'session_token', '')

        def task(auth_token):
            try:
                res = requests.get(f"{SERVER_URL}/api/v1/admin/threats", headers={"X-Admin-Token": auth_token}, verify=True, timeout=10)
                if res.status_code == 200:
                    self.threats_data = res.json().get("data", [])
                    self.after(0, self.render_cards)
            except: pass
            finally: self.after(0, lambda: self.sync_btn.configure(state="normal", text="🔄 Refresh Logs"))
        threading.Thread(target=task, args=(token,), daemon=True).start()

    def render_cards(self):
        if not self.winfo_exists(): return
        for widget in self.scroll.winfo_children(): widget.destroy()
        if not self.threats_data:
            ctk.CTkLabel(self.scroll, text="🛡️ No incidents found. System is secure.", text_color=Colors.SUCCESS, font=Fonts.H3).pack(pady=50)
            return
        for alert in self.threats_data:
            self.create_alert_card(alert)

    def create_alert_card(self, data):
        sev = data.get('severity_level', 'High').upper()
        is_crit = sev in ['CRITICAL', 'HIGH']
        accent = Colors.CRITICAL if is_crit else Colors.WARNING

        card = ctk.CTkFrame(self.scroll, fg_color=Colors.PANEL_BG, corner_radius=10, border_width=1, border_color=Colors.BORDER)
        card.pack(fill="x", pady=8, padx=2)

        ctk.CTkFrame(card, width=5, fg_color=accent, corner_radius=0).pack(side="left", fill="y")

        main = ctk.CTkFrame(card, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=15)

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.pack(fill="x")

        badge = ctk.CTkFrame(top, fg_color=accent, corner_radius=4, width=85, height=24)
        badge.pack(side="left")
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=sev, font=Fonts.META, text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(top, text=data.get('timestamp', ''), font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY).pack(side="right")

        file_name = data.get('file_path', '').split('/')[-1].split('\\')[-1]
        action = data.get('action_type', 'Suspicious Activity')

        ctk.CTkLabel(main, text=f"{action} Detection", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(anchor="w", pady=(10, 0))
        ctk.CTkLabel(main, text=f"Agent: {data.get('agent_id')}  |  File: {file_name}", font=Fonts.BODY, text_color=Colors.ACCENT_BLUE).pack(anchor="w")

        bot = ctk.CTkFrame(main, fg_color="transparent")
        bot.pack(fill="x", pady=(15, 0))

        status = data.get('action_status', 'Logged')
        is_healed = "Revert" in status
        st_color = Colors.SUCCESS if is_healed else Colors.WARNING
        ctk.CTkLabel(bot, text=f"● {status.upper()}", font=Fonts.META, text_color=st_color).pack(side="left")

        ctk.CTkButton(bot, text="🔍 Investigate", width=120, height=32, fg_color=Colors.ACCENT_BLUE, command=lambda d=data: IncidentDetailsDialog(self, d)).pack(side="right")