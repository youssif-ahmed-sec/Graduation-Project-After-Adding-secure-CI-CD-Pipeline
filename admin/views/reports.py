"""
views/reports.py
Reports View - Dynamic Analytics and Reporting hooked to C2 Server (WSS Enabled).
"""
import customtkinter as ctk
import requests
import threading
import urllib3
import socketio
from ui.theme import Colors, Fonts

SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class ReportsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(header_frame, text="Security Reports & Analytics", font=Fonts.H1, text_color=Colors.TEXT_PRIMARY).pack(side="left")

        filters = ctk.CTkFrame(self, fg_color=Colors.PANEL_BG, corner_radius=10, height=60)
        filters.pack(fill="x", pady=(0, 20))
        self.create_filter_ui(filters)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self.load_analytics_data()

        self.sio = socketio.Client(ssl_verify=True)
        self._setup_websocket_events()
        self.after(1000, self._connect_websocket)


    def _setup_websocket_events(self):
        @self.sio.event
        def connect():
            print("[+] Reports View connected to WSS Feed!")

        @self.sio.on('new_threat_alert')
        def on_new_threat(data):
            print(f"[WSS] New incident detected, refreshing analytics charts...")
            self.after(0, self.load_analytics_data)

    def _connect_websocket(self):
        def _attempt():
            try:
                token = getattr(self.winfo_toplevel(), 'session_token', '')
                if token and not self.sio.connected:
                    self.sio.connect(SERVER_URL, auth={'token': token, 'is_admin': True})
            except: pass
        threading.Thread(target=_attempt, daemon=True).start()

    def create_filter_ui(self, parent):
        ctk.CTkLabel(parent, text="Date Range:", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=(20, 10), pady=15)
        ctk.CTkOptionMenu(parent, values=["All Time", "Last 24 Hours", "Last 7 Days"], fg_color=Colors.PRIMARY_BG, button_color=Colors.ACCENT_BLUE).pack(side="left", pady=15)

        self.refresh_btn = ctk.CTkButton(parent, text="🔄 Refresh Data", font=Fonts.BODY, fg_color=Colors.ACCENT_BLUE, command=self.load_analytics_data)
        self.refresh_btn.pack(side="right", padx=20, pady=15)

    def load_analytics_data(self):
        if not self.winfo_exists(): return
        self.refresh_btn.configure(state="disabled", text="⏳ Loading...")

        try:
            token = getattr(self.winfo_toplevel(), 'session_token', '')
        except:
            token = ''

        def task(auth_token):
            try:
                headers = {"X-Admin-Token": auth_token}
                res = requests.get(f"{SERVER_URL}/api/v1/admin/threats", headers=headers, verify=True, timeout=10)

                if res.status_code == 200:
                    threats = res.json().get("data", [])
                    if self.winfo_exists():
                        self.after(0, lambda: self.process_and_render(threats))
            except Exception as e:
                if self.winfo_exists():
                    self.after(0, lambda: self.show_error(str(e)))
            finally:
                if self.winfo_exists():
                    self.after(0, lambda: self.refresh_btn.configure(state="normal", text="🔄 Refresh Data"))

        threading.Thread(target=task, args=(token,), daemon=True).start()

    def show_error(self, error_msg):
        for w in self.scroll.winfo_children(): w.destroy()
        ctk.CTkLabel(self.scroll, text=f"Failed to load data:\n{error_msg}", text_color=Colors.CRITICAL).pack(pady=50)

    def process_and_render(self, threats):
        if not self.winfo_exists(): return
        for w in self.scroll.winfo_children(): w.destroy()

        if not threats:
            ctk.CTkLabel(self.scroll, text="No threats recorded yet. System is secure.", font=Fonts.H2, text_color=Colors.SUCCESS).pack(pady=50)
            return

        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        file_counts = {}
        status_counts = {"Logged Only": 0, "Other": 0}

        for t in threats:
            sev = str(t.get('severity_level', 'LOW')).upper()
            if sev in severity_counts: severity_counts[sev] += 1
            else: severity_counts["LOW"] += 1
            fpath = t.get('file_path', 'Unknown')
            fname = fpath.replace('\\', '/').split('/')[-1]
            file_counts[fname] = file_counts.get(fname, 0) + 1
            status = str(t.get('action_status', '')).lower()
            if "log" in status:
                status_counts["Logged Only"] += 1
            else:
                status_counts["Other"] += 1

        top_files = dict(sorted(file_counts.items(), key=lambda item: item[1], reverse=True)[:5])
        sev_colors = {"CRITICAL": Colors.CRITICAL, "HIGH": ("#D9534F", "#e67e22"), "MEDIUM": Colors.WARNING, "LOW": Colors.SUCCESS}

        self.create_bar_chart_section(self.scroll, "Alerts by Severity", severity_counts, sev_colors)
        self.create_bar_chart_section(self.scroll, "Top Targeted Honeyfiles", top_files, Colors.WARNING)
        self.create_response_actions_chart(self.scroll, status_counts)

    def create_bar_chart_section(self, parent, title, data, color_map_or_str):
        frame = ctk.CTkFrame(parent, fg_color=Colors.PANEL_BG, corner_radius=10)
        frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(frame, text=title, font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=20)
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=(0, 20))
        max_val = max(data.values()) if data and max(data.values()) > 0 else 1
        for k, v in data.items():
            row = ctk.CTkFrame(content, fg_color="transparent"); row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=k, width=150, anchor="e", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=(0, 15))
            bar_container = ctk.CTkFrame(row, fg_color=Colors.PRIMARY_BG, height=15, corner_radius=4); bar_container.pack(side="left", fill="x", expand=True)
            bar_color = color_map_or_str.get(k, Colors.ACCENT_BLUE) if isinstance(color_map_or_str, dict) else color_map_or_str
            progress = ctk.CTkProgressBar(bar_container, progress_color=bar_color, height=15, corner_radius=4, fg_color=Colors.PRIMARY_BG); progress.pack(fill="both")
            progress.set(v / max_val if v > 0 else 0)
            ctk.CTkLabel(row, text=str(v), font=("Roboto", 13, "bold"), text_color=Colors.TEXT_PRIMARY, width=40).pack(side="left", padx=(15, 0))

    def create_response_actions_chart(self, parent, status_counts):
        frame = ctk.CTkFrame(parent, fg_color=Colors.PANEL_BG, corner_radius=10); frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(frame, text="Response Actions Effectiveness", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=20)
        chart_frame = ctk.CTkFrame(frame, fg_color="transparent", height=50); chart_frame.pack(fill="x", padx=20, pady=(0, 20))
        total = sum(status_counts.values())
        if total == 0:
            ctk.CTkLabel(chart_frame, text="No response actions executed yet.").pack(); return
        color_map = {"Logged Only": Colors.WARNING, "Other": Colors.CRITICAL}
        col_idx = 0
        for key, val in status_counts.items():
            if val > 0:
                weight = int((val / total) * 100); chart_frame.grid_columnconfigure(col_idx, weight=weight)
                c = ctk.CTkFrame(chart_frame, fg_color=color_map[key], corner_radius=0, height=40); c.grid(row=0, column=col_idx, sticky="ew")
                col_idx += 1
        legend = ctk.CTkFrame(frame, fg_color="transparent"); legend.pack(padx=20, pady=(0, 20), fill="x")
        for key, val in status_counts.items():
            if val > 0:
                pct = int((val / total) * 100); self.add_legend_item(legend, f"{key} ({pct}%)", color_map[key])

    def add_legend_item(self, parent, text, color):
        item = ctk.CTkFrame(parent, fg_color="transparent"); item.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(item, text="■", font=("Arial", 16), text_color=color).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(item, text=text, font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(side="left")