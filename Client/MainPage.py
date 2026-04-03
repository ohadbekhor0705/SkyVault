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
from PIL import Image


def load_icon(path):
    img = Image.open(path)
    return ctk.CTkImage(img, img)

icons = {
    "folder": load_icon("./icons/folder.png"),
    "share": load_icon("./icons/share.png"),
    "edit": load_icon("./icons/edit.png"),
    "upload": load_icon("./icons/cloud_upload.png"),
    "delete": load_icon("./icons/delete.png"),
    "new_folder": load_icon("./icons/create_new_folder.png"),
    "download": load_icon("./icons/download.png"),
    "cloud_lock": load_icon("./icons/cloud_lock.png")
}
ctk.set_appearance_mode("light")
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
        self.folder_rows: dict[str, FolderRow] = {}


        self.FolderFrames = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.files_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.files_frame.columnconfigure(0, weight=1)
        self.FolderFrames.columnconfigure(0, weight=1)


        self.grid_columnconfigure(0, weight=0, minsize=275)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)
        
        self.selected_folder_id: str = ""

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
            image=icons["upload"],
            compound="right",
            command=self._on_click_Upload
        )
        self.create_folder_button = ctk.CTkButton(
            self,
            text="",
            image=icons["new_folder"],
            compound="right",
            font = ctk.CTkFont(size=20),
            command=self.on_click_create_folder
        )
        self.progress_bar = ctk.CTkProgressBar(self)

        self.progress_bar.grid(row=1, column=0, sticky="nsew",pady=9,padx=9, columnspan=2)
        self.upload_button.grid(row=2, column=1, sticky="nsew",pady=9,padx=9)
        self.create_folder_button.grid(row=2, column=0, sticky="nsew",pady=9,padx=9)
        self.FolderFrames.grid(row=3, column=0, sticky="nsew",pady=7,padx=9)
        self.files_frame.grid(row=3, column=1, sticky="nsew", padx=3,pady=7)

        # if client_bl:
        #     self.progress_bar.set(self.client_bl.current_storage/self.client_bl.max_storage)
        #     for i, f in enumerate(client_bl.files):
        #         row = FileRow(
        #             self.files_frame,
        #             f["file_id"],
        #             f["filename"],
        #             f["size"],
        #             str(datetime.fromtimestamp(f["modified"]).date()),
        #             f["file_hash"],
        #             bool(f["share_link"]),
        #             self.client_bl, 
        #             on_delete=self.make_delete_callback(f["file_id"],f["size"] , None),  # placeholder row, will fix below
        #             on_save=self.make_save_callback(f["file_id"], f["filename"]),
        #             on_share=None
        #         )

        #         # Fix the row references in the callback after row is created
        #         row.on_delete = self.make_delete_callback(f["file_id"],f["size"], row)
        #         row.on_share= self.make_share_callback(row)

        #         row.grid(row=i+3, column=0, sticky="nsew", padx=12, pady=6)
        #         self.file_rows.append(row)

        if client_bl:
            self.progress_bar.set(self.client_bl.current_storage/self.client_bl.max_storage)
            for i, f in enumerate(self.client_bl.folders):
                folder_row = FolderRow(self.FolderFrames,self, f["folder_name"],f["folder_id"],self.client_bl, bool(f["root"]))
                folder_row.grid(column=0, row=i, sticky= "nsew", padx=5, pady=5)
                self.folder_rows[folder_row.folder_id] = folder_row
                if f["root"]:
                    self.selected_folder_id = f["folder_id"]
        # else:
        #     for i in range(15):
        #         folder_row = FolderRow(self.FolderFrames,self, "folder_name",f"{i}",self.client_bl, i == 0)
        #         folder_row.grid(column=0, row=i, sticky= "nsew", padx=12, pady=6)
        #         self.folder_rows[folder_row.folder_id] = folder_row
        #         if i == 0:
        #             self.selected_folder_id = "0"

            
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
                    self.selected_folder_id,
                    [self.make_delete_callback, self.make_save_callback, self.make_share_callback],
                    header_field=res_text,
                    parent=self.files_frame,
                    animate=self.animate,
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
                bar=self.progress_bar
            )
            # Remove row from UI
            row.grid_forget()
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
    
    def on_click_create_folder(self):
        if self.client_bl.work_event.is_set():
            return
        if self.client_bl._send_message({"cmd": "create_folder"}):
            response = self.client_bl._get_message()
            if response["status"]:
                new_folder = FolderRow(self.FolderFrames, self,"", response["folder_id"], self.client_bl, False)
                self.folder_rows[response["folder_id"]] = new_folder
                new_folder.grid(column=0, row = self.FolderFrames.grid_size()[1],sticky= "nsew", padx=5, pady=7)
                new_folder._on_double_click()
    def clear_file_rows(self):
        for file_row in self.files_frame.grid_slaves():
            file_row.destroy()
    def animate(self):
        dots = [i*"." for i in range(7)]
        for c in itertools.cycle(dots):
            if self.client_bl.work_event.is_set():
                self.header.configure(text=c)
                sleep(0.5)
            else: break


