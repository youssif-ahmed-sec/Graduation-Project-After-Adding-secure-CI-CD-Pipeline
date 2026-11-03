"""
components/table.py
Shared Table Component to enforce consistent alignment across the application.
Uses Grid layout exclusively.
"""
import customtkinter as ctk
from ui.theme import Colors, Fonts

class TableColumn:
    def __init__(self, name, width=100, weight=0, anchor="w", key=None, min_width=None):
        self.name = name
        self.width = min_width if min_width is not None else width
        self.weight = weight
        self.anchor = anchor
        self.key = key

class TableHelper:
    @staticmethod
    def render_header(parent, columns, height=35):
        """Renders the header row using grid."""
        header = ctk.CTkFrame(parent, fg_color=Colors.SECONDARY_BG, height=height, corner_radius=0)
        header.pack(fill="x")

        for i, col in enumerate(columns):
            header.grid_columnconfigure(i, weight=col.weight, minsize=col.width)

            lbl = ctk.CTkLabel(
                header,
                text=col.name.upper(),
                font=("Roboto", 11, "bold"),
                text_color=Colors.TEXT_SECONDARY,
                anchor=col.anchor
            )
            lbl.grid(row=0, column=i, sticky="ew", padx=10, pady=8)

        return header

    @staticmethod
    def render_row(parent, columns, data_map=None, height=45):

        row = ctk.CTkFrame(parent, fg_color=Colors.PANEL_BG, corner_radius=0, height=height)
        row.pack(fill="x", pady=2)

        for i, col in enumerate(columns):
            row.grid_columnconfigure(i, weight=col.weight, minsize=col.width)

            if data_map:
                key = col.key if col.key else i
                if key in data_map:
                    val_data = data_map[key]
                    text = str(val_data)
                    color = Colors.TEXT_PRIMARY
                    font = Fonts.BODY

                    if isinstance(val_data, tuple):
                        text = str(val_data[0])
                        if len(val_data) > 1: color = val_data[1]
                        if len(val_data) > 2: font = val_data[2]

                    lbl = ctk.CTkLabel(row, text=text, font=font, text_color=color, anchor=col.anchor)
                    lbl.grid(row=0, column=i, sticky="ew", padx=10)

        return row
