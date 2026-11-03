"""
views/audit_logs.py
Displays the administrative actions and logs (SuperAdmin Only).
"""
import customtkinter as ctk
import requests
import threading
import urllib3
from ui.theme import Colors, Fonts

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class AuditLogsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            self.header_frame,
            text="🛡️ System Audit Logs",
            font=Fonts.H1,
            text_color=Colors.TEXT_PRIMARY
        ).pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            self.header_frame,
            text="🔄 Refresh",
            width=100,
            fg_color=Colors.PANEL_BG,
            hover_color=Colors.BORDER,
            command=self.load_logs_async
        )
        self.refresh_btn.pack(side="right", padx=10)

        self.table_header = ctk.CTkFrame(self, height=40, fg_color=Colors.PANEL_BG, corner_radius=6)
        self.table_header.pack(fill="x", pady=(0, 5))

        cols = [("Timestamp", 180), ("Operator", 150), ("Action", 200), ("Details", 400)]
        for col_name, width in cols:
            lbl = ctk.CTkLabel(self.table_header, text=col_name, font=Fonts.H3, text_color=Colors.ACCENT_BLUE, width=width, anchor="w")
            lbl.pack(side="left", padx=10)


        self.table_body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.table_body.pack(fill="both", expand=True)

        self.load_logs_async()

    def load_logs_async(self):
        for widget in self.table_body.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.table_body, text="Fetching audit logs...", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(pady=20)
        threading.Thread(target=self._fetch_logs, daemon=True).start()

    def _fetch_logs(self):
        try:
            app_window = self.winfo_toplevel()
            token = getattr(app_window, 'session_token', '')

            res = requests.get(
                f"{SERVER_URL}/api/v1/admin/audit_logs",
                headers={"X-Admin-Token": token},
                verify=True,
                timeout=10
            )

            if res.status_code == 200:
                data = res.json().get('data', [])
                self.after(0, lambda: self._render_logs(data))
            else:
                err = res.json().get('error', 'Access Denied')
                self.after(0, lambda: self._render_error(f"❌ {err}"))
        except Exception as e:
            self.after(0, lambda: self._render_error(f"🚫 Network Error: Server unreachable"))

    def _render_logs(self, logs):
        for widget in self.table_body.winfo_children():
            widget.destroy()

        if not logs:
            ctk.CTkLabel(self.table_body, text="No audit logs found.", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(pady=20)
            return

        for i, log in enumerate(logs):
            bg_color = Colors.PANEL_BG if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(self.table_body, fg_color=bg_color, corner_radius=4, height=40)
            row.pack(fill="x", pady=2)

            time_str = str(log['timestamp'])[:19]

            ctk.CTkLabel(row, text=time_str, font=Fonts.BODY, width=180, anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=log['username'], font=Fonts.BODY, width=150, anchor="w", text_color=Colors.WARNING).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=log['action'], font=Fonts.BODY, width=200, anchor="w", text_color=Colors.SUCCESS).pack(side="left", padx=10)

            details_lbl = ctk.CTkLabel(row, text=log['details'], font=Fonts.META, anchor="w", justify="left", text_color=Colors.TEXT_PRIMARY)
            details_lbl.pack(side="left", padx=10, fill="x", expand=True)

    def _render_error(self, msg):
        for widget in self.table_body.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.table_body, text=msg, font=Fonts.H3, text_color=Colors.CRITICAL).pack(pady=20)