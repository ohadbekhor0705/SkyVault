import customtkinter as ctk
import tkinter as tk
from typing import Callable, Optional, Any
import pyperclip
class FileRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        file_id: str,
        file_name: str,
        file_size: int,
        date_modified: str,
        file_hash: bytes,
        share_link: bool,
        client_bl,
        on_delete: Optional[Callable[[str], None]] = None,
        on_save: Optional[Callable[[str], None]] = None,
        on_share: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.client_bl = client_bl
        self.filename = file_name
        self.file_id = file_id

        self.on_delete = on_delete
        self.on_save = on_save
        self.on_share = on_share
        self.file_hash = file_hash
        self.share_link: str = ""
        self.has_share_link = share_link

        self.default_fg = self.cget("fg_color")
        self.hover_fg = ("#cfcfcf", "#3a3a3a")


        self.check_var: ctk.BooleanVar = ctk.BooleanVar(value=self.has_share_link)

        # Fixed Column Configuration for perfect alignment across rows
        self.grid_columnconfigure(0, minsize=300)  # Name column 
        self.grid_columnconfigure(1, minsize=100)  # Size column
        self.grid_columnconfigure(2, minsize=150)  # Date column
        self.grid_columnconfigure(3, weight=1)      # Spacer to push buttons right
        self.grid_columnconfigure(4, weight=0)      # Menu button
        self.grid_columnconfigure(5, weight=0)      # Checkbox

        # Widgets - set fg_color to transparent so they inherit the Frame's hover color
        self.name_entry = ctk.CTkEntry(self, border_width=0, fg_color="transparent", font=ctk.CTkFont("Outfit"))
        self.name_entry.insert(0, file_name)
        self.name_entry.configure(state="disabled")
        self.size_label = ctk.CTkLabel(self, text=file_size, anchor="w", fg_color="transparent")
        self.date_label = ctk.CTkLabel(self, text=str(date_modified), anchor="w", fg_color="transparent")
        self.link_checkbox = ctk.CTkCheckBox(self, command=self._handle_share, variable=self.check_var, text="")
        self.menu_button = ctk.CTkButton(self, text="⋯", width=36, command=self._show_menu)

        # Grid placement with consistent sticky behavior
        Padx = 12
        Pady = 6
        self.name_entry.grid(row=0, column=0, padx=Padx, pady=Pady, sticky="we")
        self.size_label.grid(row=0, column=1, padx=Padx, pady=Pady, sticky="w")
        self.date_label.grid(row=0, column=2, padx=Padx, pady=Pady, sticky="w")
        self.menu_button.grid(row=0, column=4, padx=Padx, pady=Pady, sticky="e")
        self.link_checkbox.grid(row=0, column=5, padx=Padx, pady=Pady, sticky="e")

        # Context menu with Windows-11 styling\n        
        BG_COLOR = "#ffffff"         # Pure white menu background\n        
        FG_COLOR = "#000000"         # Black text
        ACTIVE_BG = "#226aa5"        # Soft Windows-11 style light blue for hover
        ACTIVE_FG = "#000000"        # Keep text black on hover
        self.menu = tk.Menu(
            self, 
            tearoff=0, 
            font=("Outfit", 15), 
            bg=BG_COLOR, 
            fg=FG_COLOR,
            activebackground=ACTIVE_BG, 
            activeforeground=ACTIVE_FG,
            relief="flat", 
            bd=0,
            activeborderwidth=0
        )

        self.name_entry.bind("<Return>", self._on_send)
        self.name_entry.bind("<Escape>", self._on_cancel)


        self.menu.add_command(label="Save file", command=self._handle_save)
        self.menu.add_separator()
        self.menu.add_command(label="Delete", command=self._handle_delete)
        self.menu.add_command(label="Rename", command=self._on_edit)
        self.menu.add_command(label="Copy link", command=lambda: pyperclip.copy(f"{self.client_bl.server_ip}/view_file/{self.file_id}"))

        # Hover bindings
        widgets = (self.name_entry, self.size_label, self.date_label, self.menu_button, self.link_checkbox)
        self._bind_hover(self)
        for w in widgets:
            self._bind_hover(w)


    # Hover handling
    def _bind_hover(self, widget):
        """Bind hover events to a widget to trigger enter/leave color changes."""
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


    def _on_edit(self):
        self.name_entry.configure(state="normal",border_width=2)
        self.name_entry.focus()
        end = self.name_entry.get().rfind(".")
        self.name_entry.select_range(0, end)
        self.name_entry.icursor(end)
        
        
    def _on_send(self, event):
        new_filename = self.name_entry.get().strip()
        if new_filename == "" or new_filename == self.filename or self.client_bl.work_event.is_set():
            if new_filename == "":
                self.name_entry.delete(0, "end")
                self.name_entry.insert(0, self.filename)
        else:
            if (not self.client_bl.work_event.is_set()) and self.client_bl._send_message({"cmd": "rename", "name": new_filename, "id": self.file_id, "type": "file"}):
                response = self.client_bl._get_message()
                if response:
                    if response["status"]:
                        self.filename = new_filename

        self.name_entry.configure(state="disabled", border_width=0)
    def _on_cancel(self, event=None):
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, self.filename)
        self.name_entry.configure(state="disabled", border_width=0)


