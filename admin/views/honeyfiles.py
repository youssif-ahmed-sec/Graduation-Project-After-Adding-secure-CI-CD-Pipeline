"""
views/honeyfiles.py
File Security Manager - FIM & Deception (Using the Original Stable Agent 'LS' Logic & Event Triggers)
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts, Dims
import requests
import threading
import os
import time
import urllib3
import socketio

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class HoneyFilesView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.files_data = []
        self.browser_update_callback = None

        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", pady=(0, 20))

        title_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text="File Security Manager", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Manage Integrity Monitoring (FIM) and Deception Networks", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        btn_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        btn_frame.pack(side="right")

        self.add_real_btn = ctk.CTkButton(
            btn_frame, text="🛡️ Monitor Real File", font=Fonts.BODY,
            fg_color=Colors.ACCENT_BLUE, hover_color=Colors.HOVER_BLUE, height=36,
            command=lambda: self.open_deploy_modal(category="real")
        )
        self.add_real_btn.pack(side="left", padx=10)

        self.add_honey_btn = ctk.CTkButton(
            btn_frame, text="🍯 Create Honeyfile", font=Fonts.BODY,
            fg_color=Colors.WARNING, hover_color="#cc9900", text_color="#1a1a1a", height=36,
            command=lambda: self.open_deploy_modal(category="honey")
        )
        self.add_honey_btn.pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self.refresh_list()

        self.sio = socketio.Client(ssl_verify=False)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)

    def _setup_websocket_events(self):
        @self.sio.event
        def connect(): print("[+] Honeyfiles View connected to WSS Feed!")
        @self.sio.on('new_task_result')
        def on_task_result(data):
            task_data = data.get('data', {})
            if task_data.get('type') == 'ls_result':
                if hasattr(self, 'browser_update_callback') and self.browser_update_callback:
                    self.after(0, lambda: self.browser_update_callback(task_data))

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected:
                    self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except: pass
        threading.Thread(target=_attempt, daemon=True).start()

    def refresh_list(self):
        for widget in self.scroll.winfo_children(): widget.destroy()
        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.get(f"{SERVER_URL}/api/v1/admin/honeyfiles", headers={"X-Admin-Token": token}, verify=False, timeout=10)
                if res.status_code == 200:
                    self.files_data = res.json().get("data", [])
                    self.after(0, self.render_cards)
            except: pass
        threading.Thread(target=task, daemon=True).start()

    def render_cards(self):
        if not self.winfo_exists(): return
        if not self.files_data:
            ctk.CTkLabel(self.scroll, text="No files are currently being monitored.", text_color=Colors.TEXT_SECONDARY, font=Fonts.BODY).pack(pady=40)
            return
        for data in self.files_data:
            self.create_card(data)

    def create_card(self, data):
        card = ctk.CTkFrame(self.scroll, fg_color=Colors.PANEL_BG, corner_radius=10, border_width=1, border_color=Colors.BORDER)
        card.pack(fill="x", pady=8, padx=5)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=20, pady=(15, 5))

        category = data.get('category', 'honey')
        file_name = data.get('name', 'Unknown File')

        if category == "real":
            icon, badge_text = "🛡️", "REAL FILE (FIM)"
            badge_bg, badge_fg = ("#D0E2FF", "#004B95"), ("#001D6C", "#FFFFFF")
        else:
            icon, badge_text = "🍯", "DECOY FILE"
            badge_bg, badge_fg = ("#FEF08A", "#854D0E"), ("#713F12", "#FFFFFF")

        ctk.CTkLabel(top_row, text=f"{icon}  {file_name}", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(side="left")

        cat_badge = ctk.CTkFrame(top_row, fg_color=badge_bg, corner_radius=6, height=28)
        cat_badge.pack(side="left", padx=15)
        cat_badge.pack_propagate(False)
        ctk.CTkLabel(cat_badge, text=badge_text, font=Fonts.META, text_color=badge_fg).pack(padx=10, pady=4)

        level = str(data.get('level', 'MEDIUM')).upper()
        sev_color = Colors.CRITICAL if level == "CRITICAL" else (Colors.WARNING if level in ["HIGH", "MEDIUM"] else Colors.SUCCESS)
        sev_badge = ctk.CTkFrame(top_row, fg_color=sev_color, corner_radius=6, width=80, height=28)
        sev_badge.pack(side="right")
        sev_badge.pack_propagate(False)
        ctk.CTkLabel(sev_badge, text=level, font=Fonts.META, text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        bot_row = ctk.CTkFrame(card, fg_color="transparent")
        bot_row.pack(fill="x", padx=20, pady=(5, 15))

        agent_id, path = data.get('agent_id', 'N/A'), data.get('path', 'N/A')
        ctk.CTkLabel(bot_row, text=f"Agent ID: {agent_id}", font=Fonts.MONO, text_color=Colors.ACCENT_BLUE).pack(side="left", padx=(0, 30))
        ctk.CTkLabel(bot_row, text=f"Path: {path}", font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY).pack(side="left")

        ctk.CTkButton(bot_row, text="🗑️ Stop & Remove", width=120, height=30, fg_color="transparent", text_color=Colors.CRITICAL, hover_color=("#F8D7DA", "#331111"), command=lambda a=agent_id, p=path: self.delete_file(a, p)).pack(side="right")

    def open_deploy_modal(self, category):
        modal = ctk.CTkToplevel(self)
        title = "Monitor Real File (FIM)" if category == "real" else "Deploy Honeyfile (Decoy)"
        modal.title(title)
        modal.geometry("550x620")
        modal.configure(fg_color=Colors.PRIMARY_BG)
        modal.attributes("-topmost", True)
        modal.grab_set()

        ctk.CTkLabel(modal, text=title, font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(pady=(30, 20))

        ctk.CTkLabel(modal, text="Target Agent:", font=Fonts.BODY).pack(anchor="w", padx=50)
        agent_var = ctk.StringVar(value="ALL")
        agent_menu = ctk.CTkOptionMenu(modal, variable=agent_var, values=["ALL", "Fetching..."], width=450, height=40, fg_color=Colors.SECONDARY_BG)
        agent_menu.pack(pady=(5, 15))

        ctk.CTkLabel(modal, text="File Path:", font=Fonts.BODY).pack(anchor="w", padx=50)
        path_frame = ctk.CTkFrame(modal, fg_color="transparent")
        path_frame.pack(fill="x", padx=50, pady=(5, 15))

        path_entry = ctk.CTkEntry(path_frame, placeholder_text="Absolute Path on target machine...", height=40, font=Fonts.BODY, fg_color=Colors.SECONDARY_BG)
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(
            path_frame, text="📁 Browse", width=90, height=40, font=Fonts.BODY,
            fg_color=Colors.PANEL_BG, hover_color=Colors.BORDER, text_color=Colors.TEXT_PRIMARY,
            command=lambda: self.open_remote_browser(agent_var.get(), category, path_entry)
        )
        browse_btn.pack(side="right")

        ctk.CTkLabel(modal, text="Trigger Alert On (File Actions):", font=Fonts.BODY).pack(anchor="w", padx=50)
        triggers_frame = ctk.CTkFrame(modal, fg_color="transparent")
        triggers_frame.pack(fill="x", padx=50, pady=(5, 15))

        chk_read = ctk.CTkCheckBox(triggers_frame, text="Open / Copy", width=120)
        chk_edit = ctk.CTkCheckBox(triggers_frame, text="Edit", width=80)
        chk_del  = ctk.CTkCheckBox(triggers_frame, text="Delete / Cut", width=120)
        chk_ren  = ctk.CTkCheckBox(triggers_frame, text="Rename", width=80)

        chk_read.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        chk_edit.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        chk_del.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        chk_ren.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        chk_edit.select()
        chk_del.select()
        chk_ren.select()
        if category == "honey":
            chk_read.select()

        ctk.CTkLabel(modal, text="Response Policy Level:", font=Fonts.BODY).pack(anchor="w", padx=50)
        lvl_var = ctk.StringVar(value="HIGH")
        ctk.CTkOptionMenu(modal, variable=lvl_var, values=["LOW", "MEDIUM", "HIGH", "CRITICAL"], width=450, height=40, fg_color=Colors.SECONDARY_BG).pack(pady=(5, 25))

        def fetch_agents():
            try:
                res = requests.get(f"{SERVER_URL}/api/v1/admin/agents", headers={"X-Admin-Token": getattr(self.winfo_toplevel(), 'session_token', '')}, verify=False)
                if res.status_code == 200:
                    agents = [a['agent_id'] for a in res.json().get('data', [])]
                    modal.after(0, lambda: agent_menu.configure(values=["ALL"] + agents))
            except: pass
        threading.Thread(target=fetch_agents, daemon=True).start()

        def submit():
            from tkinter import messagebox
            btn_submit.configure(state="disabled", text="⏳ Sending...")

            selected_events = []
            if chk_read.get(): selected_events.append("read")
            if chk_edit.get(): selected_events.append("modify")
            if chk_del.get(): selected_events.append("delete")
            if chk_ren.get(): selected_events.append("move")

            payload = {
                "agent_id": agent_var.get(),
                "path": path_entry.get().strip(),
                "level": lvl_var.get(),
                "category": category,
                "events": selected_events
            }

            if not payload["path"]:
                messagebox.showerror("Error", "Please specify a file path.")
                btn_submit.configure(state="normal", text="EXECUTE")
                return

            def task():
                try:
                    token = getattr(self.winfo_toplevel(), 'session_token', '')
                    res = requests.post(f"{SERVER_URL}/api/v1/admin/honeyfiles", json=payload, headers={"X-Admin-Token": token}, verify=False, timeout=5)
                    if res.status_code == 200:
                        self.after(0, modal.destroy)
                        self.after(500, self.refresh_list)
                except:
                    self.after(0, lambda: btn_submit.configure(state="normal", text="Error! Try Again"))
            threading.Thread(target=task, daemon=True).start()

        btn_color, btn_text_color = (Colors.ACCENT_BLUE, "white") if category == "real" else (Colors.WARNING, "#1a1a1a")
        btn_submit = ctk.CTkButton(modal, text="EXECUTE", width=450, height=45, font=Fonts.H3, fg_color=btn_color, text_color=btn_text_color, hover_color=btn_color, command=submit)
        btn_submit.pack(pady=10)

    def open_remote_browser(self, agent_id, category, entry_widget):
        from tkinter import messagebox
        if not agent_id or agent_id == "ALL" or agent_id == "Fetching...":
            messagebox.showwarning("Warning", "Please select a specific agent to browse its files.")
            return

        browser = ctk.CTkToplevel(self)
        browser.title(f"Remote Explorer - {agent_id}")
        browser.geometry("700x550")
        browser.configure(fg_color=Colors.PRIMARY_BG)
        browser.attributes("-topmost", True)
        browser.grab_set()

        current_path_var = ctk.StringVar(value="Fetching...")

        header = ctk.CTkFrame(browser, fg_color=Colors.PANEL_BG, corner_radius=0, height=60)
        header.pack(fill="x")
        nav_frame = ctk.CTkFrame(header, fg_color="transparent")
        nav_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.95)

        ctk.CTkButton(nav_frame, text="⬆ Up", width=60, height=35, fg_color=Colors.SECONDARY_BG, text_color=Colors.TEXT_PRIMARY, hover_color=Colors.BORDER, command=lambda: go_up()).pack(side="left", padx=(0, 10))
        ctk.CTkEntry(nav_frame, textvariable=current_path_var, font=Fonts.BODY, height=35, fg_color=Colors.PRIMARY_BG, border_width=1).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(nav_frame, text="Go ➔", width=60, height=35, fg_color=Colors.ACCENT_BLUE, command=lambda: load_dir(current_path_var.get())).pack(side="left")

        list_frame = ctk.CTkScrollableFrame(browser, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=15, pady=10)

        footer = ctk.CTkFrame(browser, fg_color=Colors.PANEL_BG, height=60, corner_radius=0)

        def go_up():
            path = current_path_var.get()
            if not path or path == "This PC" or path == "/" or len(path) <= 3: load_dir("/")
            else:
                parent = os.path.dirname(path.rstrip('\\/'))
                if not parent or parent == path: load_dir("/")
                else: load_dir(parent)

        def load_dir(target_path):
            if not list_frame.winfo_exists(): return
            for w in list_frame.winfo_children(): w.destroy()
            ctk.CTkLabel(list_frame, text="📡 Querying remote file system...", text_color=Colors.TEXT_SECONDARY).pack(pady=20)

            self.browser_update_callback = update_ui

            def fetch():
                try:
                    token = getattr(self.winfo_toplevel(), 'session_token', '')
                    requests.post(f"{SERVER_URL}/api/v1/admin/set_task", json={"agent_id": agent_id, "task": {"command": "LS", "path": target_path}}, headers={"X-Admin-Token": token}, verify=False, timeout=5)
                    time.sleep(2)
                    res = requests.get(f"{SERVER_URL}/api/v1/admin/get_browse_results/{agent_id}", headers={"X-Admin-Token": token}, verify=False)
                    if res.status_code == 200:
                        data = res.json().get("data", {})
                        if data and browser.winfo_exists(): self.after(0, lambda d=data: update_ui(d))
                except: pass
            threading.Thread(target=fetch, daemon=True).start()

        def update_ui(data):
            if not list_frame.winfo_exists() or not data: return
            self.browser_update_callback = None
            for w in list_frame.winfo_children(): w.destroy()

            path = data.get("path", "")
            current_path_var.set(path)

            items = data.get("items", [])
            items = sorted(items, key=lambda x: (not x['is_dir'], x['name'].lower()))

            for item in items:
                name, is_dir = item['name'], item['is_dir']
                row_f = ctk.CTkFrame(list_frame, fg_color="transparent")
                row_f.pack(fill="x", pady=2)

                icon = "💽" if (path == "This PC" or path == "/") else ("📁" if is_dir else "📄")
                btn = ctk.CTkButton(row_f, text=f"{icon} {name}", font=Fonts.BODY, fg_color="transparent", text_color="#EAB308" if is_dir else Colors.TEXT_PRIMARY, anchor="w")
                btn.pack(side="left", fill="x", expand=True)

                if is_dir:
                    new_path = name if (path == "This PC" or path == "/") else os.path.join(path, name)
                    btn.configure(command=lambda p=new_path: load_dir(p))
                else:
                    if category == "real":
                        ctk.CTkButton(row_f, text="✅ Select File", width=90, fg_color=Colors.SUCCESS, hover_color="#166534", command=lambda p=os.path.join(path, name): select_and_close(p)).pack(side="right", padx=5)

            if category == "honey":
                footer.pack(fill="x", side="bottom")
                for w in footer.winfo_children(): w.destroy()
                ctk.CTkButton(footer, text=f"✅ Select Current Folder: {path}", font=Fonts.H3, height=40, fg_color=Colors.WARNING, text_color="#1a1a1a", hover_color="#cc9900", command=lambda: select_and_close(path)).pack(pady=10, padx=20, fill="x")
            else:
                footer.pack_forget()

        def select_and_close(final_path):
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, final_path.replace("/", "\\"))
            self.browser_update_callback = None
            browser.destroy()

        load_dir("/")
    def delete_file(self, agent_id, path):
        def task():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                res = requests.delete(f"{SERVER_URL}/api/v1/admin/honeyfiles", json={"agent_id": agent_id, "path": path}, headers={"X-Admin-Token": token}, verify=False, timeout=5)
                if res.status_code == 200: self.after(0, self.refresh_list)
            except: pass
        threading.Thread(target=task, daemon=True).start()