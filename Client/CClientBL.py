import io
import platform
import socket
from typing import Tuple,BinaryIO
import json
import struct
import os
from typing import Any, overload
from customtkinter import CTkProgressBar, CTkLabel
from datetime import datetime
from tkinter.ttk import Treeview
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography import fernet
import base64
import threading
import subprocess
CHUNK_SIZE = 1024 * 64
FORMAT = "!I"
class CClientBL():
    def __init__(self) -> None:
        self.ADDR = ("127.0.0.1", 9999)
        
        self.conn: socket.socket | None = None
        self.user = {}
        self.connection_event = threading.Event()
        self.public_key: bytes
        self.session_key: bytes
        self.fernet: fernet.Fernet

        self.current_storage: int = 0
        self.max_storage: int = 0
        self.files: list[dict[str,Any]] = []
        self.username: str = ""
        self.work_event: threading.Event = threading.Event()
     
    def connect(self, username: str, password: str, cmd: str) -> dict[str, Any]:
        """
        Establishes a connection to the server and sends authentication credentials.
        Args:
            username (str): Username for authentication
            password (str): Password for authentication 
            cmd (str): Command to be sent to server
        Returns:
            dict[str, Any]: A json containing:
                - str: Response message from server
        Raises:
            Exception: Any network or connection related exceptions that may occur
        Description:
            Creates a TCP socket connection to the server specified in self.ADDR
            Sends JSON encoded credentials and command
            Receives and parses server response,
            Logs connection status and responses
            Returns server message and socket if successful
        """
        global FORMAT
        try:
            _client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            _client_socket.connect(self.ADDR)
            # Receiving public key from server
            key_len_recv = _client_socket.recv(4)
            len_pem_public: int = struct.unpack(FORMAT,key_len_recv)[0]

            pem_public = _client_socket.recv(len_pem_public)
            self.public_key = server_public_key = serialization.load_pem_public_key(pem_public) # Loading public key
            #Generate session key and send it encrypted
            raw_session_key = os.urandom(32)
            self.session_key = base64.urlsafe_b64encode(raw_session_key)
            encrypted_session_key = server_public_key.encrypt(self.session_key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
            _client_socket.send(struct.pack(FORMAT,len(encrypted_session_key)) + encrypted_session_key) #sending session key

            self.fernet = fernet.Fernet(self.session_key)


            auth = {
                    "username": username,
                    "password": password,
                    "cmd": cmd
            }
            encrypted_auth = self.fernet.encrypt(json.dumps(auth).encode())
            _client_socket.send(struct.pack(FORMAT,len(encrypted_auth)) +  encrypted_auth)
            # getting authentication response:
            response_length: bytes = _client_socket.recv(4)
            response_bytes_encrypted: bytes = _client_socket.recv(struct.unpack(FORMAT,response_length)[0])
            response: dict[str, Any] = json.loads(self.fernet.decrypt(response_bytes_encrypted).decode())
            if response["status"] == True:
                self.connection_event.set() # setting the flag to True.
                self.user = response["user"]
                self.files = response["files"]
                self.username = auth["username"]
                self.current_storage = response["user"]["curr_storage"] / (1024**2)
                self.max_storage = response["user"]["max_storage"] / (1024**2)
                self.conn = _client_socket
            print(response)
            return response
        except ConnectionRefusedError:
            return {"status": False,"message": "The server isn't running. Please Try Again Later."}
    
    
    def sendfile(self,file: BinaryIO, command: str,**kwargs) -> None:
        self.work_event.set()
        global FORMAT
        response_text: CTkLabel =  kwargs["response_text"]
        files_table: Treeview = kwargs["table"]
        file_size: int = os.path.getsize(file.name) # file size in bytes.
        # if user doesn't have storage then display appropriate message
        if file_size/(1024**2) + self.current_storage  > self.max_storage:
            response_text.configure(text= "You dont't have enough storage to upload this file")
            return
        payload: dict[str, Any] = {
            "cmd": command,
            "filename":  file.name.split("/")[-1],
            "filesize": file_size,
        }
        self.send_message(payload)

        while chunk := file.read(CHUNK_SIZE):
            encrypted_chunk = self.fernet.encrypt(chunk)
            header = struct.pack(FORMAT, len(encrypted_chunk))
            self.conn.sendall(header + encrypted_chunk)
        print("EOF")
        self.conn.sendall(struct.pack(FORMAT, 0))

        response = self.get_message()
        self.work_event.clear()
        if response["status"]:
            self.files.append({"file_id": response["file_id"] ,"filename": payload["filename"], "filesize": file_size / (1024**2)})
            self.current_storage += file_size / (1024**2)
            dateTime: datetime = datetime.now().strftime("%Y-%m-%d")
            files_table.insert("","end", values= (response["file_id"],file.name.split("/")[-1], str(round(file_size,2))+" bytes",dateTime))
            response_text.configure(text=f"{response["message"]}")
    
    def delete_files(self,file_ids: list[str], files_table: Treeview, selected_rows: tuple[str,...], **kwargs) -> None:
        self.work_event.set()
        response_text = kwargs["response_text"]

        payload = {
            "cmd": "delete",
            "ids": file_ids
        }
        self.send_message(payload)
        response = self.get_message()
        self.work_event.clear()
        response_text.configure(text=response["message"])
        updated: int = 0
        if response["status"]:
            files_table.delete(*selected_rows)

    def ReceiveFile(self, file_id:str, filename:str):
        ...

    @overload
    def send_message(self, payload: str): ...
    @overload 
    def send_message(self, payload: dict[str, Any]): ...
    
    def send_message(self, payload: dict[str,Any] | str) -> None:
        """sending Encrypted message to server

        Args:
            payload (dict[str,Any] | str): payload to send.
        """ 
        if isinstance(payload, str):
            encrypted = self.fernet.encrypt(payload.encode())
            Header = struct.pack(FORMAT,len(encrypted))
            self.conn.send(Header + encrypted)
        if isinstance(payload, dict):    
            encrypted = self.fernet.encrypt(json.dumps(payload).encode())
            Header = struct.pack(FORMAT,len(encrypted))
            self.conn.send(Header + encrypted)

    def get_message(self) -> dict[str, Any]:
        """Receiving response frm server

        Returns:
            dict[str, Any]: message from server.
        """ 
        len_bytes: bytes = self.conn.recv(4)
        encrypted_payload = self.conn.recv(struct.unpack(FORMAT,len_bytes)[0])
        
        return json.loads(self.fernet.decrypt(encrypted_payload).decode())
    
    def recv_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            packet = self.conn.recv(size - len(data))
            if not packet:
                raise ConnectionError("Socket closed unexpectedly")
            data += packet
        return data
