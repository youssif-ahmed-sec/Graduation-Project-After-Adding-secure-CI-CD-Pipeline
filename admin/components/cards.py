"""
components/cards.py
Reusable UI components like Metric Cards and Info Panels.
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts

class MetricCard(ctk.CTkFrame):
    def __init__(self, master, title, value, subtext, color=Colors.ACCENT_BLUE):
        super().__init__(master, fg_color=Colors.PANEL_BG, corner_radius=6, border_width=1, border_color=Colors.BORDER)

        self.grid_columnconfigure(0, weight=1)

        self.lbl_title = ctk.CTkLabel(
            self, text=title.upper(),
            font=Fonts.META, text_color=Colors.TEXT_SECONDARY, anchor="w"
        )
        self.lbl_title.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.lbl_value = ctk.CTkLabel(
            self, text=value,
            font=("Roboto", 28, "bold"), text_color=Colors.TEXT_PRIMARY, anchor="w"
        )
        self.lbl_value.grid(row=1, column=0, padx=15, pady=0, sticky="w")

        self.lbl_sub = ctk.CTkLabel(
            self, text=subtext,
            font=Fonts.META, text_color=color, anchor="w"
        )
        self.lbl_sub.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="w")

class ActivityItem(ctk.CTkFrame):
    def __init__(self, master, time, text, type="info"):
        super().__init__(master, fg_color="transparent")

        color = Colors.ACCENT_BLUE
        if type == "crit": color = Colors.CRITICAL
        elif type == "warn": color = Colors.WARNING

        self.marker = ctk.CTkLabel(self, text="●", text_color=color, font=("Arial", 14))
        self.marker.pack(side="left", padx=(0, 10))

        self.time_lbl = ctk.CTkLabel(self, text=time, font=Fonts.MONO, text_color=Colors.TEXT_SECONDARY, width=80, anchor="w")
        self.time_lbl.pack(side="left", padx=(0, 10))

        self.text_lbl = ctk.CTkLabel(self, text=text, font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY, anchor="w")
        self.text_lbl.pack(side="left", fill="x", expand=True)