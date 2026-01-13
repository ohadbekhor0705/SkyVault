import customtkinter as ctk
from CClientBL import CClientBL
from AuthPage import AuthFrame
from HomePage import HomePage
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SkyVault")
        self.client_bl = CClientBL()
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
            on_login=lambda u, p: print("Login:", u),
            on_register=lambda u, e, p: print("Register:", u),
            on_back_home=lambda: self.home.tkraise(),
            frames=self.frames,
            client_bl = self.client_bl
        )

        for page in (self.home, self.auth):
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.home.tkraise()
app = App()
app.mainloop()