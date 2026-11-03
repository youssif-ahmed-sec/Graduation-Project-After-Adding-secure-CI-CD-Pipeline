"""
views/agents.py
Agent management with live search, deployment, and Terminal Shell (Enterprise Card UI).
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts, Dims
import requests
import threading
import urllib3
import socketio
from views.terminal_window import ChatTerminal

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class AgentsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.real_agents_data = []

        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", pady=(0, 20))

        title_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text="Endpoint Management", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Monitor, control, and investigate connected agents", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        self.refresh_btn = ctk.CTkButton(self.top_frame, text="🔄 Refresh Data", width=120, height=36, corner_radius=Dims.CORNER_RADIUS, fg_color=Colors.PANEL_BG, text_color=Colors.TEXT_PRIMARY, hover_color=Colors.BORDER, command=self.fetch_agents_from_server)
        self.refresh_btn.pack(side="right", pady=5)

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self.refresh_table)
        self.search = ctk.CTkEntry(self, placeholder_text="🔍 Search by hostname, IP, MAC or ID...", height=40, corner_radius=Dims.CORNER_RADIUS, fg_color=Colors.PANEL_BG, border_color=Colors.BORDER, border_width=1, font=Fonts.BODY, textvariable=self.search_var)
        self.search.pack(fill="x", pady=(0, 15))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self.fetch_agents_from_server()

        self.sio = socketio.Client(ssl_verify=True)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)


    def _setup_websocket_events(self):
        @self.sio.event
        def connect(): print("[+] Agents View connected to WSS Feed!")

        @self.sio.on('agent_status_update')
        def on_agent_status(data):
            self.after(0, self.fetch_agents_from_server)

        @self.sio.on('new_task_result')
        def on_task_result(data):
            pass

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected:
                    self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except: pass
        threading.Thread(target=_attempt, daemon=True).start()

    def fetch_agents_from_server(self):
        if not self.winfo_exists(): return
        self.refresh_btn.configure(text="⏳ Loading...", state="disabled")
        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.get(f"{SERVER_URL}/api/v1/admin/agents", headers={"X-Admin-Token": token}, verify=True, timeout=10)
                if res.status_code == 200:
                    self.real_agents_data = res.json().get("data", [])
            except: pass
            finally:
                if self.winfo_exists():
                    self.after(0, self.refresh_table)
                    self.after(0, lambda: self.refresh_btn.configure(text="🔄 Refresh Data", state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def refresh_table(self, *args):
        for widget in self.scroll.winfo_children(): widget.destroy()
        query = self.search_var.get().lower()
        filtered = [a for a in self.real_agents_data if query in str(a.get('agent_id','')).lower() or query in str(a.get('hostname','')).lower() or query in str(a.get('ip_address','')) or query in str(a.get('mac_address','')).lower()]

        if not filtered:
            ctk.CTkLabel(self.scroll, text="No agents found matching your search.", text_color=Colors.TEXT_SECONDARY, font=Fonts.BODY).pack(pady=40)
            return

        for agent in filtered:
            self.create_card(agent)


    def create_card(self, data):
        card = ctk.CTkFrame(self.scroll, fg_color=Colors.PANEL_BG, corner_radius=10, border_width=1, border_color=Colors.BORDER)
        card.pack(fill="x", pady=8, padx=5)


        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=20, pady=(15, 5))

        os_name = str(data.get('os_details', 'Unknown')).lower()
        os_icon = "🪟" if "win" in os_name else ("🐧" if "lin" in os_name or "ubun" in os_name else ("🍏" if "mac" in os_name or "darwin" in os_name else "💻"))
        hostname = data.get('hostname', 'Unknown Host')

        ctk.CTkLabel(top_row, text=f"{os_icon}  {hostname}", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(side="left")

        status = data.get('status', 'Offline')
        is_online = status == "Online"
        badge_bg = ("#D1E7DD", "#113322") if is_online else ("#F8D7DA", "#331111")
        badge_color = Colors.SUCCESS if is_online else Colors.CRITICAL

        status_frame = ctk.CTkFrame(top_row, fg_color=badge_bg, corner_radius=6, width=85, height=28)
        status_frame.pack(side="right")
        status_frame.pack_propagate(False)
        ctk.CTkLabel(status_frame, text=f"● {status}", font=Fonts.BODY, text_color=badge_color).place(relx=0.5, rely=0.5, anchor="center")

        mid_row = ctk.CTkFrame(card, fg_color="transparent")
        mid_row.pack(fill="x", padx=20, pady=(5, 10))

        agent_id = data.get('agent_id', 'N/A')
        ip = data.get('ip_address', 'N/A')
        mac = data.get('mac_address', 'N/A')
        time_str = str(data.get('last_heartbeat', 'N/A')).split(".")[0]

        ctk.CTkLabel(mid_row, text=f"ID: {agent_id}", font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=(0, 25))
        ctk.CTkLabel(mid_row, text=f"IP: {ip}", font=Fonts.MONO, text_color=Colors.ACCENT_BLUE).pack(side="left", padx=(0, 25))
        ctk.CTkLabel(mid_row, text=f"MAC: {mac}", font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=(0, 25))
        ctk.CTkLabel(mid_row, text=f"Seen: {time_str}", font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY).pack(side="left")

        bot_row = ctk.CTkFrame(card, fg_color="transparent")
        bot_row.pack(fill="x", padx=20, pady=(5, 15))

        btn_style = {"height": 32, "corner_radius": 6, "font": Fonts.BODY}

        ctk.CTkButton(bot_row, text="⌨️ Remote Shell", width=120, fg_color=Colors.SECONDARY_BG, hover_color=Colors.BORDER, text_color=Colors.TEXT_PRIMARY, command=lambda a=agent_id: ChatTerminal(self, a, self.sio), **btn_style).pack(side="left")
        ctk.CTkButton(bot_row, text="🛑 Terminate Agent", width=130, fg_color="transparent", text_color=Colors.CRITICAL, border_width=1, border_color=Colors.CRITICAL, hover_color="#331111", command=lambda a=agent_id: self.send_shutdown_task(a), **btn_style).pack(side="right")

    def send_shutdown_task(self, agent_id):
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm Remote Kill", f"Are you sure you want to FORCE SHUTDOWN {agent_id}?"): return
        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.post(f"{SERVER_URL}/api/v1/admin/set_task", json={"agent_id": agent_id, "task": {"command": "SHUTDOWN_AGENT"}}, headers={"X-Admin-Token": token}, verify=True, timeout=15)
                if res.status_code == 200 and self.winfo_exists():
                    self.after(0, lambda: messagebox.showinfo("Sent", f"Shutdown queued for {agent_id}."))
            except: pass
        threading.Thread(target=task, daemon=True).start()