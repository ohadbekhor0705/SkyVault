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
        file_hash: bytes,
        share_link: bool,
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
        self.file_hash = file_hash
        self.share_link = share_link

        self.default_fg = self.cget("fg_color")
        self.hover_fg = ("#cfcfcf", "#3a3a3a")
        self.check_var: ctk.BooleanVar = ctk.BooleanVar(value=share_link)

        # Fixed Column Configuration for perfect alignment across rows
        self.grid_columnconfigure(0, minsize=300)  # Name column 
        self.grid_columnconfigure(1, minsize=100)  # Size column
        self.grid_columnconfigure(2, minsize=150)  # Date column
        self.grid_columnconfigure(3, weight=1)      # Spacer to push buttons right
        self.grid_columnconfigure(4, weight=0)      # Menu button
        self.grid_columnconfigure(5, weight=0)      # Checkbox

        # Widgets - set fg_color to transparent so they inherit the Frame's hover color
        self.name_label = ctk.CTkLabel(self, text=file_name, anchor="w", fg_color="transparent")
        self.size_label = ctk.CTkLabel(self, text=file_size, anchor="w", fg_color="transparent")
        self.date_label = ctk.CTkLabel(self, text=str(date_modified), anchor="w", fg_color="transparent")
        self.link_checkbox = ctk.CTkCheckBox(self, command=self._handle_share, variable=self.check_var, text="")
        self.menu_button = ctk.CTkButton(self, text="⋯", width=36, command=self._show_menu)

        # Grid placement with consistent sticky behavior
        Padx = 12
        Pady = 10
        self.name_label.grid(row=0, column=0, padx=Padx, pady=Pady, sticky="w")
        self.size_label.grid(row=0, column=1, padx=Padx, pady=Pady, sticky="w")
        self.date_label.grid(row=0, column=2, padx=Padx, pady=Pady, sticky="w")
        self.menu_button.grid(row=0, column=4, padx=Padx, pady=Pady, sticky="e")
        self.link_checkbox.grid(row=0, column=5, padx=Padx, pady=Pady, sticky="e")

        # Context menu
        bg_color = "#2b2b2b"
        fg_color = "#ffffff"
        select_color = "#3d3d3d"
        self.menu = tk.Menu(
            self,
            tearoff=0,
            bg=bg_color,
            fg=fg_color,
            activebackground=select_color,
            activeforeground=bg_color,
            bd=0,
            font=ctk.CTkFont(size=20)
        )
        self.menu.add_command(label="💾 Save file", command=self._handle_save)
        self.menu.add_separator()
        self.menu.add_command(label="🗑️ Delete file", command=self._handle_delete)

        # Hover bindings
        widgets = (self.name_label, self.size_label, self.date_label, self.menu_button, self.link_checkbox)
        self._bind_hover(self)
        for w in widgets:
            self._bind_hover(w)

    # Hover handling
    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        self.configure(fg_color=self.hover_fg)

    def _on_leave(self, event=None):
        self.configure(fg_color=self.default_fg)

    # Menu handling
    def _show_menu(self):
        x = self.menu_button.winfo_rootx()
        y = self.menu_button.winfo_rooty() + self.menu_button.winfo_height()
        self.menu.tk_popup(x, y)

    # Keep all original handlers exactly as-is
    def _handle_delete(self):
        if self.on_delete:
            self.on_delete()

    def _handle_save(self):
        if self.on_save:
            self.on_save()

    def _handle_share(self):
        if self.on_share:
            self.on_share()