class FolderRow(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkScrollableFrame,main_frame: MainFrame, folder_name: str,folder_id: str, client_bl: CClientBL, is_root: bool = False, **kwargs):
        
        super().__init__(master,**kwargs)
        self.client_bl = client_bl
        self.is_root = is_root
        #self.file_rows: list[FileRow] = []
        self.folder_name = folder_name
        self.root = master

        self.main_frame = main_frame
        self.folder_id = folder_id
        self.default_fg = self.cget("fg_color")
        self.hover_fg = ("#cfcfcf", "#3a3a3a")
        # self.columnconfigure(0,weight=1)
        self.columnconfigure(1,weight=1)

        Padx = 12
        Pady = 6

        self.folder_entry = ctk.CTkEntry(self, border_width=0, font=ctk.CTkFont("Arial",20), fg_color="transparent")
        self.image_label = ctk.CTkLabel(self, image=icons["cloud_lock"] if self.is_root else icons["folder"],text="")
        self.folder_entry.insert(0, folder_name)
        self.folder_entry.configure(state="disabled")

        self.folder_entry.grid(row=0,column=0, sticky="nsew" ,padx=Padx,pady=Pady)
        self.image_label.grid(row=0,column=1,sticky="e" ,padx=Padx,pady=Pady)

        

        self.bind("<Button-1>", lambda event: threading.Thread(target=self.on_click).start())
        if not self.is_root:
            self.folder_entry.bind("<Double-Button-1>", self._on_double_click)
            self.folder_entry.bind("<Return>", self._on_send)
            self.folder_entry.bind("<Escape>", self._on_cancel)

        self.configure(corner_radius=15)

        for w in (self.folder_entry, self.image_label):
            self._bind_hover(w)

    def on_click(self, event=None):
        prev: FolderRow = self.main_frame.folder_rows[self.main_frame.selected_folder_id]
        prev.configure(border_width=0)
        prev._on_cancel()
        self.main_frame.clear_file_rows()
        self.main_frame.selected_folder_id = self.folder_id
        print(self.main_frame.selected_folder_id)
        self.configure(border_width = 4, border_color=("gray75", "gray25"))

        file_rows = self.client_bl.get_files_data(
            self.folder_id,
            self.main_frame.files_frame,
            [
                self.main_frame.make_delete_callback,
                self.main_frame.make_save_callback,
                self.main_frame.make_share_callback
            ]
        )

        for i, file_rows in enumerate(file_rows):
            file_rows.grid(row=i, column=0, padx=12,pady=6, sticky="nsew")
  
    def _on_double_click(self, event=None):
        self.main_frame.upload_button.configure(state="disabled")
        self.main_frame.create_folder_button.configure(state="disabled")
        self.folder_entry.configure(state="normal", border_width=2)
        self.folder_entry.focus()
    
    def _on_send(self, event):
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
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, self.folder_name)
        self.folder_entry.configure(state="disabled", border_width=0)

        self.main_frame.upload_button.configure(state="normal")
        self.main_frame.create_folder_button.configure(state="normal")

    # Hover handling
    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Button-1>", self.on_click)

    def _on_enter(self, event=None):
        self.configure(fg_color=self.hover_fg)

    def _on_leave(self, event=None):
        self.configure(fg_color=self.default_fg)

if __name__ == "__main__":
    app = ctk.CTk()
    app.minsize(1100,700)
    main_frame = MainFrame(app,[])
    main_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
    app.mainloop()