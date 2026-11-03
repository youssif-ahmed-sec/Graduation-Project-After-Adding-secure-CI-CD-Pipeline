"""
views/insights.py
Premium Market Analysis & Solution Comparison.
Displays static PDF-based data with user annotation capabilities.
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui_stubs import stubs
from components.modals import NoteModal

class InsightsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(self.top_bar, text="Market Insights", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(self.top_bar, text=" |  Detailed solution analysis & competitive positioning", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=10, pady=(5,0))

        self.tabs = ctk.CTkTabview(self, fg_color=Colors.PANEL_BG, segmented_button_selected_color=Colors.ACCENT_BLUE)
        self.tabs.pack(fill="both", expand=True)
        self.tabs.add("Market Comparison")
        self.tabs.add("Value Engineering")

        self.build_comparison_tab()
        self.build_value_tab()

    def build_comparison_tab(self):
        tab = self.tabs.tab("Market Comparison")

        info = ctk.CTkFrame(tab, fg_color=Colors.SECONDARY_BG)
        info.pack(fill="x", pady=(10, 20), padx=10)
        ctk.CTkLabel(info, text="Feature Matrix: File Track vs. Traditional Solutions", font=("Roboto", 14, "bold"), text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=20, pady=10)

        grid = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=10)

        headers = ["FEATURE", "TRADITIONAL FIM", "DLP SOLUTIONS", "ANTIVIRUS / EDR", "FILE TRACK (OURS)"]
        grid.grid_columnconfigure((0,1,2,3,4), weight=1)

        for i, h in enumerate(headers):
            color = Colors.ACCENT_BLUE if i == 4 else Colors.TEXT_SECONDARY
            font = ("Roboto", 12, "bold") if i == 4 else Fonts.META
            ctk.CTkLabel(grid, text=h, font=font, text_color=color).grid(row=0, column=i, sticky="ew", pady=10)

        for idx, row_data in enumerate(stubs.market_comparison):
            r = idx + 1
            bg = Colors.PANEL_BG if r % 2 == 0 else "transparent"
            row_frame = ctk.CTkFrame(grid, fg_color=bg, corner_radius=0)
            row_frame.grid(row=r, column=0, columnspan=5, sticky="ew")
            row_frame.grid_columnconfigure((0,1,2,3,4), weight=1)

            ctk.CTkLabel(row_frame, text=row_data['feature'], font=("Roboto", 12, "bold")).grid(row=0, column=0, pady=15)

            ctk.CTkLabel(row_frame, text=row_data['ossec'], text_color=Colors.TEXT_SECONDARY).grid(row=0, column=1)
            ctk.CTkLabel(row_frame, text=row_data['dlp'], text_color=Colors.TEXT_SECONDARY).grid(row=0, column=2)
            ctk.CTkLabel(row_frame, text=row_data['edr'], text_color=Colors.TEXT_SECONDARY).grid(row=0, column=3)

            ctk.CTkLabel(row_frame, text=row_data['file_track'], text_color=Colors.SUCCESS, font=("Roboto", 12, "bold")).grid(row=0, column=4)

            btn = ctk.CTkButton(row_frame, text="+", width=24, height=24, fg_color=Colors.SECONDARY_BG,
                                command=lambda f=row_data['feature']: self.open_note_modal(f))
            btn.grid(row=0, column=4, sticky="e", padx=5)

    def build_value_tab(self):
        tab = self.tabs.tab("Value Engineering")

        banner = ctk.CTkFrame(tab, fg_color=Colors.ACCENT_BLUE, height=60)
        banner.pack(fill="x", padx=10, pady=(10, 20))
        ctk.CTkLabel(banner, text="KEY TAKEAWAY", font=("Roboto", 12, "bold"), text_color="white").pack(side="left", padx=20)
        ctk.CTkLabel(banner, text="File Track bridges the gap between reactive logs and heavy content inspection.",
                     font=("Roboto", 16), text_color="white").pack(side="left", padx=10)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)

        for item in stubs.flaw_analysis:
            self.render_value_card(scroll, item)

    def render_value_card(self, parent, data):
        card = ctk.CTkFrame(parent, fg_color=Colors.PANEL_BG, corner_radius=8, border_color=Colors.BORDER, border_width=1)
        card.pack(fill="x", pady=10)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(hdr, text=data['system'], font=Fonts.H3, text_color=Colors.TEXT_PRIMARY).pack(side="left")

        imp_col = Colors.CRITICAL if data['impact'] == "Critical" else (Colors.WARNING if data['impact'] == "High" else Colors.SUCCESS)
        ctk.CTkLabel(hdr, text=f"Limit Impact: {data['impact']}", font=Fonts.META, text_color=imp_col).pack(side="right")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=(0, 15))

        flaw_frame = ctk.CTkFrame(content, fg_color=Colors.SECONDARY_BG, corner_radius=6)
        flaw_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ctk.CTkLabel(flaw_frame, text="THE FLAW", font=("Roboto", 10, "bold"), text_color=Colors.CRITICAL).pack(anchor="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(flaw_frame, text=data['flaw'], wraplength=350, justify="left", font=Fonts.BODY).pack(anchor="w", padx=10, pady=(0, 15))

        ctk.CTkLabel(content, text="➜", font=("Arial", 24), text_color=Colors.TEXT_SECONDARY).pack(side="left", padx=5)

        fix_frame = ctk.CTkFrame(content, fg_color=Colors.SECONDARY_BG, corner_radius=6)
        fix_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))

        ctk.CTkLabel(fix_frame, text="FILE TRACK FIX", font=("Roboto", 10, "bold"), text_color=Colors.SUCCESS).pack(anchor="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(fix_frame, text=data['fix'], wraplength=350, justify="left", font=Fonts.BODY).pack(anchor="w", padx=10, pady=(0, 15))

        act = ctk.CTkFrame(card, fg_color="transparent", height=30)
        act.pack(fill="x", padx=15, pady=(0, 10))
        ctk.CTkButton(act, text="Add Note", fg_color=Colors.SECONDARY_BG, text_color=Colors.TEXT_SECONDARY, width=80, height=24,
                      command=lambda s=data['system']: self.open_note_modal(s)).pack(side="right")

        notes = stubs.get_notes(data['system'])
        if notes:
            n_frame = ctk.CTkFrame(card, fg_color=Colors.PRIMARY_BG)
            n_frame.pack(fill="x", padx=15, pady=(0, 10))
            for n in notes:
                ctk.CTkLabel(n_frame, text=f"Note: {n['text']}", font=Fonts.META, text_color=Colors.ACCENT_BLUE).pack(anchor="w", padx=5, pady=2)


    def open_note_modal(self, target_id):
        NoteModal(self, f"Add Note to '{target_id}'", lambda t: self.handle_add_note(target_id, t))

    def handle_add_note(self, target_id, text):
        stubs.add_note(target_id, text)

        if self.tabs.get() == "Value Engineering":
             for w in self.tabs.tab("Value Engineering").winfo_children(): w.destroy()
             self.build_value_tab()

        self.show_toast("Note Added")

    def show_toast(self, msg):
        top = ctk.CTkToplevel(self)
        top.geometry("200x50")
        top.overrideredirect(True)
        x = self.winfo_rootx() + (self.winfo_width()//2) - 100
        y = self.winfo_rooty() + (self.winfo_height()//2) - 25
        top.geometry(f"+{x}+{y}")
        f = ctk.CTkFrame(top, fg_color=Colors.SUCCESS)
        f.pack(fill="both", expand=True)
        ctk.CTkLabel(f, text=msg, text_color="white").pack(expand=True)
        self.after(1500, top.destroy)
