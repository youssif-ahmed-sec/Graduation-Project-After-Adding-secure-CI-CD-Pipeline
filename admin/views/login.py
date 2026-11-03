import sys
import customtkinter as ctk
import requests
import threading
import urllib3
import os
import jwt
from PIL import Image, ImageTk
from typing import Callable

SERVER_URL = "https://filetrack-2026.duckdns.org:5000"

class LoginView(ctk.CTkFrame):
    def __init__(self, master, on_login_success: Callable):
        super().__init__(master, fg_color="#0a1121")
        self.on_login_success = on_login_success
        self.pack(fill="both", expand=True)

        self._load_raw_assets()

        self.canvas = ctk.CTkCanvas(self, bg="#0a1121", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.container = ctk.CTkFrame(self.canvas, fg_color="transparent")

        self.bind("<Configure>", self._update_ui_dimensions)
        self._create_widgets()

        self.master.bind("<Return>", lambda e: self.handle_login())

    def _load_raw_assets(self):
        try:
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            assets_path = os.path.join(base_path, "assets")
            self.bg_img_full = Image.open(os.path.join(assets_path, "mesh_background.png"))
            self.shield_img_raw = Image.open(os.path.join(assets_path, "shield_logo.png"))
        except Exception as e:
            print(f"[-] Asset Load Error: {e}")
            self.bg_img_full = None
            self.shield_img_raw = None

    def _update_ui_dimensions(self, event=None):
        width = self.winfo_width()
        height = self.winfo_height()

        self.canvas.delete("all")

        if self.bg_img_full:
            resized_bg = self.bg_img_full.resize((width, height), Image.LANCZOS)
            self.bg_tk = ImageTk.PhotoImage(resized_bg)
            self.canvas.create_image(0, 0, image=self.bg_tk, anchor="nw")

        panel_w, panel_h = 460, 660
        cx, cy = width // 2, height // 2
        x1, y1 = cx - (panel_w // 2), cy - (panel_h // 2)
        x2, y2 = cx + (panel_w // 2), cy + (panel_h // 2)

        self._draw_rounded_rect(x1, y1, x2, y2, radius=20, fill="#0a1121", outline="#184285")

        if self.shield_img_raw:
            shield_resized = self.shield_img_raw.resize((100, 100), Image.LANCZOS)
            self.shield_tk = ImageTk.PhotoImage(shield_resized)
            self.canvas.create_image(cx, y1, image=self.shield_tk, anchor="center")

        self.canvas.create_window(cx, cy + 20, window=self.container, anchor="center")

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        points = [x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y1+radius, x2, y2-radius, x2, y2-radius, x2, y2, x2-radius, y2, x2-radius, y2, x1+radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1]
        return self.canvas.create_polygon(points, **kwargs, smooth=True, width=2)

    def _create_widgets(self):
        ctk.CTkLabel(self.container, text="FILE TRACK", font=("Orbitron", 42, "bold"), text_color="#2781D9").pack(pady=(40, 0))
        ctk.CTkLabel(self.container, text="SECURE INFRASTRUCTURE", font=("Consolas", 12), text_color="#5F738F").pack(pady=(0, 45))

        field_style = {"width": 360, "height": 55, "corner_radius": 10, "fg_color": "#0A1121",
                       "border_color": "#1C273C", "border_width": 1, "text_color": "#FFFFFF", "font": ("Consolas", 15)}

        ctk.CTkLabel(self.container, text="👤 OPERATOR ID", font=("Consolas", 11, "bold"), text_color="#2781D9").pack(anchor="w", padx=10)
        self.user_entry = ctk.CTkEntry(self.container, placeholder_text="e.g. admin_01", **field_style)
        self.user_entry.pack(pady=(2, 20))

        ctk.CTkLabel(self.container, text="🔑 ACCESS KEY", font=("Consolas", 11, "bold"), text_color="#2781D9").pack(anchor="w", padx=10)
        self.pass_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.pass_frame.pack(fill="x")

        self.pass_entry = ctk.CTkEntry(self.pass_frame, placeholder_text="••••••••", show="•", **field_style)
        self.pass_entry.pack(side="left")

        self.show_btn = ctk.CTkButton(self.pass_frame, text="👁️", width=35, height=35, fg_color="transparent",
                                      hover=False, text_color="#2781D9", font=("Arial", 16), command=self._toggle_pass)
        self.show_btn.place(relx=1.0, rely=0.5, anchor="e", x=-10)

        self.status_lbl = ctk.CTkLabel(self.container, text="", font=("Consolas", 12), height=30)
        self.status_lbl.pack(pady=5)

        self.login_btn = ctk.CTkButton(self.container, text="INITIALIZE SESSION", width=360, height=55,
                                       corner_radius=30, fg_color="#196AC6", hover_color="#2A85F2",
                                       font=("Orbitron", 15, "bold"), command=self.handle_login)
        self.login_btn.pack(pady=(10, 0))

        ctk.CTkLabel(self.container, text="🔒 AES-256-GCM | ✅ SOC2 CERTIFIED", font=("Consolas", 10), text_color="#333A49").pack(pady=35)

    def _toggle_pass(self):
        if self.pass_entry.cget("show") == "•":
            self.pass_entry.configure(show="")
            self.show_btn.configure(text="🔒")
        else:
            self.pass_entry.configure(show="•")
            self.show_btn.configure(text="👁️")

    def update_status(self, msg, color):
        if self.winfo_exists():
            self.status_lbl.configure(text=msg, text_color=color)

    def handle_login(self):
        user, pwd = self.user_entry.get().strip(), self.pass_entry.get().strip()
        if not user or not pwd:
            self.update_status("⚠️ IDENTITY REQUIRED", "#FF3333")
            return

        self.login_btn.configure(state="disabled", text="VERIFYING...")

        def _auth():
            try:
                res = requests.post(f"{SERVER_URL}/api/v1/admin/login", json={"username": user, "password": pwd}, verify=True, timeout=12)

                if res.status_code == 200:
                    data = res.json()

                    if data.get("status") == "requires_2fa":
                        self.after(0, lambda: self.update_status("🔐 2FA REQUIRED", "#FFA500"))
                        self.after(0, lambda: self.show_2fa_popup(
                            data.get("temp_token"),
                            data.get("is_first_time"),
                            data.get("totp_secret")
                        ))
                        self.after(0, lambda: self.login_btn.configure(state="normal", text="INITIALIZE SESSION"))
                    else:
                        self.master.session_token = data.get("token")
                        self.master.logged_in_user = user
                        self.after(0, lambda: self.update_status("✅ ACCESS GRANTED", "#00FF7F"))
                        self.after(800, self.on_login_success)
                else:
                    self.after(0, lambda: [self.update_status("❌ AUTH FAILED", "#FF3333"), self.login_btn.configure(state="normal", text="INITIALIZE SESSION")])
            except Exception as e:
                print(f"[-] Login Error: {e}")
                self.after(0, lambda: [self.update_status("🚫 SERVER OFFLINE", "#FF3333"), self.login_btn.configure(state="normal", text="RETRY")])

        threading.Thread(target=_auth, daemon=True).start()

    def show_2fa_popup(self, temp_token, is_first_time, secret_key):
        dialog = ctk.CTkToplevel(self)
        dialog.title("SECURE 2FA VERIFICATION")
        dialog.geometry("400x350")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color="#0a1121")

        if is_first_time:
            ctk.CTkLabel(dialog, text="⚠️ INITIAL SETUP", text_color="#FFA500", font=("Orbitron", 16, "bold")).pack(pady=(20, 5))
            ctk.CTkLabel(dialog, text="Add this key to Google Authenticator:", text_color="#5F738F", font=("Consolas", 12)).pack()
            key_entry = ctk.CTkEntry(dialog, justify="center", width=250, font=("Consolas", 14, "bold"), fg_color="#1C273C", border_color="#2781D9")
            key_entry.insert(0, secret_key)
            key_entry.configure(state="readonly")
            key_entry.pack(pady=10)
        else:
            ctk.CTkLabel(dialog, text="🔐 SECURITY CHECK", text_color="#2781D9", font=("Orbitron", 18, "bold")).pack(pady=(30, 10))

        ctk.CTkLabel(dialog, text="ENTER 6-DIGIT OTP CODE", text_color="#FFFFFF", font=("Consolas", 12)).pack(pady=(10, 5))
        otp_entry = ctk.CTkEntry(dialog, placeholder_text="000000", justify="center", font=("Consolas", 24, "bold"), width=150, height=50, text_color="#00FF7F", fg_color="#1C273C")
        otp_entry.pack(pady=10)

        error_lbl = ctk.CTkLabel(dialog, text="", text_color="#FF3333", font=("Consolas", 12))
        error_lbl.pack(pady=5)

        def verify_code():
            code = otp_entry.get().strip()
            if len(code) == 6 and code.isdigit():
                error_lbl.configure(text="VERIFYING...", text_color="#FFA500")
                def _verify():
                    try:
                        payload = {"temp_token": temp_token, "otp_code": code}
                        res = requests.post(f"{SERVER_URL}/api/v1/admin/verify_2fa", json=payload, verify=True, timeout=10)
                        if res.status_code == 200:
                            real_token = res.json().get("token")
                            self.master.session_token = real_token
                            self.master.logged_in_user = self.user_entry.get().strip()

                            try:
                                decoded = jwt.decode(real_token, options={"verify_signature": False})
                                self.master.logged_in_role = decoded.get('role', 'Analyst')
                            except:
                                self.master.logged_in_role = 'Analyst'

                            self.after(0, dialog.destroy)
                            self.after(0, lambda: self.update_status("✅ IDENTITY VERIFIED", "#00FF7F"))
                            self.after(500, self.on_login_success)
                        else:
                            self.after(0, lambda: error_lbl.configure(text="❌ INVALID CODE", text_color="#FF3333"))
                    except Exception as e:
                        self.after(0, lambda: error_lbl.configure(text="🚫 NETWORK ERROR", text_color="#FF3333"))
                threading.Thread(target=_verify, daemon=True).start()
            else:
                error_lbl.configure(text="CODE MUST BE 6 DIGITS", text_color="#FF3333")

        btn = ctk.CTkButton(dialog, text="AUTHENTICATE", width=200, height=45, font=("Orbitron", 14, "bold"), fg_color="#196AC6", hover_color="#2A85F2", command=verify_code)
        btn.pack(pady=10)

        dialog.bind("<Return>", lambda e: verify_code())