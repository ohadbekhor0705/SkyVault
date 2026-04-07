import customtkinter as ctk
import threading
import sys
from CServerBL import CServerBL
class ServerApp(ctk.CTk):
    def __init__(self, server_bl):
        super().__init__()
        
        self.server_bl = server_bl
        
        # Window configuration
        self.title("Secure File Server - Control Panel")
        self.geometry("700x450")
        self.minsize(500, 300)
        
        # Grid layout (1 column, 2 rows)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Top Frame: Controls ---
        self.controls_frame = ctk.CTkFrame(self, corner_radius=10)
        self.controls_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        # Start Button
        self.start_btn = ctk.CTkButton(
            self.controls_frame, 
            text="Start Server", 
            fg_color="green", 
            hover_color="darkgreen",
            command=self.start_server_thread
        )
        self.start_btn.pack(side="left", padx=20, pady=15)

        # Stop Button
        self.stop_btn = ctk.CTkButton(
            self.controls_frame, 
            text="Stop Server", 
            fg_color="red", 
            hover_color="darkred",
            state="disabled",
            command=self.stop_server
        )
        self.stop_btn.pack(side="left", padx=0, pady=15)

        # --- Bottom Frame: Logging ---
        self.log_frame = ctk.CTkFrame(self, corner_radius=10)
        self.log_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        self.log_label = ctk.CTkLabel(self.log_frame, text="Server Logs", font=ctk.CTkFont(weight="bold"))
        self.log_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        # Textbox acting as logger_box
        self.log_box = ctk.CTkTextbox(self.log_frame, wrap="word", state="normal")
        self.log_box.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Attach the textbox to the BL's logger attribute
        # We override the default insert to also auto-scroll to the bottom
        self.server_bl.logger_box = self

        # Handle window closure gracefully
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def insert(self, index, text):
        """
        Wrapper method to satisfy self.logger_box.insert("end", msg) in CServerBL.
        It writes to the CTkTextbox and auto-scrolls to the latest message.
        """
        self.log_box.insert(index, text)
        self.log_box.see("end")  # Auto-scroll

    def start_server_thread(self):
        """Starts the server in a daemon thread to prevent freezing the GUI loop."""
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        # Run start_server in the background
        self.server_thread = threading.Thread(target=self.server_bl.start_server, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        """Stops the server and resets the UI buttons."""
        self.stop_btn.configure(state="disabled")
        
        # Call the BL stop method
        self.server_bl.stop_server()
        
        self.start_btn.configure(state="normal")

    def on_closing(self):
        """Ensures sockets and threads are cleaned up when clicking the 'X'."""
        self.server_bl.stop_server()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    # CustomTkinter Theme Settings
    ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
    ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

    # Initialize Business Logic
    backend = CServerBL()

    # Initialize and run GUI
    app = ServerApp(backend)
    app.mainloop()