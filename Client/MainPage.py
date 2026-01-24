import itertools
from time import sleep
from typing import Callable
from CClientBL import CClientBL
import customtkinter as ctk
from FileRow import FileRow
import threading
from tkinter import filedialog as fd
class MainFrame(ctk.CTkScrollableFrame):
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
        # Allow this frame to expand fully
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.header = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=20)
        )
        self.header.grid(row=0, column=0, sticky="nsew")
        self.upload_button = ctk.CTkButton( # Upload button
            self,
            text="Upload File",
            font= ctk.CTkFont(size=20),
            command=self._on_click_Upload
        )
        self.upload_button.grid(row=1, column=0, sticky="nsew")

        if client_bl:
            for i, f in enumerate(client_bl.files):
                row = FileRow(
                    self,
                    f["file_id"],
                    f["filename"],
                    f["size"],
                    f["modified"],
                    on_delete=self.make_delete_callback(f["file_id"], None),  # placeholder row, will fix below
                    on_save=self.make_save_callback(f["file_id"], f["filename"]),
                    on_share=None
                )

                # Fix the row reference in the callback after row is created
                row.on_delete = self.make_delete_callback(f["file_id"], row)

                row.grid(row=i+2, column=0, sticky="nsew", padx=5, pady=2)
                self.file_rows.append(row)
    def _on_click_Upload(self) -> None:
        # if other tasks are running then prevent from user from sending other network requests
        if self.client_bl._operation_thread  and self.client_bl._operation_thread.is_alive():
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
                    parent=self,
                    animate=self.animate,
                    file_rows = self.file_rows
                )
            )
            self.client_bl._operation_thread.start()
        else:
            self.header.configure(text="File not found! Please select a file again.")
            
    def make_delete_callback(self,file_id: str, row: FileRow) -> Callable[[], None]:
        # Define a wrapper for delete to remove row from UI
        def callback():
            # Call business logic
            self.client_bl.delete_files([file_id],header_field=self.header, file_rows=self.file_rows)
            # Remove row from UI
            row.grid_forget()
            # Optionally remove from list
            self.file_rows.remove(row)
        return lambda: threading.Thread(target=callback).start()
    def make_save_callback(self,file_id: str, filename: str):
        def callback():
            self.client_bl.work_event.set()
            threading.Thread(target=self.animate).start()
            self.client_bl.ReceiveFile(file_id,filename, header_field=self.header)
        return lambda: threading.Thread(target=callback).start()
    def make_share_callback(self, file_id: str):
        def callback():
            ...
        return None
        
    def animate(self):
        dots = [i*"." for i in range(7)]
        for c in itertools.cycle(dots):
            if self.client_bl.work_event.is_set():
                self.header.configure(text=c)
                sleep(0.5)
            else: break
