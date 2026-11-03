"""
components/modals.py
Reusable Modal Dialogs for Deployments, Additions, and Edits.
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts

class BaseModal(ctk.CTkToplevel):
    def __init__(self, master, title, width=400, height=300):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.configure(fg_color=Colors.PRIMARY_BG)
        self.resizable(False, False)

        self.transient(master)
        self.grab_set()

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() // 2) - (width // 2)
        y = master.winfo_rooty() + (master.winfo_height() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)


class AddHoneyFileModal(ctk.CTkToplevel):
    def __init__(self, master, agents_list, save_callback, browse_callback):
        super().__init__(master)
        self.title("Deploy Honeyfile")
        self.geometry("450x550")
        self.attributes("-topmost", True)

        self.save_callback = save_callback
        self.browse_callback = browse_callback

        ctk.CTkLabel(self, text="Deploy New Honeyfile", font=("Arial", 16, "bold")).pack(pady=(20, 10))

        ctk.CTkLabel(self, text="Select Target Agents:", font=("Arial", 12)).pack(anchor="w", padx=20)

        self.agents_frame = ctk.CTkScrollableFrame(self, height=120)
        self.agents_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.agent_vars = {}

        self.select_all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.agents_frame, text="Select All", text_color="#FFCC00",
                        variable=self.select_all_var, command=self.toggle_all).pack(anchor="w", pady=(0, 10))

        for agent in agents_list:
            agent_id = agent.get("id", agent.get("agent_id", "Unknown"))
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(self.agents_frame, text=agent_id, variable=var)
            cb.pack(anchor="w", pady=2)
            self.agent_vars[agent_id] = var

        ctk.CTkLabel(self, text="Target Path:", font=("Arial", 12)).pack(anchor="w", padx=20)
        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="e.g. C:\\Users\\passwords.txt")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(path_frame, text="Browse", width=60, command=self.do_browse).pack(side="right")

        ctk.CTkLabel(self, text="Alert Level:", font=("Arial", 12)).pack(anchor="w", padx=20)
        self.level_var = ctk.StringVar(value="HIGH")
        ctk.CTkOptionMenu(self, variable=self.level_var, values=["LOW", "MED", "HIGH", "CRITICAL"]).pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(self, text="Deploy to Selected", fg_color="green", hover_color="darkgreen", command=self.save).pack(fill="x", padx=20, pady=10)

    def toggle_all(self):
        is_checked = self.select_all_var.get()
        for var in self.agent_vars.values():
            var.set(is_checked)

    def do_browse(self):
        selected_agents = [aid for aid, var in self.agent_vars.items() if var.get()]
        if not selected_agents:
            return
        self.browse_callback(selected_agents[0], self.path_entry, parent_modal=self)

    def save(self):
        selected_agents = [aid for aid, var in self.agent_vars.items() if var.get()]
        path = self.path_entry.get().strip()
        level = self.level_var.get()

        if not selected_agents:
            return
        if not path:
            return

        self.save_callback(selected_agents, path, level)
        self.destroy()

class DeployAgentModal(BaseModal):
    def __init__(self, master, callback):
        super().__init__(master, "Deploy New Agent", width=600, height=450)
        self.callback = callback
        self.step_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=40)
        self.step_frame.pack(fill="x", pady=(0, 20))
        self.create_step(self.step_frame, "1", "Config", True).pack(side="left", padx=10)
        ctk.CTkFrame(self.step_frame, width=30, height=2, fg_color=Colors.ACCENT_BLUE).pack(side="left")
        self.create_step(self.step_frame, "2", "Method", True).pack(side="left", padx=10)
        ctk.CTkFrame(self.step_frame, width=30, height=2, fg_color=Colors.BORDER).pack(side="left")
        self.create_step(self.step_frame, "3", "Deploy", False).pack(side="left", padx=10)
        ctk.CTkLabel(self.main_frame, text="Target Configuration", font=Fonts.H3).pack(anchor="w", pady=(0, 15))
        self.name_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Hostname (e.g. SRV-09)", height=40)
        self.name_entry.pack(fill="x", pady=(0, 15))
        self.os_combo = ctk.CTkComboBox(self.main_frame, values=["Windows 11", "Windows Server 2022", "Ubuntu 22.04 LTS"], height=40)
        self.os_combo.pack(fill="x", pady=(0, 15))
        self.method_seg = ctk.CTkSegmentedButton(self.main_frame, values=["Local Script", "Network Push", "GPO"], height=40)
        self.method_seg.set("Network Push")
        self.method_seg.pack(fill="x", pady=(0, 20))
        self.status_lbl = ctk.CTkLabel(self.main_frame, text="Ready.", font=Fonts.META, text_color=Colors.TEXT_SECONDARY)
        self.status_lbl.pack(pady=(0, 10))
        ctk.CTkButton(self.main_frame, text="Generate & Deploy", fg_color=Colors.ACCENT_BLUE, height=45, command=self.deploy).pack(fill="x", side="bottom")

    def create_step(self, parent, num, text, active):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        bg = Colors.ACCENT_BLUE if active else Colors.BORDER
        ctk.CTkButton(f, text=num, width=24, height=24, corner_radius=12, fg_color=bg, hover=False).pack(side="left", padx=5)
        ctk.CTkLabel(f, text=text, font=("Roboto", 11)).pack(side="left")
        return f

    def deploy(self):
        if self.name_entry.get():
            self.callback(self.name_entry.get(), self.os_combo.get(), self.method_seg.get())
            self.destroy()

class LevelModal(BaseModal):
    def __init__(self, master, title, callback, existing_data=None):
        super().__init__(master, title, height=350)
        self.callback = callback
        self.colors = {"Green (Low)": "#22C55E", "Yellow (Med)": "#F59E0B", "Orange (High)": "#F97316", "Red (Crit)": "#EF4444"}
        ctk.CTkLabel(self.main_frame, text="Sensitivity Definition", font=Fonts.H3).pack(anchor="w", pady=(0, 15))
        self.name_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Level Name", height=35)
        self.name_entry.pack(fill="x", pady=(0, 15))
        self.color_combo = ctk.CTkComboBox(self.main_frame, values=list(self.colors.keys()), height=35)
        self.color_combo.pack(fill="x", pady=(0, 20))
        if existing_data: self.name_entry.insert(0, existing_data['name'])
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x")
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy).pack(side="left")
        ctk.CTkButton(btn_frame, text="Save", command=self.save).pack(side="right")

    def save(self):
        if self.name_entry.get():
            self.callback(self.name_entry.get(), self.colors.get(self.color_combo.get()))
            self.destroy()

class SolutionModal(BaseModal):
    def __init__(self, master, title, callback, existing_data=None):
        super().__init__(master, title, width=500, height=550)
        self.callback = callback

        ctk.CTkLabel(self.main_frame, text="Solution Registry", font=Fonts.H3).pack(anchor="w", pady=(0, 15))


        ctk.CTkLabel(self.main_frame, text="Company *", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(5,0))
        self.company = ctk.CTkEntry(self.main_frame, height=35)
        self.company.pack(fill="x", pady=(0, 5))


        ctk.CTkLabel(self.main_frame, text="Product Name *", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(5,0))
        self.product = ctk.CTkEntry(self.main_frame, height=35)
        self.product.pack(fill="x", pady=(0, 5))


        ctk.CTkLabel(self.main_frame, text="Category *", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(5,0))
        self.category = ctk.CTkComboBox(self.main_frame, values=["Antivirus/EDR", "DLP", "FIM", "System Logs", "Other"], height=35)
        self.category.pack(fill="x", pady=(0, 5))


        ctk.CTkLabel(self.main_frame, text="Research Status *", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(5,0))
        self.status = ctk.CTkComboBox(self.main_frame, values=["Researching", "Validated", "Replaced", "Not Relevant"], height=35)
        self.status.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(self.main_frame, text="Key Strengths", font=Fonts.META, text_color=Colors.TEXT_SECONDARY).pack(anchor="w", pady=(5,0))
        self.strengths = ctk.CTkTextbox(self.main_frame, height=80)
        self.strengths.pack(fill="x", pady=(0, 10))


        if existing_data:
            self.company.insert(0, existing_data.get('company', ''))
            self.product.insert(0, existing_data.get('product', ''))
            self.category.set(existing_data.get('category', 'Antivirus/EDR'))
            self.status.set(existing_data.get('status', 'Researching'))
            self.strengths.insert("0.0", existing_data.get('strengths', ''))

        self.error_lbl = ctk.CTkLabel(self.main_frame, text="", text_color=Colors.CRITICAL, font=Fonts.META)
        self.error_lbl.pack(pady=5)

        ctk.CTkButton(self.main_frame, text="Save Solution", fg_color=Colors.ACCENT_BLUE, height=40, command=self.save).pack(fill="x", side="bottom")

    def save(self):
        data = {
            "company": self.company.get().strip(),
            "product": self.product.get().strip(),
            "category": self.category.get(),
            "status": self.status.get(),
            "strengths": self.strengths.get("0.0", "end").strip()
        }

        if not data['company'] or not data['product']:
            self.error_lbl.configure(text="Company and Product are required.")
            return

        self.callback(data)
        self.destroy()

class FlawFixModal(BaseModal):
    def __init__(self, master, title, callback, existing_data=None):
        super().__init__(master, title, width=600, height=700)
        self.callback = callback

        ctk.CTkLabel(self.main_frame, text="Flaw & Fix Mapping", font=Fonts.H3).pack(anchor="w", pady=(0, 15))

        scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, pady=(0, 20))


        ctk.CTkLabel(scroll, text="Identified Flaw/Error *", font=Fonts.META).pack(anchor="w", pady=(5,0))
        self.flaw = ctk.CTkTextbox(scroll, height=80)
        self.flaw.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(scroll, text="Impact Level *", font=Fonts.META).pack(anchor="w", pady=(5,0))
        self.impact = ctk.CTkComboBox(scroll, values=["Low", "Medium", "High", "Critical"], height=35)
        self.impact.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(scroll, text="Evidence (Short/One-liner)", font=Fonts.META).pack(anchor="w", pady=(5,0))
        self.evidence = ctk.CTkEntry(scroll, height=35)
        self.evidence.pack(fill="x", pady=(0, 5))

        ctk.CTkFrame(scroll, height=1, fg_color=Colors.BORDER).pack(fill="x", pady=15)

        ctk.CTkLabel(scroll, text="Our Fix (File Track) *", font=Fonts.META).pack(anchor="w", pady=(5,0))
        self.fix = ctk.CTkTextbox(scroll, height=80)
        self.fix.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(scroll, text="Fix Mechanism *", font=Fonts.META).pack(anchor="w", pady=(5,0))
        self.fix_type = ctk.CTkComboBox(scroll, values=["HoneyFiles", "Event-driven Monitoring", "Adaptive Response", "Visual Forensics", "Process Attribution", "Other"], height=35)
        self.fix_type.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(scroll, text="Verification Status *", font=Fonts.META).pack(anchor="w", pady=(5,0))
        self.status = ctk.CTkComboBox(scroll, values=["Proposed", "Implemented (UI)", "Verified (UI)", "Needs Testing"], height=35)
        self.status.pack(fill="x", pady=(0, 5))

        if existing_data:
            self.flaw.insert("0.0", existing_data.get('flaw', ''))
            self.impact.set(existing_data.get('impact', 'Medium'))
            self.evidence.insert(0, existing_data.get('evidence', ''))
            self.fix.insert("0.0", existing_data.get('fix', ''))
            self.fix_type.set(existing_data.get('fix_type', 'Other'))
            self.status.set(existing_data.get('status', 'Proposed'))

        self.error_lbl = ctk.CTkLabel(self.main_frame, text="", text_color=Colors.CRITICAL, font=Fonts.META)
        self.error_lbl.pack(pady=5)

        ctk.CTkButton(self.main_frame, text="Save Mapping", fg_color=Colors.ACCENT_BLUE, height=40, command=self.save).pack(fill="x", side="bottom")

    def save(self):
        data = {
            "flaw": self.flaw.get("0.0", "end").strip(),
            "impact": self.impact.get(),
            "evidence": self.evidence.get().strip(),
            "fix": self.fix.get("0.0", "end").strip(),
            "fix_type": self.fix_type.get(),
            "status": self.status.get()
        }

        if not data['flaw'] or not data['fix']:
            self.error_lbl.configure(text="Flaw and Fix description are required.")
            return

        self.callback(data)
        self.destroy()

class NoteModal(BaseModal):
    def __init__(self, master, title, callback):
        super().__init__(master, title, height=300)
        self.callback = callback

        ctk.CTkLabel(self.main_frame, text="Add Analyst Note", font=Fonts.H3).pack(anchor="w", pady=(0, 15))

        self.txt = ctk.CTkTextbox(self.main_frame, height=120)
        self.txt.pack(fill="x", pady=(0, 20))
        self.txt.focus_set()

        ctk.CTkButton(self.main_frame, text="Save Note", fg_color=Colors.ACCENT_BLUE, height=40, command=self.save).pack(fill="x", side="bottom")

    def save(self):
        text = self.txt.get("0.0", "end").strip()
        if text:
            self.callback(text)
            self.destroy()