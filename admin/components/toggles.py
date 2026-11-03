"""
components/toggles.py
Custom Toggle Switch UI components with descriptions.
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts

class SettingToggle(ctk.CTkFrame):
    def __init__(self, master, title, description, default_value=False, command=None):
        super().__init__(master, fg_color=Colors.PRIMARY_BG, corner_radius=6, border_width=1, border_color=Colors.BORDER)

        self.command = command

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)

        self.title_lbl = ctk.CTkLabel(text_frame, text=title, font=("Roboto", 13, "bold"), text_color=Colors.TEXT_PRIMARY, anchor="w")
        self.title_lbl.pack(fill="x")

        self.desc_lbl = ctk.CTkLabel(text_frame, text=description, font=Fonts.META, text_color=Colors.TEXT_SECONDARY, anchor="w", wraplength=400)
        self.desc_lbl.pack(fill="x")

        self.switch = ctk.CTkSwitch(
            self,
            text="",
            onvalue=True,
            offvalue=False,
            progress_color=Colors.ACCENT_BLUE,
            command=self.on_toggle
        )
        if default_value:
            self.switch.select()

        self.switch.pack(side="right", padx=15)

    def on_toggle(self):
        if self.command:
            self.command(self.switch.get())

    def get(self):
        return self.switch.get()