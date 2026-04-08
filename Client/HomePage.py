import customtkinter as ctk
from typing import Callable, Optional
from threading import Thread

class HomePage(ctk.CTkFrame):

    def __init__(
        self,
        master,
        client_bl,
        on_authenticate: Optional[Callable[[], None]] = None,
        frames: dict[str, ctk.CTkFrame] = {},
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.client_bl = client_bl
        self.frames = frames

        # Callback injected by the application controller
        self.on_authenticate = on_authenticate

        # Allow this frame to expand fully
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Wrapper frame for global padding and future theming
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=40,
            pady=30
        )

        # Single-column layout, centered
        root.grid_columnconfigure(0, weight=1)

        # HERO SECTION (Top branding & CTA)
        hero = ctk.CTkFrame(root, fg_color="transparent")
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 40))
        hero.grid_columnconfigure(0, weight=1)

        # Primary heading 
        ctk.CTkLabel(
            hero,
            text="Welcome to SkyVault",
            font=ctk.CTkFont(size=44, weight="bold")
        ).grid(row=0, column=0, pady=(20, 10))

        # Subtitle / value proposition
        ctk.CTkLabel(
            hero,
            text=(
                "Secure. Fast. Always available.\n"
                "Your cloud, your control."
            ),
            font=ctk.CTkFont(size=18),
            text_color=("gray30", "gray70"),
            justify="center"
        ).grid(row=1, column=0, pady=(0, 30))

        # Call-to-action buttons

        cta_row = ctk.CTkFrame(hero, fg_color="transparent")
        cta_row.grid(row=2, column=0)

        # Primary action: authentication
        self.auth_button = ctk.CTkButton(
            cta_row,
            text="Sign in / Create account",
            width=260,
            height=48,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._go_auth,
            state="disabled"
        )
        self.auth_button.grid(row=0, column=0, padx=10)

        # Secondary action (non-blocking)
        ctk.CTkButton(
            cta_row,
            text="Learn more",
            width=180,
            height=48,
            fg_color="transparent",
            border_width=2
        ).grid(row=0, column=1, padx=10)

        # FEATURES SECTION (3-column layout)

        features = ctk.CTkFrame(root)
        features.grid(row=1, column=0, sticky="ew", pady=(0, 40))

        # Each column expands equally
        features.grid_columnconfigure((0, 1, 2), weight=1)

        # Feature cards (created via helper method)
        self._feature(
            features,
            col=0,
            icon="☁️",
            title="Cloud Storage",
            text="Access your files from anywhere, on any device."
        )

        self._feature(
            features,
            col=1,
            icon="🔒",
            title="Secure by Design",
            text="End-to-end encryption keeps your data safe."
        )

        self._feature(
            features,
            col=2,
            icon="⚡",
            title="Fast & Reliable",
            text="Optimized transfers and high availability."
        )

        # FOOTER (low visual priority)

        footer = ctk.CTkFrame(root, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer,
            text="SkyVault © 2026 • Version 1.0",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        ).grid(row=0, column=0, pady=10)

        self._process_tcp_connection()
        

    # Feature card factory

    def _feature(self, parent, col, icon, title, text):
        """
        Creates a reusable feature card.
        """

        frame = ctk.CTkFrame(parent, corner_radius=12)
        frame.grid(
            row=0,
            column=col,
            padx=15,
            pady=20,
            sticky="nsew"
        )

        # Icon (emoji keeps things simple and cross-platform)
        ctk.CTkLabel(
            frame,
            text=icon,
            font=ctk.CTkFont(size=36)
        ).pack(pady=(20, 10))

        # Feature title
        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(0, 6))

        # Feature description
        ctk.CTkLabel(
            frame,
            text=text,
            font=ctk.CTkFont(size=14),
            text_color=("gray30", "gray70"),
            wraplength=260,
            justify="center"
        ).pack(padx=20, pady=(0, 20))

    # Action handlers

    def _go_auth(self):
        """
        Emit intent to authenticate.
        Navigation is handled by the app controller.
        """
        if self.on_authenticate:
            self.on_authenticate(
            )
    def _process_tcp_connection(self) -> None: 
        self.auth_button.configure(state="disabled")
        Thread(target=lambda: self.client_bl._process_handshake(auth_button=self.auth_button)).start()

if __name__ == "__main__":
    app = ctk.CTk()
    home_page = HomePage(app)
    home_page.place(relx=0, rely=0, relwidth=1, relheight=1)
    app.mainloop()