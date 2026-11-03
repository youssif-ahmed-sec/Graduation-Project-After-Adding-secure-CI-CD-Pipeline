"""
components/sidebar.py
Navigation sidebar with Logo and Logout functionality.
"""
import customtkinter as ctk
import os
from PIL import Image
from ui.theme import Colors, Fonts, Dims

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, nav_callback, logout_callback):
        super().__init__(master, width=Dims.SIDEBAR_WIDTH, corner_radius=0, fg_color=Colors.SECONDARY_BG)
        self.nav_callback = nav_callback
        self.logout_callback = logout_callback

        self.logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.logo_frame.pack(fill="x", pady=(20, 20), padx=20)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "shield_logo.png")

        try:
            image = Image.open(logo_path)
            self.logo_img = ctk.CTkImage(light_image=image, dark_image=image, size=(38, 38))
            self.logo_img_lbl = ctk.CTkLabel(self.logo_frame, image=self.logo_img, text="")
            self.logo_img_lbl.pack(side="left", padx=(0, 12))
        except Exception as e:
            print(f"[UI Warning] Could not load logo from {logo_path}: {e}")
            self.logo_img_lbl = ctk.CTkLabel(self.logo_frame, text="🛡️", font=("Arial", 32))
            self.logo_img_lbl.pack(side="left", padx=(0, 10))

        self.text_frame = ctk.CTkFrame(self.logo_frame, fg_color="transparent")
        self.text_frame.pack(side="left", fill="both", expand=True)

        self.logo_lbl = ctk.CTkLabel(
            self.text_frame,
            text="FILE TRACK",
            font=("Roboto", 20, "bold"),
            text_color=Colors.ACCENT_BLUE
        )
        self.logo_lbl.pack(anchor="w")

        self.ver_lbl = ctk.CTkLabel(
            self.text_frame,
            text="ENTERPRISE EDITION v4.6",
            font=Fonts.META,
            text_color=Colors.TEXT_SECONDARY
        )
        self.ver_lbl.pack(anchor="w", pady=(0, 0))

        ctk.CTkFrame(self, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=20, pady=(0, 20))

        current_role = getattr(master.winfo_toplevel(), 'logged_in_role', 'Analyst')

        self.buttons = []
        self.add_nav_button("Dashboard", "dashboard")
        self.add_nav_button("Agents", "agents")
        self.add_nav_button("File Management", "honeyfiles")
        self.add_nav_button("Incidents & Alerts", "alerts")
        self.add_nav_button("Response Engine", "response")
        self.add_nav_button("Forensics", "forensics")
        self.add_nav_button("Reports", "reports")
        self.add_nav_button("Settings", "settings")

        if current_role == 'SuperAdmin':
            self.add_nav_button("Audit Logs", "audit_logs")

        self.bottom_area = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_area.pack(side="bottom", fill="x", padx=10, pady=20)

        self.logout_btn = ctk.CTkButton(
            self.bottom_area,
            text="Logout",
            font=Fonts.BODY,
            fg_color=Colors.PANEL_BG,
            hover_color=Colors.CRITICAL,
            text_color=Colors.TEXT_PRIMARY,
            height=32,
            command=self.logout_callback
        )
        self.logout_btn.pack(fill="x", pady=(0, 10))

        self.user_frame = ctk.CTkFrame(self.bottom_area, fg_color=Colors.PANEL_BG, height=60)
        self.user_frame.pack(fill="x")

        current_user = getattr(master.winfo_toplevel(), 'logged_in_user', 'System Admin')

        ctk.CTkLabel(self.user_frame, text=current_user, font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).place(x=10, y=10)
        ctk.CTkLabel(self.user_frame, text=current_role, font=Fonts.META, text_color=Colors.TEXT_SECONDARY).place(x=10, y=30)
        ctk.CTkLabel(self.user_frame, text="●", font=("Arial", 16), text_color=Colors.SUCCESS).place(x=180, y=15)

    def add_nav_button(self, text, view_name):
        btn = ctk.CTkButton(
            self,
            text=text,
            font=Fonts.BODY,
            height=40,
            fg_color="transparent",
            text_color=Colors.TEXT_SECONDARY,
            hover_color=Colors.PANEL_BG,
            anchor="w",
            command=lambda: self.handle_click(view_name, btn)
        )
        btn.pack(fill="x", padx=10, pady=2)
        self.buttons.append(btn)

        if view_name == "dashboard":
            self.handle_click("dashboard", btn)

    def handle_click(self, view_name, btn_instance):
        for b in self.buttons:
            b.configure(fg_color="transparent", text_color=Colors.TEXT_SECONDARY, border_width=0)

        btn_instance.configure(
            fg_color=Colors.PANEL_BG,
            text_color=Colors.ACCENT_BLUE,
            border_width=1,
            border_color=Colors.BORDER
        )
        self.nav_callback(view_name)