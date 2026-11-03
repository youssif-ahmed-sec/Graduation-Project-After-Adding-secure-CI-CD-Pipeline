import customtkinter as ctk
from ui.theme import Colors
from components.sidebar import Sidebar
from views.login import LoginView
from views.dashboard import DashboardView
from views.agents import AgentsView
from views.honeyfiles import HoneyFilesView
from views.alerts import AlertsView
from views.settings import SettingsView
from views.forensics import ForensicsView
from views.reports import ReportsView
from views.response_engine import ResponseEngineView
from views.audit_logs import AuditLogsView

import gc
import socketio
import sys
import ctypes
import os
from PIL import Image, ImageTk

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("File Track | Enterprise Security Console")
        self.geometry("1280x800")
        self.minsize(1024, 768)

        try:
            myappid = 'filetrack.enterprise.console.v1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass

        def get_asset_path(relative_path):
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base_path, relative_path)

        ico_path = get_asset_path(os.path.join("assets", "shield_logo.ico"))
        png_path = get_asset_path(os.path.join("assets", "shield_logo.png"))

        try:
            self.iconbitmap(ico_path)
            icon_img = ImageTk.PhotoImage(Image.open(png_path))
            self.wm_iconphoto(True, icon_img)
            self.iconphoto(True, icon_img)
        except:
            pass

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("dark-blue")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_view = None
        self.sidebar = None
        self.content_area = None

        self.protocol("WM_DELETE_WINDOW", self.graceful_exit)

        self.show_login()

    def show_login(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=1)
        self.login_view = LoginView(self, self.start_application)

    def start_application(self):
        self.login_view.destroy()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self.content_area = ctk.CTkFrame(self, fg_color=Colors.PRIMARY_BG, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")

        self.sidebar = Sidebar(self, self.navigate, self.handle_logout)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.navigate("dashboard")

    def handle_logout(self):
        self.show_login()

    def navigate(self, view_name):
        if self.current_view:
            self.current_view.destroy()
            self.current_view = None

        for widget in self.content_area.winfo_children():
            widget.destroy()

        if view_name == "dashboard":
            self.current_view = DashboardView(self.content_area)
        elif view_name == "agents":
            self.current_view = AgentsView(self.content_area)
        elif view_name == "honeyfiles":
            self.current_view = HoneyFilesView(self.content_area)
        elif view_name == "alerts":
            self.current_view = AlertsView(self.content_area)
        elif view_name == "response":
            self.current_view = ResponseEngineView(self.content_area)
        elif view_name == "forensics":
            self.current_view = ForensicsView(self.content_area)
        elif view_name == "reports":
            self.current_view = ReportsView(self.content_area)
        elif view_name == "audit_logs":
            self.current_view = AuditLogsView(self.content_area)
        elif view_name == "settings":
            self.current_view = SettingsView(self.content_area)

        if self.current_view:
            self.current_view.pack(fill="both", expand=True, padx=30, pady=30)

    def reload_ui(self):
        target_view = "settings"

        if self.sidebar:
            self.sidebar.destroy()
        if self.content_area:
            self.content_area.destroy()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self.content_area = ctk.CTkFrame(self, fg_color=Colors.PRIMARY_BG, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")

        self.sidebar = Sidebar(self, self.navigate, self.handle_logout)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.navigate(target_view)

    def graceful_exit(self):
        try:
            for obj in gc.get_objects():
                if isinstance(obj, socketio.Client):
                    try:
                        if obj.connected:
                            obj.disconnect()
                    except:
                        pass
        except:
            pass
        finally:
            self.destroy()
            os._exit(0)