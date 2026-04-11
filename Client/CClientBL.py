import io
import socket
from typing import Callable, Tuple, BinaryIO
import json
import struct
import os
from typing import Any, overload
from customtkinter import CTkScrollableFrame, CTkLabel
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography import fernet
import base64
import threading
from FileRow import FileRow
from time import sleep
from customtkinter import END
import hashlib

# Constants
CHUNK_SIZE = 1024 * 64  # Size of file chunks for transmission (64 KB)
FORMAT = "!I"  # Network byte order unsigned int for packet headers


class CClientBL():
    """Client Business Logic class handling server communication and file operations."""
    
    def __init__(self) -> None:
        """Initialize client with default settings and threading primitives."""
        self._conn: socket.socket | None = None  # Server connection socket
        self.connection_event = threading.Event()  # Event flag for connection status
        self._fernet: fernet.Fernet  # Encryption/decryption cipher

        # Storage information
        self.current_storage: int = 0  # Current storage used in bytes
        self.max_storage: int = 0  # Maximum storage allowed in bytes
        self.username: str = ""  # Authenticated username
        
        # Server connection details
        self.server_ip: str = "localhost"
        self.server_port: str = 7777
        
        # Work event to track ongoing operations
        self.work_event: threading.Event = threading.Event()

    def _process_handshake(self, **kwargs) -> None:
        """
        Perform SSL/TLS-like handshake with server to establish encrypted session.
        Exchanges public key and establishes Fernet cipher for symmetric encryption.
        """
        # Attempt connection with retry logic
        while True:
            try:
                print("Attempting to connect...")
                _client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                _client_socket.connect((self.server_ip, self.server_port))
                self._conn = _client_socket
                break
            except ConnectionRefusedError:
                print("Connection Has failed")
                _client_socket.close()
            sleep(0.5)

        # Receive server's public key
        key_len_recv = self._recv_exact(4)
        len_pem_public: int = struct.unpack(FORMAT, key_len_recv)[0]
        pem_public = self._recv_exact(len_pem_public)
        public_key = server_public_key = serialization.load_pem_public_key(pem_public)
        
        # Generate session key and encrypt it with server's public key
        raw_session_key = os.urandom(32)
        session_key = base64.urlsafe_b64encode(raw_session_key)
        encrypted_session_key = server_public_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Send encrypted session key to server
        _client_socket.sendall(struct.pack(FORMAT, len(encrypted_session_key)) + encrypted_session_key)
        self.fernet = fernet.Fernet(session_key)

        # Enable authentication button if provided
        if auth_button := kwargs.get("auth_button"):
            auth_button.configure(state="normal")

    def connect(self, username: str, password: str, cmd: str) -> dict[str, Any]:
        """
        Authenticate user with server credentials.
        
        Args:
            username (str): Username for authentication
            password (str): Password for authentication 
            cmd (str): Command to be sent to server
            
        Returns:
            dict[str, Any]: Response with status, message, and user data
        """
        global FORMAT
        try:
            # Create and encrypt authentication payload
            auth: dict[str, str] = {"username": username, "password": password, "cmd": cmd}
            print(auth)
            encrypted_auth = self.fernet.encrypt(json.dumps(auth).encode())
            self._conn.send(struct.pack(FORMAT, len(encrypted_auth)) + encrypted_auth)
            
            # Receive and decrypt authentication response
            response_length: bytes = self._conn.recv(4)
            response_bytes_encrypted: bytes = self._conn.recv(struct.unpack(FORMAT, response_length)[0])
            response: dict[str, Any] = json.loads(self.fernet.decrypt(response_bytes_encrypted).decode())
            print(response)
            
            # Store user data on successful authentication
            if response["status"] == True:
                self.connection_event.set()
                self.folders = response["folders"]
                self.username = auth["username"]
                self.current_storage = response["curr_storage"]
                self.max_storage = response["max_storage"]
                self._conn = self._conn
            return response
        except (ConnectionAbortedError, ConnectionError, ConnectionResetError):
            return {"status": False, "message": "Server Error"}

    def  get_files_data(self, folder_id: str, parent: CTkScrollableFrame, callbacks: list[Callable], **kwargs) -> list[FileRow]:
        """
        Retrieve files from specified folder and create FileRow UI elements.
        
        Args:
            folder_id (str): ID of folder to retrieve files from
            parent: Parent widget for FileRow elements
            callbacks: List of callback functions [on_delete, on_save, on_share]
            
        Returns:
            list[FileRow]: List of FileRow UI objects
        """
        self.work_event.set()
        animate: Callable | None = kwargs.get("animate")
        
        # Start animation in separate thread
        if animate: 
            threading.Thread(target=animate).start()
            
        header_field: CTkLabel | None = kwargs.get("header_field")
        try:
            # Request files from server
            self._send_message({"cmd": "get_files", "folder_id": folder_id})
            response = self._get_message()
            file_rows: list[FileRow] = []
            
            if response["status"]:
                files_data = response["files"]
                print(len(files_data))
                
                # Create FileRow UI elements for each file
                for i, file_data in enumerate(files_data):
                    file_row = FileRow(
                        parent,
                        file_data["file_id"],
                        file_data["filename"],
                        file_data["size"],
                        str(datetime.fromtimestamp(file_data["modified"]).date()),
                        file_data["file_hash"],
                        bool(file_data["share_link"]),
                        self,
                        on_delete=callbacks[0](file_data["file_id"], file_data["size"], None),
                        on_save=callbacks[1](file_data["file_id"], file_data["filename"], file_data[""]),
                        on_share=None,
                    )
                    
                    # Update callbacks with row reference after creation
                    file_row.on_delete = callbacks[0](file_row.file_id, file_data["size"], file_row)
                    file_row.on_share = callbacks[2](file_row)
                    file_rows.append(file_row)
                    
        except (ConnectionAbortedError, ConnectionError, ConnectionResetError):
            if header_field:
                self.work_event.clear()
                header_field.configure(text="Something went wrong with the server! Couldn't retrieve data from the cloud", text_color="red")
        finally:
            self.work_event.clear()
            return file_rows

    def sendfile(self, file: BinaryIO, folder_id: int, callbacks: list[Callable], **kwargs) -> None:
        """
        Upload file to server in encrypted chunks.
        
        Args:
            file (BinaryIO): File object opened in binary read mode
            folder_id (int): Destination folder ID
            callbacks (list[Callable]): Callback functions for file operations
        """
        print("sendfile() started!")
        self.work_event.set()
        global FORMAT
        
        # Extract UI components
        header_field: CTkLabel = kwargs["header_field"]
        parent: CTkScrollableFrame = kwargs["parent"]
        bar = kwargs["bar"]
        header_field.configure(text_color="black")
        
        # Start animation thread
        animate_callback: Callable | None = kwargs.get("animate")
        if animate_callback:
            threading.Thread(target=animate_callback).start()

        # Check file size and available storage
        file_size: int = os.path.getsize(file.name)
        if file_size + self.current_storage > self.max_storage:
            header_field.configure(text="You dont't have enough storage to upload this file")
            self.work_event.clear()
            return
            
        # Compute file hash for integrity verification
        file_hash = self._hash_file(file)
        print(file_hash)
        
        # Prepare upload payload
        payload: dict[str, Any] = {
            "cmd": "upload",
            "filename": file.name.split("/")[-1],
            "folder_id": folder_id,
            "filesize": file_size,
            "hash": file_hash
        }
        
        try:
            self._send_message(payload)

            # Send file in chunks
            while chunk := file.read(CHUNK_SIZE):
                encrypted_chunk = self.fernet.encrypt(chunk)
                header = struct.pack(FORMAT, len(encrypted_chunk))
                self._conn.sendall(header + encrypted_chunk)
                
            # Send EOF marker
            self._conn.sendall(struct.pack(FORMAT, 0))
            file.close()

            # Receive server response
            response = self._get_message()
            print(response)
            if response["status"]:
                # Update storage and create new FileRow
                self.current_storage += file_size
                bar.set(self.current_storage / self.max_storage)
                header_field.configure(text=response["message"], text_color="green")
                
                last_row = parent.grid_size()[1]
                file_row = FileRow(
                    parent,
                    response["file_id"],
                    file.name.split("/")[-1],
                    file_size,
                    datetime.now().strftime("%Y-%m-%d"),
                    file_hash,
                    False,
                    self,
                    on_delete=callbacks[0](response["file_id"], file_size, None),
                    on_save=callbacks[1](response["file_id"], file.name.split("/")[-1], file_hash),
                    on_share=None,
                )

                # Update callbacks with row reference
                file_row.on_delete = callbacks[0](response["file_id"], file_size, file_row)
                file_row.on_share = callbacks[2](file_row)
                file_row.grid(row=last_row, column=0, sticky="ew", padx=12, pady=6)
                
        except (ConnectionResetError, ConnectionAbortedError, ConnectionError):
            header_field.configure(text="Something went wrong with the server! Couldn't fulfill the request.", text_color="red")
        except FileNotFoundError:
            header_field.configure(text="The selected file was not found. Please try again.", text_color="red")
        finally:
            self.work_event.clear()

    def _hash_file(self, file: BinaryIO, algorithm="sha256", return_to_start=True) -> str:
        """
        Compute hash digest of file for integrity verification.
        
        Args:
            file (BinaryIO): File object to hash
            algorithm (str): Hash algorithm (default: sha256)
            return_to_start (bool): Reset file pointer to start
            
        Returns:
            str: Hex digest of file hash
        """
        hasher = hashlib.new(algorithm)
        BLOCKSIZE = io.DEFAULT_BUFFER_SIZE
        
        # Read file in blocks and update hash
        for chunk in iter(lambda: file.read(BLOCKSIZE), b''):
            hasher.update(chunk)
            
        if return_to_start:
            file.seek(0)
        return hasher.hexdigest()

    def delete_file(self, file_id: str, size: int, **kwargs) -> dict[str, Any]:
        """
        Request deletion of file from server.
        
        Args:
            file_id (str): ID of file to delete
            size (int): Size of file in bytes
        """
        print(size, self.current_storage)
        self.work_event.set()
        header = kwargs["header_field"]
        bar = kwargs["bar"]
        
        # Send delete request
        payload = {"cmd": "delete", "type": "file", "id": file_id}
        self._send_message(payload)
        response = self._get_message()
        print(response)
        
        # Update storage if successful
        if response["status"]:
            self.current_storage -= size
            print(self.current_storage)
            bar.set(self.current_storage / self.max_storage)
        self.work_event.clear()

    def delete_folder(self, folder_row, folder_rows: dict, **kwargs) -> None:
        """
        Request deletion of folder from server.
        
        Args:
            folder_row: Folder UI element to delete
            folder_rows (dict): Dictionary of all folder rows
        """
        self.work_event.set()
        header_field: CTkLabel | None = kwargs.get("header_field")
        progress_bar: CTkLabel | None = kwargs.get("bar")
        
        try:
            # Send delete request
            self._send_message({"cmd": "delete", "type": "folder", "id": folder_row.folder_id})
            response = self._get_message()

            if not response:
                raise ConnectionError
                
            if response["status"]:
                # Update storage and remove folder from UI
                self.current_storage = response["current_storage"]
                del folder_rows[folder_row.folder_id]
                value = next(iter(folder_rows.values()))
                value.on_click()
                folder_row.destroy()
                del folder_row
            else:
                if header_field:
                    header_field.configure(text="The server could'nt this this folder", text_color="red")

        except (ConnectionAbortedError, ConnectionResetError, ConnectionError):
            if header_field:
                header_field.configure(text="Something went wrong with the server! Couldn't fulfill the request.", text_color="red")
            if progress_bar:
                progress_bar.set(self.current_storage / self.max_storage)
        finally:
            self.work_event.clear()

    def ReceiveFile(self, file_id: str, filename: str, save_path: str, file_hash, **kwargs) -> None:
        """
        Download encrypted file from server and verify integrity.
        
        Args:
            file_id (str): ID of file to download
            filename (str): Name to save file as
            save_path (str): Destination directory path
            file_hash: Expected hash for integrity verification
        """
        self.work_event.set()
        header_field: CTkLabel = kwargs["header_field"]
        
        # Request file from server
        self._send_message({"cmd": "save", "file_id": file_id})
        path = f"{save_path}/{filename}"
        
        try:
            # Receive and decrypt file chunks
            with open(path, "wb") as f:
                while True:
                    header: int = struct.unpack(FORMAT, self._recv_exact(4))[0]
                    if header == 0:  # EOF marker
                        break
                    decrypted: bytes = self.fernet.decrypt(self._recv_exact(header))
                    f.write(decrypted)
                    
            # Verify file integrity
            with open(f"{save_path}/{filename}", "rb") as f:
                saved_file_hash = self._hash_file(f)
                
            if saved_file_hash == file_hash:
                header_field.configure(text=f"file saved on: '/{save_path}/{filename}'", text_color="green")
            else:
                header_field.configure(text=f"{filename} seems corrupted!", text_color="orange")
                
        except (ConnectionAbortedError, ConnectionResetError):
            os.remove(path)
            header_field.configure(text="Something went wrong with the server! Couldn't fulfill the request.", text_color="red")
        finally:
            self.work_event.clear()

    @overload
    def _send_message(self, payload: str): ...

    @overload 
    def _send_message(self, payload: dict[str, Any]): ...

    def _send_message(self, payload: dict[str, Any] | str) -> bool:
        """
        Send encrypted message to server.
        
        Args:
            payload (dict[str,Any] | str): Data to encrypt and send
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"sending {payload}...")
            if isinstance(payload, str):
                # Encrypt string payload
                encrypted = self.fernet.encrypt(payload.encode())
                Header = struct.pack(FORMAT, len(encrypted))
                print(f"Header Length: {Header}")
                self._conn.sendall(Header + encrypted)
            elif isinstance(payload, dict):
                # Encrypt dictionary payload as JSON
                encrypted = self.fernet.encrypt(json.dumps(payload).encode())
                Header = struct.pack(FORMAT, len(encrypted))
                self._conn.sendall(Header + encrypted)
            else:
                raise ValueError(f"Type {type(payload)} isn't supported!")
        except (ConnectionResetError, ConnectionError):
            return False
        return True

    def _get_message(self) -> dict[str, Any] | None:
        """
        Receive and decrypt message from server.
        
        Returns:
            dict[str, Any]: Decrypted message from server, or None on error
        """ 
        try:
            # Receive message length and payload
            len_bytes: bytes = self._recv_exact(4)
            print(f"Received header: {struct.unpack(FORMAT, len_bytes)[0]}")
            encrypted_payload = self._recv_exact(struct.unpack(FORMAT, len_bytes)[0])
            return json.loads(self.fernet.decrypt(encrypted_payload).decode())
        except (ConnectionAbortedError, ConnectionResetError, ConnectionError):
            return None

    def _recv_exact(self, size: int) -> bytes:
        """
        Reliably receive exact number of bytes from socket.
        
        Args:
            size (int): Number of bytes to receive
            
        Returns:
            bytes: Received data
            
        Raises:
            ConnectionError: If socket closes unexpectedly
        """
        data = bytearray()
        while len(data) < size:
            packet = self._conn.recv(size - len(data))
            if not packet:
                raise ConnectionError("Socket closed unexpectedly")
            data.extend(packet)
        return bytes(data)
