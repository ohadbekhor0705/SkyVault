import itertools
import socket
from time import sleep
from typing import Callable, NoReturn
from CClientBL import CClientBL
import customtkinter as ctk
from UI_Components.FileRow import FileRow
import threading
from tkinter import filedialog as fd
from PIL import Image


def load_icon(path, size: tuple[int, int] = (20,20)):
    """Load and resize an icon image for UI buttons."""
    img = Image.open(path)
    return ctk.CTkImage(img, img, size)

# Dictionary of preloaded UI icons
icons: dict[str, ctk.CTkImage] = {
    "upload": load_icon("./icons/cloud_upload.png"),
    "delete": load_icon("./icons/delete.png"),
    "new_folder": load_icon("./icons/create_new_folder.png"),
    "cloud_lock": load_icon("./icons/cloud_lock.png"),
    "logout": load_icon("./icons/logout.png",size=(15,15))
}

# Set global theme and font
ctk.set_appearance_mode("light")

class MainFrame(ctk.CTkFrame):
    """Primary UI frame for authenticated session: folders/files lists, upload/delete/share ops."""

    def __init__(
        self,
        master,
        frames: dict[str, ctk.CTkFrame],
        client_bl: CClientBL | None = None,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        self.frames = frames
        self.client_bl = client_bl 
        self.folder_rows: dict[str, FolderRow] = {}

        # Create scrollable frames for folders and files
        self.folders_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.files_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.files_frame.columnconfigure(0, weight=1)
        self.folders_frame.columnconfigure(0, weight=1)

        # Configure grid layout
        self.grid_columnconfigure(0, weight=0, minsize=275)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)
        
        self.selected_folder_id: str = ""
        
        # Logout button
        self._disconnect_button = ctk.CTkButton(
            self,
            text="Logout",
            fg_color="red",
            hover_color=None,
            text_color="white",
            image=icons["logout"],
            font=ctk.CTkFont("Arial",15),
            command=self.on_click_logout
        )
        self._disconnect_button.grid(row=0, column=0, sticky="e", pady=17,padx=9, columnspan=2)

        # Header label for status messages
        self.header = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont("Arial",20)
        )
        self.header.grid(row=1, column=0, sticky="ew", pady=2,padx=9, columnspan=2)
        
        # Upload file button
        self.upload_button = ctk.CTkButton(
            self,
            text="Upload File",
            font= ctk.CTkFont("Arial",20),
            image=icons["upload"],
            compound="right",
            command=self._on_click_Upload
        )
        
        # Create new folder button
        self.create_folder_button = ctk.CTkButton(
            self,
            text="",
            image=icons["new_folder"],
            compound="right",
            font = ctk.CTkFont("Arial",20),
            command=self.on_click_create_folder
        )
        
        # Storage progress bar
        self.progress_bar = ctk.CTkProgressBar(self)

        # Grid layout for buttons and content
        self.progress_bar.grid(row=2, column=0, sticky="nsew",pady=9,padx=9, columnspan=2)
        self.upload_button.grid(row=3, column=1, sticky="nsew",pady=9,padx=9)
        self.create_folder_button.grid(row=3, column=0, sticky="nsew",pady=9,padx=9)
        self.folders_frame.grid(row=4, column=0, sticky="nsew",pady=7,padx=9)
        self.files_frame.grid(row=4, column=1, sticky="nsew", padx=3,pady=7)

        # Initialize with client data if available
        if client_bl:
            self.progress_bar.set(self.client_bl.current_storage/self.client_bl.max_storage)
            for i, f in enumerate(self.client_bl.folders):
                folder_row = FolderRow(self.folders_frame,self, f["folder_name"],f["folder_id"],self.client_bl, bool(f["is_system"]))
                folder_row.grid(column=0, row=i, sticky= "nsew", padx=12, pady=6)
                self.folder_rows[folder_row.folder_id] = folder_row
                if f["is_system"]:
                    self.selected_folder_id = f["folder_id"]
                    folder_row.on_click()
            
        # Start connection check thread      
        threading.Thread(target=self.check_connection, daemon=True).start()

            
    def _on_click_Upload(self) -> None:
        """Handle file upload button click."""
        # if other tasks are running then prevent from user from sending other network requests
        if self.client_bl.work_event.is_set():
            print("Another task is running!")
            return 
        
        # Open file dialog
        filename: str = fd.askopenfilename(
        title="Open a file",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            f = open(filename,"rb")
            res_text = self.header
            # Start upload in background thread
            task = threading.Thread(
                target=lambda: self.client_bl.sendfile(
                    f,
                    self.selected_folder_id,
                    [self.make_delete_callback, self.make_save_callback],
                    header_field=res_text,
                    parent=self.files_frame,
                    animate=self.animate,
                    bar = self.progress_bar
                )
            )
            task.start()
        else:
            self.header.configure(text="File not found! Please select a file again.", text_color= "red")
    
    def make_delete_callback(self,file_id: str, size: int, row: FileRow) -> Callable[[], None]:
        """Create a callback function for file deletion."""
        def callback():
            # Prevent multiple simultaneous operations
            if self.client_bl.work_event.is_set():
                return
            self.client_bl.work_event.set()
            threading.Thread(target=self.animate).start()
            # Call business logic
            self.client_bl.delete_file(
                file_id,
                size,
                header_field=self.header,
                bar=self.progress_bar
            )
            # Remove row from UI
            row.grid_forget()
        return lambda: threading.Thread(target=callback).start()
    
    def make_save_callback(self,file_id: str, filename: str, file_hash: str):
        """Create a callback function for file download/save."""
        def callback():
            print(f"Initiating download for file_id: {file_id}, filename: {filename}")
            # Prevent multiple simultaneous operations
            if self.client_bl.work_event.is_set():
                return 
            save_path = fd.askdirectory(title=f"Choose a path to save {filename}.")
            if not save_path:
                return
            self.client_bl.work_event.set()
           
            # Start animation and call business logic
            threading.Thread(target=self.animate).start()
            self.client_bl.ReceiveFile(file_id,filename,save_path,file_hash, header_field=self.header)
        return lambda: threading.Thread(target=callback).start()
    
    
    def on_click_create_folder(self):
        """Handle new folder creation."""
        # Prevent multiple simultaneous operations
        if self.client_bl.work_event.is_set():
            return
        # Start folder creation in background thread
        if self.client_bl._send_message({"cmd": "create_folder"}):
            response = self.client_bl._get_message()
            if response:
                if response["status"]:
                    folder_id: str = response["folder_id"]
                    new_folder = FolderRow(self.folders_frame, self,"", folder_id, self.client_bl, False)
                    self.folder_rows[folder_id] = new_folder
                    new_folder.grid(column=0, row = self.folders_frame.grid_size()[1],sticky= "nsew", padx=12, pady=6)
                    new_folder._on_double_click()
    
    def clear_file_rows(self):
        """Remove all file rows from the files frame."""
        for file_row in self.files_frame.grid_slaves():
            file_row.destroy()
            del file_row
    
    def animate(self):
        """Animate dots while task is running."""
        dots = [i*"." for i in range(7)]
        for c in itertools.cycle(dots):
            if self.client_bl.work_event.is_set():
                self.header.configure(text=c)
                sleep(0.5)
            else: 
                break
    
    def on_click_logout(self):
        """Handle logout button click."""
        self.client_bl._send_message({"cmd":"logout"})
        self.client_bl.work_event.set()
        if response := self.client_bl._get_message():
            def logout_cleanup():
                if response["status"]:
                    self.client_bl.work_event.clear()
                    # Clean up Main frame safely
                    if "Main" in self.frames:
                        self.frames["Main"].destroy()
                        del self.frames["Main"]
                    # Raise Home page
                    self.frames["Home"].tkraise()
                    # Optionally restart connection flow
            self.after(100, logout_cleanup)

            self.frames["Home"]._process_tcp_connection()
    
    def check_connection(self) -> NoReturn:
        """Monitor server connection health."""
        try:
            while True:
                if not self.client_bl.work_event.is_set(): 
                    self.client_bl._send_message({"cmd": "ping"})
                    if response := self.client_bl._get_message():
                         if response["status"]:
                            print("Connection healthy") 
                    else:
                         raise ConnectionError("No response to ping")
                sleep(3)
        except (socket.error, ConnectionAbortedError, ConnectionError, ConnectionResetError, BrokenPipeError):
            def logout_cleanup():
                    self.client_bl.work_event.clear()
                    # Clean up Main frame safely
                    if "Main" in self.frames:
                        self.frames["Main"].destroy()
                        del self.frames["Main"]
                    # Raise Home page
                    self.frames["Home"].tkraise()
                    # Optionally restart connection flow
            self.after(100, logout_cleanup)
            self.frames["Home"]._process_tcp_connection()
            


class FolderRow(ctk.CTkFrame):
    """UI component representing a single folder row."""
    
    def __init__(self,
        master: ctk.CTkScrollableFrame,main_frame: MainFrame,
        folder_name: str ,folder_id: str,
        client_bl: CClientBL,
        is_system: bool = False,
        **kwargs
    ):
        
        super().__init__(master,**kwargs)
        self.client_bl: CClientBL = client_bl
        self.is_system = is_system
        self.folder_name = folder_name if folder_name != "" else "unnamed"
        self.root = master
        self.main_frame = main_frame
        self.folder_id = folder_id
        self.default_fg = self.cget("fg_color")
        self.hover_fg = ("#cfcfcf", "#3a3a3a")
        self.columnconfigure(1,weight=0, minsize=20)

        Padx = 12
        Pady = 6

        # Folder name entry field
        self.folder_entry = ctk.CTkEntry(self,
            border_width=0,
            font=ctk.CTkFont("Arial",20),
            fg_color="transparent"
        )
        self.folder_entry.insert(0, folder_name)
        self.folder_entry.configure(state="disabled")
        self.folder_entry.grid(row=0,column=0, sticky="nsew" ,padx=Padx,pady=Pady)

        # Delete button (only for non-system folders)
        if not self.is_system:
            self.delete_button = ctk.CTkButton(
                self,
                text="",
                image=icons["delete"],
                command=self.on_click_delete,
                width=20,
                fg_color="red"
            )
            self.delete_button.grid(row=0,column=1,sticky="nsew" ,padx=0,pady=Pady)

            # Bind editing events
            self.folder_entry.bind("<Double-Button-1>", self._on_double_click)
            self.folder_entry.bind("<Return>", self._on_send)
            self.folder_entry.bind("<Escape>", self._on_cancel)

        self.configure(corner_radius=15)
        self._bind_hover(self.folder_entry)

    def on_click(self, event=None):
        """Handle folder selection - load files for this folder."""
        # Deselect previous folder\
        print(self.client_bl.work_event.is_set())
        if self.client_bl.work_event.is_set():
            return
        
        if prev := self.main_frame.folder_rows.get(self.main_frame.selected_folder_id):
            if prev != self:
                prev.configure(border_width=0)
                prev._on_cancel()
        
        # Clear previous files and load new folder's files
        self.main_frame.after(50, self.main_frame.clear_file_rows)
        self.main_frame.selected_folder_id = self.folder_id
        self.configure(border_width = 4, border_color=("gray50", "gray75"), fg_color = "transparent")

        # Fetch and display files for this folder
        file_rows: list[FileRow] = self.client_bl.get_files_data(
            self.folder_id,
            self.main_frame.files_frame, [
                self.main_frame.make_delete_callback,
                self.main_frame.make_save_callback,
            ],
            header_field = self.main_frame.header,
            animate = self.main_frame.animate
        )
        
        for i, file_row in enumerate(file_rows):
            file_row.grid(row=i, column=0, padx=12,pady=6, sticky="nsew")
  
    def _on_double_click(self, event=None):
        """Enable folder name editing on double-click."""
        if self.client_bl.work_event.is_set():
            return
        self.main_frame.upload_button.configure(state="disabled")
        self.main_frame.create_folder_button.configure(state="disabled")
        self.folder_entry.configure(state="normal", border_width=2)
        self.folder_entry.focus()
    
    def _on_send(self, event):
        """Confirm folder rename."""
        self.folder_entry.configure(state="disabled", border_width=0)
        new_name =  self.folder_entry.get()
        print(type(self.client_bl))
        if (not self.client_bl.work_event.is_set()) and self.client_bl._send_message({"cmd": "rename", "type": "folder","name": new_name, "id": self.folder_id}):
            response = self.client_bl._get_message()
            if response and response["status"]:
                self.folder_name = new_name
            else:
                self.folder_entry.configure(text=self.folder_name)
        self.folder_entry.configure(state="disabled", border_width=0)

        self.main_frame.upload_button.configure(state="normal")
        self.main_frame.create_folder_button.configure(state="normal")

    def _on_cancel(self, event=None):
        """Cancel folder rename."""
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, self.folder_name)
        self.folder_entry.configure(state="disabled", border_width=0)

        self.main_frame.upload_button.configure(state="normal")
        self.main_frame.create_folder_button.configure(state="normal")

    def on_click_delete(self, event=None):
        """Handle folder deletion."""
        if self.client_bl.work_event.is_set():
            return
        threading.Thread(target=self.client_bl.delete_folder(
            self,
            self.main_frame.folder_rows,
            header_field=self.main_frame.header,
            bar=self.main_frame.progress_bar
        )).start()
        self.main_frame.upload_button.configure(state="normal")
        self.main_frame.create_folder_button.configure(state="normal")

    # Hover handling
    def _bind_hover(self, *widgets: list[ctk.CTkFrame]):
        """Bind hover effects to widgets."""
        for widget in widgets:
            widget.bind("<Button-1>", lambda event: threading.Thread(target=self.on_click).start())
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        """Highlight folder on mouse enter."""
        self.configure(fg_color=self.hover_fg)

    def _on_leave(self, event=None):
        """Remove highlight on mouse leave."""
        self.configure(fg_color=self.default_fg)

if __name__ == "__main__":
    app = ctk.CTk()
    app.minsize(1100,700)
    main_frame = MainFrame(app,[])
    main_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
    app.mainloop()