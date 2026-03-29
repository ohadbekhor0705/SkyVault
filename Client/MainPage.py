import itertools
from time import sleep
from typing import Callable
from CClientBL import CClientBL
import customtkinter as ctk
from FileRow import FileRow
import threading
from tkinter import filedialog as fd
import pyperclip
from datetime import datetime, date
class MainFrame(ctk.CTkFrame):
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
        self.file_rows: list[FileRow] = [] # Keep track of rows for future access
        # Allow this frame to expand fully``


        self.FolderFrames = ctk.CTkScrollableFrame(self)
        self.files_frame = ctk.CTkScrollableFrame(self)
        self.files_frame.columnconfigure(0, weight=1)


        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.header = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=20)
        )
        self.header.grid(row=0, column=0, sticky="ew", pady=9,padx=9, columnspan=2)
        self.upload_button = ctk.CTkButton( # Upload button
            self,
            text="Upload File",
            font= ctk.CTkFont(size=20),
            command=self._on_click_Upload
        )
        self.create_folder_button = ctk.CTkButton(
            self,
            text="create folder",
            font = ctk.CTkFont(size=20)
        )
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=1, column=0, sticky="nsew",pady=9,padx=9, columnspan=2)
        self.upload_button.grid(row=2, column=1, sticky="nsew",pady=9,padx=9)
        self.create_folder_button.grid(row=2, column=0, sticky="nsew",pady=9,padx=9)
        self.FolderFrames.grid(row=3, column=0, sticky="nsew", padx=7,pady=7)
        for i in range(15):
            ctk.CTkLabel(self.FolderFrames, text="Folder").grid(column=0,row=i)
        self.files_frame.grid(row=3, column=1, sticky="nsew", padx=7,pady=7)
        if client_bl:
            self.progress_bar.set(self.client_bl.current_storage/self.client_bl.max_storage)
            for i, f in enumerate(client_bl.files):
                row = FileRow(
                    self.files_frame,
                    f["file_id"],
                    f["filename"],
                    f["size"],
                    str(datetime.fromtimestamp(f["modified"]).date()),
                    f["file_hash"],
                    bool(f["share_link"]),
                    self.client_bl, 
                    on_delete=self.make_delete_callback(f["file_id"],f["size"] , None),  # placeholder row, will fix below
                    on_save=self.make_save_callback(f["file_id"], f["filename"]),
                    on_share=None
                )

                # Fix the row references in the callback after row is created
                row.on_delete = self.make_delete_callback(f["file_id"],f["size"], row)
                row.on_share= self.make_share_callback(row)

                row.grid(row=i+3, column=0, sticky="nsew", padx=12, pady=6)
                self.file_rows.append(row)
    def _on_click_Upload(self) -> None:
        # if other tasks are running then prevent from user from sending other network requests
        if self.client_bl.work_event.is_set():
            print("Another task is running!")
            return 
        filename: str = fd.askopenfilename(
        title="Open a file",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            f = open(filename,"rb")
            res_text = self.header
            self.client_bl._operation_thread = threading.Thread(
                target=lambda: self.client_bl.sendfile(
                    f,
                    [self.make_delete_callback, self.make_save_callback, self.make_share_callback],
                    header_field=res_text,
                    parent=self.files_frame,
                    animate=self.animate,
                    file_rows = self.file_rows,
                    bar = self.progress_bar
                )
            )
            self.client_bl._operation_thread.start()
        else:
            self.header.configure(text="File not found! Please select a file again.")
    def make_delete_callback(self,file_id: str, size: int, row: FileRow) -> Callable[[], None]:
        # Define a wrapper for delete to remove row from UI
        def callback():
            if self.client_bl.work_event.is_set():
                return
            self.client_bl.work_event.set()
            threading.Thread(target=self.animate).start()
            # Call business logic
            self.client_bl.delete_file(
                file_id,
                size,
                header_field=self.header,
                file_rows=self.file_rows,
                bar=self.progress_bar
            )
            # Remove row from UI
            row.grid_forget()
            # Optionally remove from list
            self.file_rows.remove(row)
        return lambda: threading.Thread(target=callback).start()
    def make_save_callback(self,file_id: str, filename: str):
        def callback():
            if self.client_bl.work_event.is_set():
                return
            save_path = fd.askdirectory(title=f"Choose a path to save {filename}.")
            self.client_bl.work_event.set()
            threading.Thread(target=self.animate).start()
            self.client_bl.ReceiveFile(file_id,filename,save_path, header_field=self.header)
        return lambda: threading.Thread(target=callback).start()
    def make_share_callback(self,row: FileRow):
        def callback():
            if self.client_bl.work_event.is_set():
                return
            print(f"{row.check_var.get()=}")
            action = "enable" if row.check_var.get() else "disable"
            print(action)
            self.client_bl._send_message({"cmd": "handlelink", "action": action,"file_id": row.file_id})
            response = self.client_bl._get_message()
            if response["status"]:
                row.share_link = not row.check_var.get()
                if action == "enable":
                    pyperclip.copy(response["link"])
            else:
                row.check_var.set(not row.check_var.get())
            self.header.configure(text=response["message"])
            threading.Thread(target=self.animate).start()

        return lambda: threading.Thread(target=callback).start()   
    def animate(self):
        dots = [i*"." for i in range(7)]
        for c in itertools.cycle(dots):
            if self.client_bl.work_event.is_set():
                self.header.configure(text=c)
                sleep(0.5)
            else: break