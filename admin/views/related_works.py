"""
views/related_works.py
Advanced Related Works Manager.
Features:
- Solutions Registry (Table 1)
- Flaws & Fixes Mapping (Table 2 - Linked to Selection in Table 1)
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts
from ui_stubs import stubs
from components.modals import SolutionModal, FlawFixModal

class RelatedWorksView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.selected_solution_id = None
        self.expanded_flaws = set()

        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.pack(fill="x", pady=(0, 10))

        info_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        info_frame.pack(side="left")
        ctk.CTkLabel(info_frame, text="Competing Solutions", font=Fonts.H2, text_color=Colors.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(info_frame, text="Compare using Solutions Registry and Flaw Mapping.", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w")

        btn_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="Clear Data", fg_color=Colors.SECONDARY_BG, hover_color=Colors.CRITICAL, width=100, command=self.clear_all).pack(side="right", padx=5)


        self.split_container = ctk.CTkFrame(self, fg_color="transparent")
        self.split_container.pack(fill="both", expand=True)

        self.build_solutions_table(self.split_container)

        ctk.CTkFrame(self.split_container, height=2, fg_color=Colors.ACCENT_BLUE).pack(fill="x", pady=20)

        self.build_flaws_table(self.split_container)

        self.refresh_solutions()
        self.refresh_flaws()


    def build_solutions_table(self, parent):
        h_frame = ctk.CTkFrame(parent, fg_color="transparent")
        h_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(h_frame, text="Table A: Solutions Registry", font=Fonts.H3).pack(side="left")
        ctk.CTkButton(h_frame, text="+ Add Solution", fg_color=Colors.ACCENT_BLUE, height=28, command=self.open_solution_modal).pack(side="right", padx=10)

        self.sol_search = ctk.CTkEntry(h_frame, placeholder_text="Search companies...", width=200)
        self.sol_search.pack(side="right")
        self.sol_search.bind("<KeyRelease>", self.refresh_solutions)

        thead = ctk.CTkFrame(parent, fg_color=Colors.SECONDARY_BG, height=35)
        thead.pack(fill="x")
        thead.grid_columnconfigure((0,1,2,3,4,5,6), weight=1)

        cols = ["COMPANY", "PRODUCT", "CATEGORY", "STRENGTHS", "FLAWS", "STATUS", "ACTIONS"]
        for i, c in enumerate(cols):
            ctk.CTkLabel(thead, text=c, font=("Roboto", 11, "bold"), text_color=Colors.TEXT_SECONDARY).grid(row=0, column=i, sticky="ew", padx=5, pady=8)

        self.sol_scroll = ctk.CTkScrollableFrame(parent, height=200, fg_color=Colors.PRIMARY_BG)
        self.sol_scroll.pack(fill="x")
        self.sol_scroll.grid_columnconfigure((0,1,2,3,4,5,6), weight=1)

    def refresh_solutions(self, event=None):
        for w in self.sol_scroll.winfo_children(): w.destroy()

        query = self.sol_search.get().lower()
        rows = stubs.solutions

        if query:
            rows = [r for r in rows if query in r['company'].lower() or query in r['product'].lower()]

        if not rows:
            ctk.CTkLabel(self.sol_scroll, text="No solutions found. Add one to begin.", text_color=Colors.TEXT_SECONDARY).pack(pady=20)
            return

        for r in rows:
            self.render_solution_row(r)

    def render_solution_row(self, data):
        is_selected = (self.selected_solution_id == data['id'])
        bg_color = Colors.PANEL_BG if not is_selected else "#252B35"
        border_c = Colors.BORDER if not is_selected else Colors.ACCENT_BLUE
        border_w = 0 if not is_selected else 2

        row = ctk.CTkFrame(self.sol_scroll, fg_color=bg_color, border_color=border_c, border_width=border_w, height=45)
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure((0,1,2,3,4,5,6), weight=1)

        row.bind("<Button-1>", lambda e: self.select_solution(data['id']))

        def bind_click(widget):
            widget.bind("<Button-1>", lambda e: self.select_solution(data['id']))

        flaw_count = stubs.get_limitations_count(data['id'])

        vals = [
            (data['company'], Colors.TEXT_PRIMARY),
            (data['product'], Colors.TEXT_SECONDARY),
            (data['category'], Colors.TEXT_SECONDARY),
            (data['strengths'][:25]+"..." if len(data['strengths'])>25 else data['strengths'], Colors.TEXT_SECONDARY),
            (str(flaw_count), Colors.TEXT_PRIMARY),
            (data['status'], Colors.SUCCESS if data['status']=="Validated" else Colors.WARNING)
        ]

        for i, (txt, col) in enumerate(vals):
            lbl = ctk.CTkLabel(row, text=txt, text_color=col, font=Fonts.BODY)
            lbl.grid(row=0, column=i, sticky="ew", padx=5)
            bind_click(lbl)

        act_frame = ctk.CTkFrame(row, fg_color="transparent")
        act_frame.grid(row=0, column=6)
        ctk.CTkButton(act_frame, text="Edit", width=40, height=20, fg_color=Colors.SECONDARY_BG, command=lambda: self.edit_solution(data)).pack(side="left", padx=2)
        ctk.CTkButton(act_frame, text="Del", width=40, height=20, fg_color=Colors.CRITICAL, command=lambda: self.delete_solution(data['id'])).pack(side="left", padx=2)
        bind_click(act_frame)

    def select_solution(self, s_id):
        self.selected_solution_id = s_id
        self.refresh_solutions()
        self.refresh_flaws()

    def build_flaws_table(self, parent):
        h_frame = ctk.CTkFrame(parent, fg_color="transparent")
        h_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(h_frame, text="Table B: Flaws & Our Fix Mapping", font=Fonts.H3).pack(side="left")

        self.add_flaw_btn = ctk.CTkButton(h_frame, text="+ Map New Flaw", fg_color=Colors.ACCENT_BLUE, height=28, command=self.open_flaw_modal)
        self.add_flaw_btn.pack(side="right", padx=10)

        self.flaw_search = ctk.CTkEntry(h_frame, placeholder_text="Filter flaws...", width=200)
        self.flaw_search.pack(side="right")
        self.flaw_search.bind("<KeyRelease>", self.refresh_flaws)

        thead = ctk.CTkFrame(parent, fg_color=Colors.SECONDARY_BG, height=35)
        thead.pack(fill="x")
        thead.grid_columnconfigure((0,1,2,3,4,5,6), weight=1)

        cols = ["FLAW / ERROR", "IMPACT", "EVIDENCE", "OUR FIX", "TYPE", "STATUS", "ACTIONS"]
        for i, c in enumerate(cols):
            ctk.CTkLabel(thead, text=c, font=("Roboto", 11, "bold"), text_color=Colors.TEXT_SECONDARY).grid(row=0, column=i, sticky="ew", padx=5, pady=8)

        self.flaw_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.flaw_scroll.pack(fill="both", expand=True)

    def refresh_flaws(self, event=None):
        for w in self.flaw_scroll.winfo_children(): w.destroy()

        if not self.selected_solution_id:
            ctk.CTkLabel(self.flaw_scroll, text="Select a Solution above to view or map flaws.", font=Fonts.H3, text_color=Colors.TEXT_SECONDARY).pack(pady=40)
            self.add_flaw_btn.configure(state="disabled")
            return

        self.add_flaw_btn.configure(state="normal")

        rows = stubs.get_mappings_for_solution(self.selected_solution_id)
        query = self.flaw_search.get().lower()
        if query:
            rows = [r for r in rows if query in r['flaw'].lower() or query in r['fix'].lower()]

        if not rows:
            ctk.CTkLabel(self.flaw_scroll, text="No flaws mapped yet for this solution.", text_color=Colors.TEXT_SECONDARY).pack(pady=20)
            return

        for r in rows:
            self.render_flaw_row(r)

    def render_flaw_row(self, data):
        container = ctk.CTkFrame(self.flaw_scroll, fg_color=Colors.PANEL_BG, corner_radius=6)
        container.pack(fill="x", pady=4)

        top = ctk.CTkFrame(container, fg_color="transparent", height=45)
        top.pack(fill="x", padx=5, pady=5)
        top.grid_columnconfigure((0,1,2,3,4,5), weight=1)

        is_expanded = data['id'] in self.expanded_flaws
        icon = "▼" if is_expanded else "▶"
        ctk.CTkButton(top, text=icon, width=24, fg_color="transparent", text_color=Colors.ACCENT_BLUE,
                      command=lambda: self.toggle_expand(data['id'])).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(top, text=data['flaw'][:30]+"...", font=("Roboto", 12, "bold")).grid(row=0, column=0, padx=(30,0), sticky="w")

        imp_col = Colors.CRITICAL if data['impact'] == "Critical" else (Colors.WARNING if data['impact'] == "High" else Colors.SUCCESS)
        ctk.CTkLabel(top, text=data['impact'], text_color=imp_col).grid(row=0, column=1)

        ctk.CTkLabel(top, text=data['evidence'], text_color=Colors.TEXT_SECONDARY).grid(row=0, column=2)
        ctk.CTkLabel(top, text=data['fix'][:30]+"...", text_color=Colors.SUCCESS).grid(row=0, column=3)
        ctk.CTkLabel(top, text=data['fix_type'], text_color=Colors.ACCENT_BLUE).grid(row=0, column=4)

        act = ctk.CTkFrame(top, fg_color="transparent")
        act.grid(row=0, column=5)
        ctk.CTkButton(act, text="Edit", width=40, height=20, fg_color=Colors.SECONDARY_BG, command=lambda: self.edit_flaw(data)).pack(side="left", padx=2)
        ctk.CTkButton(act, text="Del", width=40, height=20, fg_color=Colors.CRITICAL, command=lambda: self.delete_flaw(data['id'])).pack(side="left", padx=2)

        if is_expanded:
            det = ctk.CTkFrame(container, fg_color=Colors.SECONDARY_BG)
            det.pack(fill="both", padx=10, pady=(0, 10))

            f_box = ctk.CTkFrame(det, fg_color="transparent")
            f_box.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            ctk.CTkLabel(f_box, text="FULL FLAW DESCRIPTION", font=Fonts.META, text_color=Colors.CRITICAL).pack(anchor="w")
            ctk.CTkLabel(f_box, text=data['flaw'], wraplength=400, justify="left").pack(anchor="w", pady=(5,0))

            ctk.CTkFrame(det, width=1, fg_color=Colors.BORDER).pack(side="left", fill="y", pady=10)

            x_box = ctk.CTkFrame(det, fg_color="transparent")
            x_box.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            ctk.CTkLabel(x_box, text="FILE TRACK REMEDIATION", font=Fonts.META, text_color=Colors.SUCCESS).pack(anchor="w")
            ctk.CTkLabel(x_box, text=data['fix'], wraplength=400, justify="left").pack(anchor="w", pady=(5,0))

    def toggle_expand(self, r_id):
        if r_id in self.expanded_flaws:
            self.expanded_flaws.remove(r_id)
        else:
            self.expanded_flaws.add(r_id)
        self.refresh_flaws()

    def open_solution_modal(self):
        SolutionModal(self, "Add New Solution", self.handle_add_sol)

    def handle_add_sol(self, data):
        data['id'] = None
        stubs.add_solution(data)
        self.refresh_solutions()

    def edit_solution(self, data):
        SolutionModal(self, "Edit Solution", lambda d: self.handle_update_sol(data['id'], d), existing_data=data)

    def handle_update_sol(self, s_id, data):
        stubs.update_solution(s_id, data)
        self.refresh_solutions()

    def delete_solution(self, s_id):
        stubs.delete_solution(s_id)
        if self.selected_solution_id == s_id:
            self.selected_solution_id = None
            self.refresh_flaws()
        self.refresh_solutions()

    def open_flaw_modal(self):
        FlawFixModal(self, "Map New Flaw", self.handle_add_flaw)

    def handle_add_flaw(self, data):
        data['solution_id'] = self.selected_solution_id
        stubs.add_mapping(data)
        self.refresh_flaws()

    def edit_flaw(self, data):
        FlawFixModal(self, "Edit Mapping", lambda d: self.handle_update_flaw(data['id'], d), existing_data=data)

    def handle_update_flaw(self, m_id, data):
        data['solution_id'] = self.selected_solution_id
        stubs.update_mapping(m_id, data)
        self.refresh_flaws()

    def delete_flaw(self, m_id):
        stubs.delete_mapping(m_id)
        self.refresh_flaws()

    def clear_all(self):
        stubs.clear_solutions()
        self.selected_solution_id = None
        self.refresh_solutions()
        self.refresh_flaws()

    def export_toast(self):
        top = ctk.CTkToplevel(self)
        top.geometry("250x60")
        top.overrideredirect(True)
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 125
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 30
        top.geometry(f"+{x}+{y}")
        frm = ctk.CTkFrame(top, fg_color=Colors.ACCENT_BLUE, corner_radius=10)
        frm.pack(fill="both", expand=True)
        ctk.CTkLabel(frm, text="Exported Summary to PDF (Demo)", text_color="white", font=Fonts.BODY).pack(expand=True)
        self.after(2500, top.destroy)
