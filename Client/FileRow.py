import customtkinter as ctk
import tkinter as tk
from typing import Callable, Optional


class FileRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        file_id: str,
        file_name: str,
        file_size: str,
        date_modified: str,
        on_delete: Optional[Callable[[str], None]] = None,
        on_save: Optional[Callable[[str], None]] = None,
        on_share: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.file_id = file_id
        self.on_delete = on_delete
        self.on_save = on_save
        self.on_share = on_share

        # Colors for hover behavior
        self.default_fg = self.cget("fg_color")
        self.hover_fg = ("#2b2b2b", "#3a3a3a")  # light / dark mode safe

        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=2)
        self.grid_columnconfigure(4, weight=0)

        # Labels
        self.id_label = ctk.CTkLabel(self, text=file_id, anchor="w")
        self.name_label = ctk.CTkLabel(self, text=file_name, anchor="w")
        self.size_label = ctk.CTkLabel(self, text=file_size, anchor="e")
        self.date_label = ctk.CTkLabel(self, text=date_modified, anchor="w")

        self.menu_button = ctk.CTkButton(
            self,
            text="⋯",
            width=36,
            command=self._show_menu
        )

        widgets = (
            self.id_label,
            self.name_label,
            self.size_label,
            self.date_label,
            self.menu_button,
        )

        self.id_label.grid(row=0, column=0, padx=8, pady=6, sticky="ew")
        self.name_label.grid(row=0, column=1, padx=8, pady=6, sticky="ew")
        self.size_label.grid(row=0, column=2, padx=8, pady=6, sticky="e")
        self.date_label.grid(row=0, column=3, padx=8, pady=6, sticky="ew")
        self.menu_button.grid(row=0, column=4, padx=6, pady=6)

        # Context menu with emoji icons
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="💾 Save file", command=self._handle_save)
        self.menu.add_command(label="🔗 Share file", command=self._handle_share)
        self.menu.add_separator()
        self.menu.add_command(label="🗑️ Delete file", command=self._handle_delete)

        # Hover bindings (apply to frame + children)
        self._bind_hover(self)
        for w in widgets:
            self._bind_hover(w)

    # ----------------------
    # Hover handling
    # ----------------------

    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        self.configure(fg_color=self.hover_fg)

    def _on_leave(self, event=None):
        self.configure(fg_color=self.default_fg)

    # ----------------------
    # Menu handling
    # ----------------------

    def _show_menu(self):
        x = self.menu_button.winfo_rootx()
        y = self.menu_button.winfo_rooty() + self.menu_button.winfo_height()
        self.menu.tk_popup(x, y)

    def _handle_delete(self):
        if self.on_delete:
            self.on_delete(self.file_id)

    def _handle_save(self):
        if self.on_save:
            self.on_save(self.file_id)

    def _handle_share(self):
        if self.on_share:
            self.on_share(self.file_id)
