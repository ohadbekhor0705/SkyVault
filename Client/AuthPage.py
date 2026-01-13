import customtkinter as ctk
from typing import Callable, Optional
from CClientBL import CClientBL
import threading
class AuthFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_login: Optional[Callable[[str, str], None]] = None,
        on_register: Optional[Callable[[str, str], None]] = None,
        on_back_home: Optional[Callable[[], None]] = None,
        frames: dict[str, ctk.CTkFrame] = {},
        client_bl: CClientBL = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_login = on_login
        self.on_register = on_register
        self.on_back_home = on_back_home
        self.mode = "login"
        self.frames = frames
        self.frames["Auth"] = self
        self.client_bl = client_bl

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Center panel
        self.panel = ctk.CTkFrame(self, corner_radius=20, fg_color="gray20")
        self.panel.grid(row=0, column=0, sticky="nsew", padx=400, pady=100)

        # Increased row count to (0-6) to accommodate the message label
        self.panel.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)
        self.panel.grid_columnconfigure(0, weight=1)

        # Title
        self.title_label = ctk.CTkLabel(
            self.panel, text="Login", font=ctk.CTkFont(size=42, weight="bold")
        )
        self.title_label.grid(row=0, column=0, pady=(30, 15))

        # Username & Password
        self.username_entry = ctk.CTkEntry(
            self.panel, placeholder_text="Username", font=ctk.CTkFont(size=20), height=50
        )
        self.username_entry.grid(row=1, column=0, padx=60, pady=12, sticky="ew")

        self.password_entry = ctk.CTkEntry(
            self.panel, placeholder_text="Password", font=ctk.CTkFont(size=20), show="•", height=50
        )
        self.password_entry.grid(row=2, column=0, padx=60, pady=12, sticky="ew")

        # ----------------------------
        # NEW: Response Message Label
        # ----------------------------
        self.message_label = ctk.CTkLabel(
            self.panel,
            text="",  # Starts empty
            font=ctk.CTkFont(size=14),
            text_color="indianred1" # Reddish color for visibility
        )
        self.message_label.grid(row=3, column=0, pady=(5, 5))

        # Submit button (Moved to row 4)
        self.submit_button = ctk.CTkButton(
            self.panel,
            text="Login",
            font=ctk.CTkFont(size=20, weight="bold"),
            height=60,
            command=lambda: threading.Thread(target=self._submit).start()
        )
        self.submit_button.grid(row=4, column=0, padx=80, pady=(15, 10), sticky="ew")

        # Toggle Button (Moved to row 5)
        self.switch_button = ctk.CTkButton(
            self.panel,
            text="Create an account",
            font=ctk.CTkFont(size=16),
            fg_color="transparent",
            hover=False,
            command=self._switch_mode
        )
        self.switch_button.grid(row=5, column=0, pady=(5, 5))

        # Back to Home (Moved to row 6)
        self.back_home_button = ctk.CTkButton(
            self.panel,
            text="Back to Home",
            font=ctk.CTkFont(size=16),
            fg_color="transparent",
            hover=False,
            command=self._go_home
        )
        self.back_home_button.grid(row=6, column=0, pady=(5, 30))

        self._apply_mode()

    def _switch_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self.message_label.configure(text="") # Clear message on switch
        self._apply_mode()

    def _apply_mode(self):
        is_register = self.mode == "register"
        self.title_label.configure(text="Register" if is_register else "Login")
        self.submit_button.configure(text="Register" if is_register else "Login")
        self.switch_button.configure(
            text="Back to login" if is_register else "Create an account"
        )

    def _submit(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.message_label.configure(text="Please fill in all fields", text_color="indianred1")
            return 

        # Call BL
        response = self.client_bl.connect(username, password, self.mode)
        if response["status"]:
            # Success
            self.message_label.configure(text="Success!", text_color="lightgreen")
            self.frames["Main"].tkraise()
        else:
            # Failure - Display the message returned from the BL
            error_msg = response["message"]
            self.message_label.configure(text=error_msg, text_color="indianred1")

    def _go_home(self):
        if self.on_back_home:
            self.on_back_home()