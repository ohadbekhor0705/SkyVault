import customtkinter as CTk
from tkinter import ttk
from CServerBL import CServerBL
import threading
from protocol2 import *
class CServerGUI(CServerBL):
    def __init__(self) -> None:
        super().__init__()
        CTk.set_appearance_mode("Dark")
        self.master = CTk.CTk()
        self.FONT: tuple[str, int] = ("Helvetica",24)
        self._ipLabel = None
        self._portLabel = None
        self.serverSwitch = None
        self.height, self.width = 750, 1300
        self.create_ui()   
    
    def create_ui(self) -> None:
        self.master.geometry(f"{self.width}x{self.height}")
        self.master.resizable(False, False)
        self.master.title("Server GUI")

        CTk.CTkLabel(self.master, text= "Server Graphical User Interface",anchor="center",font=self.FONT).place(relx = 0, rely=0.1, relheight=0.06, relwidth=1)

        self.serverSwitch = CTk.CTkSwitch(self.master, variable=CTk.StringVar(value="off"),switch_width=250,switch_height=50, text= "Toggle on/off",
                                          font=self.FONT,onvalue="on", offvalue="off", command=self.toggle_server )
        self.serverSwitch.place(relx = 0.05, rely = 0.25)

        self.logger_box = CTk.CTkTextbox(self.master,font=("consolas",12),text_color="#34AA4E")
        self.logger_box.place(relx=0.05, rely=0.34,relheight=0.6,relwidth=0.9)
    
    def toggle_server(self) -> None:
        if self.serverSwitch.get() == "on":
            self.write_to_log("on")
            self.main_thread = threading.Thread(target=self.start_server, daemon=True)
            self.main_thread.start()
        if self.serverSwitch.get() == "off":
            self.write_to_log("off")
            self.stop_server()

    def run(self) -> None:
        self.master.mainloop()


if __name__ == "__main__":
    App = CServerGUI()
    App.run()
    App.stop_server()