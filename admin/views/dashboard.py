"""
views/dashboard.py - Real-time Live Feed with Native Windows Notifications & WSS (Enterprise UI)
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts, Dims
import requests
import threading
from winotify import Notification, audio
import urllib3
import socketio

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class DashboardView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.last_threat_count = -1
        self.auto_refresh_interval = 10000

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 25))

        title_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(title_frame, text="Security Overview", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Real-time Endpoint Monitoring & Threat Intelligence", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        buttons_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        buttons_frame.pack(side="right", fill="y", pady=5)

        self.clear_btn = ctk.CTkButton(buttons_frame, text="🗑️ Clear Feed", width=110, height=36, corner_radius=Dims.CORNER_RADIUS, fg_color=Colors.CRITICAL, hover_color="#8B0000", command=self.clear_threats)
        self.clear_btn.pack(side="right", padx=(10, 0))

        self.refresh_btn = ctk.CTkButton(buttons_frame, text="🔄 Sync Now", width=110, height=36, corner_radius=Dims.CORNER_RADIUS, fg_color=Colors.PANEL_BG, text_color=Colors.TEXT_PRIMARY, hover_color=Colors.BORDER, command=self.refresh_dashboard)
        self.refresh_btn.pack(side="right")

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        self.refresh_dashboard()

        self.sio = socketio.Client(ssl_verify=True)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)


    def _setup_websocket_events(self):
        @self.sio.event
        def connect(): print("[+] Admin Dashboard connected to WSS Feed!")
        @self.sio.event
        def disconnect(): print("[-] Admin Dashboard disconnected from WSS Feed.")
        @self.sio.on('agent_status_update')
        def on_agent_status(data): self.after(0, self.refresh_dashboard)
        @self.sio.on('new_threat_alert')
        def on_new_threat(data):
            self.after(0, self.trigger_toast, data.get('agent_id'), data.get('severity_level'), data.get('file_path'))
            self.after(0, self.refresh_dashboard)
        @self.sio.on('ai_analysis_ready')
        def on_ai_ready(data): self.after(0, self.refresh_dashboard)
        @self.sio.on('new_task_result')
        def on_task_result(data): pass

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected:
                    self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except Exception as e: pass
        threading.Thread(target=_attempt, daemon=True).start()

    def refresh_dashboard(self):
        if not self.winfo_exists(): return
        self.refresh_btn.configure(state="disabled", text="Syncing...")
        token = getattr(self.winfo_toplevel(), 'session_token', '')
        def task(auth_token):
            try:
                headers = {"X-Admin-Token": auth_token}
                a_res = requests.get(f"{SERVER_URL}/api/v1/admin/agents", headers=headers, timeout=10, verify=True)
                t_res = requests.get(f"{SERVER_URL}/api/v1/admin/threats", headers=headers, timeout=10, verify=True)
                if a_res.status_code == 200 and t_res.status_code == 200:
                    self.after(0, self._safe_ui_update, a_res.json().get("data", []), t_res.json().get("data", []))
            except: pass
            finally: self.after(0, self._safe_reset_state)
        threading.Thread(target=task, args=(token,), daemon=True).start()

    def _safe_ui_update(self, agents, threats):
        if not self.winfo_exists(): return
        self.check_new_threats(len(threats), threats)
        online_count = len([a for a in agents if a.get('status') == 'Online'])
        self.update_ui(len(agents), online_count, len(threats), threats)

    def _safe_reset_state(self):
        if not self.winfo_exists(): return
        self.refresh_btn.configure(state="normal", text="🔄 Sync Now")

    def clear_threats(self):
        if not self.winfo_exists(): return
        self.clear_btn.configure(state="disabled", text="Clearing...")
        token = getattr(self.winfo_toplevel(), 'session_token', '')
        def task(auth_token):
            try:
                requests.delete(f"{SERVER_URL}/api/v1/admin/threats", headers={"X-Admin-Token": auth_token}, timeout=15, verify=True)
                self.after(0, lambda: setattr(self, 'last_threat_count', 0))
            except: pass
            finally:
                self.after(0, lambda: self.clear_btn.configure(state="normal", text="🗑️ Clear Feed"))
                self.after(0, self.refresh_dashboard)
        threading.Thread(target=task, args=(token,), daemon=True).start()

    def check_new_threats(self, count, threats):
        self.last_threat_count = count

    def trigger_toast(self, agent, severity, path):
        def _show():
            try:
                file_name = path.split('\\')[-1] if '\\' in path else path.split('/')[-1]
                toast = Notification(app_id="FileTrack C2", title=f"🚨 Threat: {severity}", msg=f"Target: {file_name}\nHost: {agent}", duration="short")
                toast.set_audio(audio.Mail, loop=False); toast.show()
            except: pass
        threading.Thread(target=_show, daemon=True).start()

    def update_ui(self, total, online, t_count, logs):
        if not self.winfo_exists(): return
        for widget in self.content_frame.winfo_children(): widget.destroy()

        cards_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 25))

        score_color = Colors.SUCCESS if t_count == 0 else (Colors.WARNING if t_count < 5 else Colors.CRITICAL)

        self.create_card(cards_frame, "Security Score", f"{max(0, 100-(t_count*5))}", "💯", score_color, "Overall Network Health")
        self.create_card(cards_frame, "Active Threats", str(t_count), "🚨", Colors.CRITICAL, "Requires Investigation")
        self.create_card(cards_frame, "Monitoring Agents", f"{online} / {total}", "💻", Colors.SUCCESS, f"{total-online} Offline Endpoints")
        self.create_card(cards_frame, "Deception Network", "Active", "🍯", Colors.WARNING, "Honeyfiles Deployed")

        feed_header = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        feed_header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(feed_header, text="Live Activity Feed", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(feed_header, text=f"Showing {len(logs)} recent events", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(side="right", anchor="s")

        feed_scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent", corner_radius=0)
        feed_scroll.pack(fill="both", expand=True)

        if not logs:
            empty_frame = ctk.CTkFrame(feed_scroll, fg_color=Colors.PANEL_BG, corner_radius=Dims.CORNER_RADIUS)
            empty_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(empty_frame, text="✅ No active threats detected. Network is secure.", text_color=Colors.SUCCESS, font=Fonts.BODY, height=80).pack()
        else:
            for i, log in enumerate(logs):
                sev = log.get('severity_level', 'High').upper()
                is_critical = sev in ['CRITICAL', 'HIGH']

                bg_color = ("#FFEBEB", "#1F1215") if is_critical else (Colors.PANEL_BG if i % 2 == 0 else "transparent")
                border_color = Colors.CRITICAL if is_critical else Colors.PANEL_BG
                border_width = 1 if is_critical else 0

                row = ctk.CTkFrame(feed_scroll, fg_color=bg_color, border_color=border_color, border_width=border_width, corner_radius=8, height=55)
                row.pack(fill="x", pady=4, padx=2)
                row.pack_propagate(False)

                icon_bg = Colors.CRITICAL if is_critical else Colors.WARNING
                icon_char = "🚨" if is_critical else "⚠️"
                icon_box = ctk.CTkFrame(row, fg_color=icon_bg, width=32, height=32, corner_radius=6)
                icon_box.pack(side="left", padx=(10, 15), pady=10)
                icon_box.pack_propagate(False)
                ctk.CTkLabel(icon_box, text=icon_char, font=("Arial", 16)).place(relx=0.5, rely=0.45, anchor="center")

                timestamp = log.get('timestamp', '').split(" ")[-1]
                ctk.CTkLabel(row, text=timestamp, font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY, width=70).pack(side="left")

                file_path = log.get('file_path', '')
                file_name = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1]
                action = log.get('action_type', 'Unknown Action')
                agent = log.get('agent_id', 'Unknown')

                text_frame = ctk.CTkFrame(row, fg_color="transparent")
                text_frame.pack(side="left", fill="x", expand=True, padx=15)

                ctk.CTkLabel(text_frame, text=f"[{agent}]", font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=(0, 10))
                ctk.CTkLabel(text_frame, text=action.upper(), font=Fonts.H3, text_color=Colors.CRITICAL if is_critical else Colors.WARNING).pack(side="left", padx=(0, 10))
                ctk.CTkLabel(text_frame, text=file_name, font=Fonts.BODY, text_color=Colors.ACCENT_BLUE).pack(side="left")

                status = log.get('action_status', 'Logged')
                is_handled = "Blocked" in status or "Isolated" in status
                status_bg = ("#D1E7DD", "#113322") if is_handled else Colors.SECONDARY_BG
                status_text_color = Colors.SUCCESS if is_handled else Colors.TEXT_SECONDARY

                status_badge = ctk.CTkFrame(row, fg_color=status_bg, corner_radius=4, height=24)
                status_badge.pack(side="right", padx=15, pady=15)
                status_badge.pack_propagate(False)
                ctk.CTkLabel(status_badge, text=status, font=Fonts.META, text_color=status_text_color).pack(padx=10, pady=2)
    def create_card(self, parent, title, value, icon, accent_color, subtitle):
        card = ctk.CTkFrame(parent, fg_color=Colors.PANEL_BG, corner_radius=Dims.CORNER_RADIUS)
        card.pack(side="left", fill="both", expand=True, padx=8)

        ctk.CTkFrame(card, height=4, fg_color=accent_color, corner_radius=0).pack(fill="x", side="top")

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkLabel(top_row, text=title, font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(side="left")
        ctk.CTkLabel(top_row, text=icon, font=("Arial", 18)).pack(side="right")

        ctk.CTkLabel(card, text=value, font=("Roboto", 34, "bold"), text_color=Colors.TEXT_PRIMARY).pack(anchor="w", padx=15)

        ctk.CTkLabel(card, text=subtitle, font=("Roboto", 11), text_color=Colors.TEXT_SECONDARY).pack(anchor="w", padx=15, pady=(0, 15))