"""
views/incident_details.py
The Modal/Dialog for deep inspection of an alert.
Updated with Forensic Visuals (Mock Screenshot, Integirty Check).
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui_stubs import stubs

class IncidentDetailsDialog(ctk.CTkToplevel):
    def __init__(self, master, incident_data):
        super().__init__(master)
        self.title(f"Incident Investigation - {incident_data['id']}")
        self.geometry("900x650")
        self.configure(fg_color=Colors.PRIMARY_BG)
        self.resizable(False, False)
        self.data = incident_data

        self.transient(master)

        header = ctk.CTkFrame(self, fg_color=Colors.SECONDARY_BG, height=60, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(header, text=f"{incident_data['event']} on {incident_data['target']}", font=Fonts.H2, text_color=Colors.CRITICAL).pack(side="left", padx=20, pady=15)

        self.action_btn = ctk.CTkButton(header, text="CLOSE INCIDENT", width=120, fg_color=Colors.SUCCESS, command=self.resolve)
        self.action_btn.pack(side="right", padx=20)

        self.tabs = ctk.CTkTabview(self, fg_color=Colors.PANEL_BG, text_color=Colors.TEXT_PRIMARY, segmented_button_selected_color=Colors.ACCENT_BLUE)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=20)

        self.tabs.add("Summary")
        self.tabs.add("Evidence & Forensics")
        self.tabs.add("Process Tree")

        self.build_summary(self.tabs.tab("Summary"), incident_data)

        self.build_forensics(self.tabs.tab("Evidence & Forensics"))

        self.build_processes(self.tabs.tab("Process Tree"))

    def build_summary(self, parent, data):
        parent.grid_columnconfigure(1, weight=1)
        labels = [
            ("Incident ID", data['id']),
            ("Timestamp", data['time']),
            ("Affected Host", data['target']),
            ("Severity", data['severity']),
            ("Detection Engine", "HoneyFile Integrity Monitor (HIM)"),
            ("Status", "Process Suspended (Auto-Block Active)")
        ]

        for i, (label, val) in enumerate(labels):
            ctk.CTkLabel(parent, text=label, font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY, anchor="w").grid(row=i, column=0, padx=20, pady=10, sticky="w")

            color = Colors.TEXT_PRIMARY
            if label == "Severity": color = Colors.CRITICAL

            ctk.CTkLabel(parent, text=val, font=("Roboto", 13, "bold"), text_color=color, anchor="w").grid(row=i, column=1, padx=20, pady=10, sticky="w")
            ctk.CTkFrame(parent, height=1, fg_color=Colors.BORDER).grid(row=i, column=0, columnspan=2, sticky="ew", padx=10)

    def build_forensics(self, parent):
        ctk.CTkLabel(parent, text="Desktop Capture (At Incident Time)", font=Fonts.H3).pack(anchor="w", padx=20, pady=(10,5))

        screen_frame = ctk.CTkFrame(parent, height=200, fg_color=Colors.PRIMARY_BG, border_color=Colors.ACCENT_BLUE, border_width=2)
        screen_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(screen_frame, text="[ SCREENSHOT CAPTURE PLACEHOLDER ]\nUser Activity: Editing 'passwords.txt'", text_color=Colors.TEXT_SECONDARY).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(parent, text="File Integrity Analysis", font=Fonts.H3).pack(anchor="w", padx=20, pady=(20,5))

        f_frame = ctk.CTkFrame(parent, fg_color=Colors.SECONDARY_BG)
        f_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(f_frame, text="Original Hash (SHA-256):", font=Fonts.MONO, text_color=Colors.SUCCESS).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(f_frame, text="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", font=Fonts.MONO).grid(row=0, column=1, sticky="w", padx=10)

        ctk.CTkLabel(f_frame, text="Modified Hash (SHA-256):", font=Fonts.MONO, text_color=Colors.CRITICAL).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(f_frame, text="8929944298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b842", font=Fonts.MONO).grid(row=1, column=1, sticky="w", padx=10)

    def build_processes(self, parent):
        ctk.CTkLabel(parent, text="Suspect Process Chain", font=Fonts.H3).pack(anchor="w", padx=20, pady=10)

        txt = ctk.CTkTextbox(parent, font=Fonts.MONO, text_color=Colors.TEXT_PRIMARY, fg_color=Colors.PRIMARY_BG)
        txt.pack(fill="both", expand=True, padx=20, pady=10)
        txt.insert("0.0", "> explorer.exe (pid: 4022) User: Admin\n  > notepad.exe (pid: 5510) [TARGET FILE OPEN]\n    > cmd.exe (pid: 9912) [SPAWNED]\n      > net.exe user add hacker 1234 /add [BLOCKED]")
        txt.configure(state="disabled")

    def resolve(self):
        stubs.resolve_alert(self.data['id'], "Manual Close")
        self.destroy()