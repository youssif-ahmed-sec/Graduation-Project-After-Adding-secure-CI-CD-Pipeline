import customtkinter as ctk
from datetime import datetime

class ChatTerminal(ctk.CTkToplevel):
    def __init__(self, master, agent_id, socket_instance):
        super().__init__(master)

        self.agent_id = agent_id
        self.socket = socket_instance

        self.title(f"🚀 Remote Shell: {agent_id}")
        self.geometry("700x600")
        self.configure(fg_color="#1a1a1a")

        self.header = ctk.CTkFrame(self, fg_color="#252525", height=50, corner_radius=0)
        self.header.pack(fill="x")
        self.header_label = ctk.CTkLabel(self.header, text=f"Connected to: {agent_id}", font=("Consolas", 14, "bold"))
        self.header_label.pack(pady=10)

        self.chat_area = ctk.CTkScrollableFrame(self, fg_color="#1a1a1a", corner_radius=0)
        self.chat_area.pack(fill="both", expand=True, padx=10, pady=10)

        self.input_frame = ctk.CTkFrame(self, fg_color="#252525", height=60, corner_radius=15)
        self.input_frame.pack(fill="x", padx=15, pady=15)

        self.cmd_input = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Type command (e.g. dir, ipconfig, whoami)...",
            fg_color="transparent", border_width=0, font=("Consolas", 13)
        )
        self.cmd_input.pack(side="left", fill="x", expand=True, padx=15)
        self.cmd_input.bind("<Return>", self.send_command)

        self.send_btn = ctk.CTkButton(
            self.input_frame, text="➤", width=40, height=40,
            corner_radius=20, fg_color="#1f538d", hover_color="#14375e",
            command=self.send_command
        )
        self.send_btn.pack(side="right", padx=10)

        self.socket.on('update_admin_terminal', self.receive_response)

    def add_bubble(self, message, sender="admin"):
        timestamp = datetime.now().strftime("%H:%M")

        bubble_frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        bubble_frame.pack(fill="x", pady=5)

        if sender == "admin":
            bubble = ctk.CTkFrame(bubble_frame, fg_color="#1f538d", corner_radius=15)
            bubble.pack(side="right", padx=(50, 10))
            text_color = "white"
            alignment = "right"
        else:
            bubble = ctk.CTkFrame(bubble_frame, fg_color="#333333", corner_radius=15)
            bubble.pack(side="left", padx=(10, 50))
            text_color = "#00FF00"
            alignment = "left"

        msg_label = ctk.CTkLabel(
            bubble, text=message, wraplength=450,
            font=("Consolas", 12), text_color=text_color, justify=alignment
        )
        msg_label.pack(padx=12, pady=8)

        time_label = ctk.CTkLabel(bubble_frame, text=timestamp, font=("Arial", 9), text_color="gray")
        time_label.pack(side="right" if sender == "admin" else "left", padx=15)

        self.chat_area._parent_canvas.yview_moveto(1.0)

    def send_command(self, event=None):
        cmd = self.cmd_input.get().strip()
        if cmd:
            self.add_bubble(cmd, sender="admin")
            self.socket.emit('send_command_to_agent', {'agent_id': self.agent_id, 'command': cmd})
            self.cmd_input.delete(0, "end")

    def receive_response(self, data):
        if data.get('agent_id') == self.agent_id:
            output = data.get('output', 'No output received.')
            self.add_bubble(output, sender="agent")