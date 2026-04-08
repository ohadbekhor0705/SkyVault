import itertools
import socket
from time import sleep
from typing import Callable, NoReturn
from CClientBL import CClientBL
import customtkinter as ctk
from FileRow import FileRow
import threading
from tkinter import filedialog as fd
import pyperclip
from datetime import datetime, date
from PIL import Image


def load_icon(path, size: tuple[int, int] = (20,20)):
    img = Image.open(path)
    return ctk.CTkImage(img, img, size)

icons: dict[str, ctk.CTkImage] = {
    "upload": load_icon("./icons/cloud_upload.png"),
    "delete": load_icon("./icons/delete.png"),
    "new_folder": load_icon("./icons/create_new_folder.png"),
    "cloud_lock": load_icon("./icons/cloud_lock.png"),
    "logout": load_icon("./icons/logout.png",size=(15,15))
}
ctk.set_appearance_mode("light")
ctk.FontManager.load_font("./fonts/Arial-VariableFont_wght.ttf")

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


        self.folders_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.files_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.files_frame.columnconfigure(0, weight=1)
        self.folders_frame.columnconfigure(0, weight=1)


        self.grid_columnconfigure(0, weight=0, minsize=275)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)
        
        self.selected_folder_id: str = ""
        self._disconnect_button = ctk.CTkButton(
            self,
            text="Logout",
            fg_color="red",
            hover_color=None,
            text_color="white",
            image=icons["logout"],
            font=ctk.CTkFont("Outfit",15),
            command=self.on_click_logout
        )
        self._disconnect_button.grid(row=0, column=0, sticky="e", pady=9,padx=9, columnspan=2)

        self.header = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont("Outfit",20)
        )
        self.header.grid(row=1, column=0, sticky="ew", pady=9,padx=9, columnspan=2)
        
        self.upload_button = ctk.CTkButton( # Upload button
            self,
            text="Upload File",
            font= ctk.CTkFont("Arial",20),
            image=icons["upload"],
            compound="right",
            command=self._on_click_Upload
        )
        self.create_folder_button = ctk.CTkButton(
            self,
            text="",
            image=icons["new_folder"],
            compound="right",
            font = ctk.CTkFont("Outfit",20),
            command=self.on_click_create_folder
        )
        self.progress_bar = ctk.CTkProgressBar(self)

        self.progress_bar.grid(row=2, column=0, sticky="nsew",pady=9,padx=9, columnspan=2)
        self.upload_button.grid(row=3, column=1, sticky="nsew",pady=9,padx=9)
        self.create_folder_button.grid(row=3, column=0, sticky="nsew",pady=9,padx=9)
        self.folders_frame.grid(row=4, column=0, sticky="nsew",pady=7,padx=9)
        self.files_frame.grid(row=4, column=1, sticky="nsew", padx=3,pady=7)


        if client_bl:
            self.progress_bar.set(self.client_bl.current_storage/self.client_bl.max_storage)
            for i, f in enumerate(self.client_bl.folders):
                folder_row = FolderRow(self.folders_frame,self, f["folder_name"],f["folder_id"],self.client_bl, bool(f["root"]))
                folder_row.grid(column=0, row=i, sticky= "nsew", padx=12, pady=6)
                self.folder_rows[folder_row.folder_id] = folder_row
                if f["root"]:
                    self.selected_folder_id = f["folder_id"]
            
        threading.Thread(target=self.check_connection, daemon=True).start()


            
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
                row.has_share_link = not row.check_var.get()
                if action == "enable":
                    link = response["link"]
                    row.share_link = link
                    pyperclip.copy(link)
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
                folder_id: str = response["folder_id"]
                new_folder = FolderRow(self.folders_frame, self,"", folder_id, self.client_bl, False)
                self.folder_rows[folder_id] = new_folder
                new_folder.grid(column=0, row = self.folders_frame.grid_size()[1],sticky= "nsew", padx=12, pady=6)
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
    def on_click_logout(self):
        self.client_bl._send_message({"cmd":"logout"})
        self.client_bl.work_event.set()
        if response := self.client_bl._get_message():
            if response["status"]:
                self.frames["Home"].tkraise()
                del self.frames["Main"]
                self.destroy()
                del self
    def check_connection(self) -> NoReturn:
        try:
            while True:
                print("checking connection....")
                if not self.client_bl.work_event.is_set():
                    self.client_bl._conn.send(b'')
                sleep(2.5)
        except (socket.error, ConnectionAbortedError, ConnectionError, ConnectionResetError):
            self.frames["Home"].tkraise()
            self.frames["Home"]._process_tcp_connection()
            del self.frames["Main"]
            self.destroy()
            del self
            


