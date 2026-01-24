import customtkinter as ctk
from CClientBL import CClientBL
from AuthPage import AuthFrame
from HomePage import HomePage

ctk.set_appearance_mode("dark")
class App(ctk.CTk):
    def __init__(self, client_bl: CClientBL):
        super().__init__()
        print("Initializing App")
        self.title("SkyVault")
        self.minsize(1300,750)
        self.client_bl: CClientBL = client_bl
        self.frames: dict[str, ctk.CTkFrame] = {}
        try:
            self.state("zoomed")
        except:
            self.attributes("-zoomed", True)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(self)
        container.grid(row=0, column=0, sticky="nsew")

        self.home = HomePage(
            container,
            on_authenticate=lambda: self.auth.tkraise(),
            corner_radius=0,
            frames=self.frames,
        )

        self.auth = AuthFrame(
            container,
            on_back_home=lambda: self.home.tkraise(),
            frames=self.frames,
            client_bl = self.client_bl
        )
        self.frames["Home"] = self.home        
        self.frames["Auth"] = self.auth
        for page in (self.home, self.auth):
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.home.tkraise()
if __name__ == "__main__": 
    client_bl = CClientBL()
    client_bl.process_handshake()
    app = App(client_bl)
    app.mainloop()