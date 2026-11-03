"""
views/settings.py
Global Settings - Identity & Access Management (IAM), AI Configuration & System Interface.
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts, Dims
import requests
import threading
import urllib3
import socketio

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class SettingsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        ctk.CTkLabel(self, text="Global Configuration", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY).pack(anchor="w", pady=(0, 20))

        self.tabs = ctk.CTkTabview(self, fg_color=Colors.PANEL_BG, corner_radius=12, segmented_button_selected_color=Colors.ACCENT_BLUE)
        self.tabs.pack(fill="both", expand=True)

        self.tabs.add("Identity & Admins")
        self.tabs.add("AI Intelligence")
        self.tabs.add("Interface & System")

        self.build_admins_tab()
        self.build_ai_tab()
        self.build_system_tab()

        self.sio = socketio.Client(ssl_verify=False)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)


    def _setup_websocket_events(self):
        @self.sio.event
        def connect(): print("[+] Settings View connected to WSS Feed!")
        @self.sio.on('admin_list_updated')
        def on_admins_update(data): self.after(0, self.refresh_admins_list)
        @self.sio.on('ai_settings_updated')
        def on_ai_update(data): self.after(0, self.load_ai_config)

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected:
                    self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except: pass
        threading.Thread(target=_attempt, daemon=True).start()


    def build_admins_tab(self):
        tab = self.tabs.tab("Identity & Admins")

        top_bar = ctk.CTkFrame(tab, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(top_bar, text="Access Control List (ACL)", font=Fonts.H3).pack(side="left")
        self.add_admin_btn = ctk.CTkButton(top_bar, text="+ Add Administrator", fg_color=Colors.ACCENT_BLUE, height=36, command=self.open_add_admin_modal)
        self.add_admin_btn.pack(side="right")

        self.admin_container = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.admin_container.pack(fill="both", expand=True, padx=10, pady=5)
        self.refresh_admins_list()

    def refresh_admins_list(self):
        if not self.winfo_exists(): return
        for child in self.admin_container.winfo_children(): child.destroy()

        def fetch():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.get(f"{SERVER_URL}/api/v1/admin/users", headers={"X-Admin-Token": token}, verify=False, timeout=10)
                if res.status_code == 200:
                    self.after(0, lambda: self.render_admin_cards(res.json().get("data", [])))
            except: pass
        threading.Thread(target=fetch, daemon=True).start()

    def render_admin_cards(self, admins):
        for admin in admins:
            card = ctk.CTkFrame(self.admin_container, fg_color=Colors.SECONDARY_BG, height=60, corner_radius=8)
            card.pack(fill="x", pady=4, padx=5)

            user_lbl = ctk.CTkLabel(card, text=f"👤 {admin['username']}", font=Fonts.H3)
            user_lbl.pack(side="left", padx=20)

            role = admin['role']
            role_color = Colors.ACCENT_BLUE if role == "SuperAdmin" else Colors.SUCCESS
            role_badge = ctk.CTkFrame(card, fg_color=role_color, width=100, height=24, corner_radius=4)
            role_badge.pack(side="left", padx=10)
            role_badge.pack_propagate(False)
            ctk.CTkLabel(role_badge, text=role.upper(), font=Fonts.META, text_color="white").place(relx=0.5, rely=0.5, anchor="center")

            last_login = admin.get('last_login') or "Never logged in"
            ctk.CTkLabel(card, text=f"Last Seen: {last_login}", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=20)

            act_f = ctk.CTkFrame(card, fg_color="transparent")
            act_f.pack(side="right", padx=15)

            ctk.CTkButton(act_f, text="🔑 Reset", width=70, height=28, fg_color=Colors.PANEL_BG, text_color=Colors.TEXT_PRIMARY, command=lambda u=admin['username']: self.open_change_pw_modal(u)).pack(side="left", padx=5)

            if admin['username'] != 'admin':
                ctk.CTkButton(act_f, text="🗑️", width=35, height=28, fg_color="transparent", text_color=Colors.CRITICAL, hover_color=("#F8D7DA", "#331111"), command=lambda u=admin['username']: self.delete_admin_logic(u)).pack(side="left")

    def build_ai_tab(self):
        tab = self.tabs.tab("AI Intelligence")

        container = ctk.CTkFrame(tab, fg_color="transparent")
        container.pack(pady=40, padx=40, fill="both", expand=True)

        ctk.CTkLabel(container, text="Google Gemini Integration", font=Fonts.H2, text_color=Colors.ACCENT_BLUE).pack(anchor="w")
        ctk.CTkLabel(container, text="Provide your API key to enable AI-powered threat analysis and automated forensics.", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(5, 20))

        ctk.CTkLabel(container, text="Gemini API Key", font=Fonts.META).pack(anchor="w")
        self.api_key_entry = ctk.CTkEntry(container, placeholder_text="AIzaSy...", width=500, height=40, show="*")
        self.api_key_entry.pack(anchor="w", pady=(5, 20))

        ctk.CTkLabel(container, text="Active Intelligence Model", font=Fonts.META).pack(anchor="w")
        self.ai_model_var = ctk.StringVar(value="gemini-2.5-flash")
        ctk.CTkOptionMenu(container, values=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"], variable=self.ai_model_var, width=500, height=40).pack(anchor="w", pady=(5, 30))

        self.save_ai_btn = ctk.CTkButton(container, text="💾 Update AI Configuration", width=220, height=40, fg_color=Colors.ACCENT_BLUE, command=self.save_ai_config)
        self.save_ai_btn.pack(anchor="w")

        self.load_ai_config()

    def load_ai_config(self):
        def task():
            try:
                res = requests.get(f"{SERVER_URL}/api/v1/admin/ai_settings", headers={"X-Admin-Token": getattr(self.winfo_toplevel(), 'session_token', '')}, verify=False, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    self.after(0, lambda: [self.api_key_entry.delete(0, 'end'), self.api_key_entry.insert(0, data.get("api_key", "")), self.ai_model_var.set(data.get("model", "gemini-2.5-flash"))])
            except: pass
        threading.Thread(target=task, daemon=True).start()

    def save_ai_config(self):
        self.save_ai_btn.configure(state="disabled", text="Saving...")
        payload = {"api_key": self.api_key_entry.get().strip(), "model": self.ai_model_var.get()}
        def task():
            try:
                res = requests.post(f"{SERVER_URL}/api/v1/admin/ai_settings", json=payload, headers={"X-Admin-Token": getattr(self.winfo_toplevel(), 'session_token', '')}, verify=False, timeout=5)
                if res.status_code == 200: self.after(0, lambda: self.save_ai_btn.configure(text="✅ Config Updated", fg_color=Colors.SUCCESS))
            except: pass
            finally: self.after(2000, lambda: self.save_ai_btn.configure(state="normal", text="💾 Update AI Configuration", fg_color=Colors.ACCENT_BLUE))
        threading.Thread(target=task, daemon=True).start()


    def build_system_tab(self):
        tab = self.tabs.tab("Interface & System")

        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=40, pady=15)
        ctk.CTkLabel(row, text="Dark Mode (Global Override)", font=Fonts.BODY).pack(side="left")

        def toggle_mode():
            if mode_switch.get() == 1:
                ctk.set_appearance_mode("Dark")
            else:
                ctk.set_appearance_mode("Light")

        mode_switch = ctk.CTkSwitch(row, text="", command=toggle_mode)
        mode_switch.pack(side="right")

        if ctk.get_appearance_mode() == "Dark":
            mode_switch.select()

        self.add_simple_switch(tab, "Real-time WSS Streaming", True)

    def add_simple_switch(self, parent, text, default):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(row, text=text, font=Fonts.BODY).pack(side="left")
        s = ctk.CTkSwitch(row, text="")
        s.pack(side="right")
        if default:
            s.select()


    def open_add_admin_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Add New Administrator")
        modal.geometry("450x500")
        modal.configure(fg_color=Colors.PRIMARY_BG)
        modal.attributes("-topmost", True)
        modal.grab_set()

        ctk.CTkLabel(modal, text="Create Security Analyst", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(pady=(30, 20))

        u_entry = ctk.CTkEntry(modal, placeholder_text="Username", width=320, height=45, font=Fonts.BODY, fg_color=Colors.SECONDARY_BG)
        u_entry.pack(pady=10)

        p_entry = ctk.CTkEntry(modal, placeholder_text="Password", width=320, height=45, show="•", font=Fonts.BODY, fg_color=Colors.SECONDARY_BG)
        p_entry.pack(pady=10)

        role_var = ctk.StringVar(value="Analyst")
        ctk.CTkOptionMenu(modal, values=["SuperAdmin", "Analyst", "ForensicExpert"], variable=role_var, width=320, height=45, font=Fonts.BODY, fg_color=Colors.PANEL_BG).pack(pady=10)

        def save():
            token = getattr(self.winfo_toplevel(), 'session_token', '')
            payload = {"username": u_entry.get(), "password": p_entry.get(), "role": role_var.get()}
            try:
                res = requests.post(f"{SERVER_URL}/api/v1/admin/users", json=payload, headers={"X-Admin-Token": token}, verify=False)
                if res.status_code == 201:
                    modal.destroy()
                    self.refresh_admins_list()
            except: pass

        ctk.CTkButton(modal, text="CREATE ACCOUNT", fg_color=Colors.ACCENT_BLUE, hover_color=Colors.HOVER_BLUE, width=320, height=45, font=Fonts.H3, command=save).pack(pady=(30, 10))

    def open_change_pw_modal(self, username):
        modal = ctk.CTkToplevel(self)
        modal.title(f"Reset PW: {username}")
        modal.geometry("450x300")
        modal.configure(fg_color=Colors.PRIMARY_BG)
        modal.attributes("-topmost", True)
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"Update Password: {username}", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(pady=(30, 20))

        new_p = ctk.CTkEntry(modal, placeholder_text="Enter New Password", width=320, height=45, show="•", font=Fonts.BODY, fg_color=Colors.SECONDARY_BG)
        new_p.pack(pady=10)

        def update():
            token = getattr(self.winfo_toplevel(), 'session_token', '')
            payload = {"username": username, "new_password": new_p.get()}
            try:
                res = requests.put(f"{SERVER_URL}/api/v1/admin/users/password", json=payload, headers={"X-Admin-Token": token}, verify=False)
                if res.status_code == 200:
                    modal.destroy()
            except: pass

        ctk.CTkButton(modal, text="UPDATE PASSWORD", fg_color=Colors.WARNING, hover_color=Colors.WARNING, text_color=Colors.TEXT_PRIMARY, width=320, height=45, font=Fonts.H3, command=update).pack(pady=(20, 10))

    def delete_admin_logic(self, username):
        requests.delete(f"{SERVER_URL}/api/v1/admin/users/{username}", headers={"X-Admin-Token": getattr(self.winfo_toplevel(), 'session_token', '')}, verify=False)
        self.refresh_admins_list()