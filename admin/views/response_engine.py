"""
views/response_engine.py
Response Engine View - Enterprise Playbook Configuration (WSS Enabled).
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts, Dims
import requests
import threading
import urllib3
import socketio

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class ResponseEngineView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.switch_vars = {"LOW": {}, "MEDIUM": {}, "HIGH": {}, "CRITICAL": {}}
        self.duration_sliders = {}
        self.duration_labels = {}


        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 25))

        title_f = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_f.pack(side="left")
        ctk.CTkLabel(title_f, text="Response Playbooks", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_f, text="Define automated mitigation strategies based on threat severity levels", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        self.save_btn = ctk.CTkButton(header_frame, text="💾 Deploy Policies", font=Fonts.H3, fg_color=Colors.ACCENT_BLUE, hover_color=Colors.HOVER_BLUE, width=180, height=40, corner_radius=Dims.CORNER_RADIUS, command=self.save_policies)
        self.save_btn.pack(side="right", pady=5)


        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self.grid_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True)
        self.grid_container.grid_columnconfigure((0, 1), weight=1)

        self.all_actions = [
            "Calculate Hash", "Notify Admin", "Log Events", "Take Screenshot",
            "Set Read-Only", "Restrict File Access", "Dump Process Memory",
            "Auto Revert", "Record Camera & Mic"
        ]

        self.create_policy_card(self.grid_container, 0, 0, "LOW", Colors.SUCCESS)
        self.create_policy_card(self.grid_container, 0, 1, "MEDIUM", Colors.WARNING)
        self.create_policy_card(self.grid_container, 1, 0, "HIGH", ("#D9534F", "#e65c00"))
        self.create_policy_card(self.grid_container, 1, 1, "CRITICAL", Colors.CRITICAL)

        self.load_policies()

        self.sio = socketio.Client(ssl_verify=True)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)

    def create_policy_card(self, parent, row, col, title, accent_color):
        card = ctk.CTkFrame(parent, fg_color=Colors.PANEL_BG, corner_radius=12, border_width=1, border_color=Colors.BORDER)
        card.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)

        header = ctk.CTkFrame(card, fg_color=accent_color, height=45, corner_radius=8)
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text=f"🛡️ {title} SEVERITY POLICY", font=("Roboto", 13, "bold"), text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        for action in self.all_actions:
            action_row = ctk.CTkFrame(body, fg_color="transparent", height=32)
            action_row.pack(fill="x", pady=2)
            action_row.pack_propagate(False)

            var = ctk.BooleanVar(value=False)
            self.switch_vars[title][action] = var

            sw = ctk.CTkSwitch(action_row, text=action, font=Fonts.BODY, variable=var, progress_color=accent_color, switch_width=40, switch_height=20)
            sw.pack(side="left")

            if action == "Record Camera & Mic":
                s_frame = ctk.CTkFrame(body, fg_color=Colors.PRIMARY_BG, corner_radius=6)
                s_frame.pack(fill="x", pady=(5, 10), padx=(20, 0))

                lbl = ctk.CTkLabel(s_frame, text="Capture Duration: 10s", font=Fonts.META, text_color=Colors.TEXT_SECONDARY)
                lbl.pack(side="left", padx=10, pady=5)

                slider = ctk.CTkSlider(s_frame, from_=5, to=60, number_of_steps=55, button_color=accent_color, height=16)
                slider.set(10)
                slider.pack(side="right", fill="x", expand=True, padx=10)

                def update_lbl(val, l=lbl): l.configure(text=f"Duration: {int(val)}s")
                slider.configure(command=update_lbl)
                self.duration_sliders[title] = slider
                self.duration_labels[title] = lbl


    def _setup_websocket_events(self):
        @self.sio.event
        def connect(): print("[+] Response Engine connected to WSS Feed!")
        @self.sio.on('policy_updated')
        def on_policy_change(data): self.after(0, self.load_policies)

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected: self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except: pass
        threading.Thread(target=_attempt, daemon=True).start()

    def load_policies(self):
        if not self.winfo_exists(): return
        self.save_btn.configure(state="disabled", text="⏳ Loading...")
        token = getattr(self.winfo_toplevel(), 'session_token', '')
        def task(auth_token):
            try:
                res = requests.get(f"{SERVER_URL}/api/v1/admin/policies", headers={"X-Admin-Token": auth_token}, verify=True, timeout=10)
                if res.status_code == 200:
                    self.after(0, lambda: self.apply_loaded_data(res.json().get("data", {})))
            except: pass
            finally: self.after(0, lambda: self.save_btn.configure(state="normal", text="💾 Deploy Policies"))
        threading.Thread(target=task, args=(token,), daemon=True).start()

    def apply_loaded_data(self, data):
        if not self.winfo_exists(): return
        for db_level, active_actions in data.items():
            if db_level in self.switch_vars:
                for action_name, var in self.switch_vars[db_level].items():
                    var.set(action_name in active_actions)
        mic_dur = data.get('mic_duration', 10)
        for level, slider in self.duration_sliders.items():
            slider.set(float(mic_dur))
            if level in self.duration_labels: self.duration_labels[level].configure(text=f"Duration: {int(mic_dur)}s")

    def save_policies(self):
        if not self.winfo_exists(): return
        self.save_btn.configure(state="disabled", text="🚀 Deploying...")
        payload = {"LOW": [], "MEDIUM": [], "HIGH": [], "CRITICAL": []}
        for level, actions_dict in self.switch_vars.items():
            for action_name, var in actions_dict.items():
                if var.get(): payload[level].append(action_name)
        if "CRITICAL" in self.duration_sliders: payload["mic_duration"] = int(self.duration_sliders["CRITICAL"].get())

        token = getattr(self.winfo_toplevel(), 'session_token', '')
        def task(auth_token):
            try:
                requests.post(f"{SERVER_URL}/api/v1/admin/policies", json=payload, headers={"X-Admin-Token": auth_token}, verify=True, timeout=10)
            except: pass
            finally: self.after(0, lambda: self.save_btn.configure(state="normal", text="💾 Deploy Policies"))
        threading.Thread(target=task, args=(token,), daemon=True).start()