class FolderRow(ctk.CTkFrame):
    def __init__(self,
        master: ctk.CTkScrollableFrame,main_frame: MainFrame,
        folder_name: str ,folder_id: str,
        client_bl: CClientBL,
        is_root: bool = False,
        **kwargs
    ):
        
        super().__init__(master,**kwargs)
        self.client_bl = client_bl
        self.is_root = is_root
        #self.file_rows: list[FileRow] = []
        self.folder_name = folder_name if folder_name != "" else "unnamed"
        self.root = master

        self.main_frame = main_frame
        self.folder_id = folder_id
        self.default_fg = self.cget("fg_color")
        self.hover_fg = ("#cfcfcf", "#3a3a3a")
        # self.columnconfigure(0,weight=1)
        self.columnconfigure(1,weight=0, minsize=20)

        Padx = 12
        Pady = 6

        self.folder_entry = ctk.CTkEntry(self,
            border_width=0,
            font=ctk.CTkFont("Outfit",20),
            fg_color="transparent"
        )
        self.folder_entry.insert(0, folder_name)
        self.folder_entry.configure(state="disabled")

        self.folder_entry.grid(row=0,column=0, sticky="nsew" ,padx=Padx,pady=Pady)

        

        # self.bind("<Button-1>", lambda event: threading.Thread(target=self.on_click).start())
        if not self.is_root:
            self.delete_button = ctk.CTkButton(
                self,
                text="",
                image=icons["delete"],
                command=self.on_click_delete,
                width=20,
                fg_color="red"
            )
            self.delete_button.grid(row=0,column=1,sticky="nsew" ,padx=0,pady=Pady)

            self.folder_entry.bind("<Double-Button-1>", self._on_double_click)
            self.folder_entry.bind("<Return>", self._on_send)
            self.folder_entry.bind("<Escape>", self._on_cancel)

        self.configure(corner_radius=15)

        self._bind_hover(self.folder_entry)

    def on_click(self, event=None):
        if prev := self.main_frame.folder_rows.get(self.main_frame.selected_folder_id):
            if prev != self:
                prev.configure(border_width=0)
                prev._on_cancel()
        
        self.main_frame.clear_file_rows()
        self.main_frame.selected_folder_id = self.folder_id
        print(self.main_frame.selected_folder_id)
        self.configure(border_width = 4, border_color=("gray50", "gray75"), fg_color = "transparent")

        file_rows: list[FileRow] = self.client_bl.get_files_data(
            self.folder_id,
            self.main_frame.files_frame,[
                self.main_frame.make_delete_callback,
                self.main_frame.make_save_callback,
                self.main_frame.make_share_callback
            ],
            header_field = self.main_frame.header,
            animate = self.main_frame.animate
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

    def on_click_delete(self, event=None):
        threading.Thread(target=self.client_bl.delete_folder(
            self,
            self.main_frame.folder_rows,
            header_field=self.main_frame.header,
            bar=self.main_frame.progress_bar
        )).start()


    # Hover handling
    def _bind_hover(self, *widgets: list[ctk.CTkFrame]):
        for widget in widgets:
            widget.bind("<Button-1>", lambda event: threading.Thread(target=self.on_click).start())
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

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