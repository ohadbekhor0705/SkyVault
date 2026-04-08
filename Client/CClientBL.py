import io
import socket
from typing import Callable, Tuple,BinaryIO
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
CHUNK_SIZE = 1024 * 64
FORMAT = "!I"
class CClientBL():
    def __init__(self) -> None:
        self._conn: socket.socket | None = None
        self.connection_event = threading.Event()
        self._fernet: fernet.Fernet

        self.current_storage: int = 0
        self.max_storage: int = 0
        self.username: str = ""
        self.work_event: threading.Event = threading.Event()
    def _process_handshake(self, **kwargs) -> None:
        while True:
            try:
                print("Attempting to connect...")
                _client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                _client_socket.connect(("127.0.0.1",7777))
                self._conn = _client_socket
                break
            except ConnectionRefusedError:
                print("Connection Has failed")
                _client_socket.close()
            sleep(0.5)



        # Receiving public key from server
        key_len_recv = _client_socket.recv(4)
        len_pem_public: int = struct.unpack(FORMAT,key_len_recv)[0]
        pem_public = _client_socket.recv(len_pem_public)
        public_key = server_public_key = serialization.load_pem_public_key(pem_public) # Loading public key
        #Generate session key and send it encrypted
        raw_session_key = os.urandom(32)
        session_key = base64.urlsafe_b64encode(raw_session_key)
        encrypted_session_key = server_public_key.encrypt(session_key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        _client_socket.send(struct.pack(FORMAT,len(encrypted_session_key)) + encrypted_session_key) #sending session key
        self.fernet = fernet.Fernet(session_key)

        if auth_button := kwargs.get("auth_button"):
            auth_button.configure(state="normal")
    def connect(self, username: str, password: str, cmd: str) -> dict[str, Any]:
        """
        sends authentication credentials.
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

            auth: dict[str, str] = {"username": username,"password": password,"cmd": cmd}
            print(auth)
            encrypted_auth = self.fernet.encrypt(json.dumps(auth).encode())
            self._conn.send(struct.pack(FORMAT,len(encrypted_auth)) +  encrypted_auth)
            # getting authentication response:
            response_length: bytes = self._conn.recv(4)
            response_bytes_encrypted: bytes = self._conn.recv(struct.unpack(FORMAT,response_length)[0])
            response: dict[str, Any] = json.loads(self.fernet.decrypt(response_bytes_encrypted).decode())
            print(response)
            if response["status"] == True:
                self.connection_event.set() # setting the flag to True.
                self.folders = response["folders"]
                self.username = auth["username"]
                self.current_storage = response["curr_storage"]
                self.max_storage = response["max_storage"]
                self._conn = self._conn
            return response
        except (ConnectionAbortedError, ConnectionError, ConnectionResetError):
            return {"status": False,"message": "Server Error"}
    def get_files_data(self, folder_id: str, parent: CTkScrollableFrame, callbacks: list[Callable], **kwargs) -> list[FileRow]:

        self.work_event.set()
        animate: Callable | None = kwargs.get("animate")
        if animate: 
            threading.Thread(target=animate).start()
        header_field: CTkLabel | None = kwargs.get("header_field")
        try:
            self._send_message({"cmd":"get_files","folder_id":folder_id} )
            response = self._get_message()
            file_rows: list[FileRow] = []
            if response["status"]:
                files_data = response["files"]
                print(len(files_data))
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
                        on_delete=callbacks[0](file_data["file_id"],file_data["size"],None),
                        on_save=callbacks[1](file_data["file_id"], file_data["filename"] ),
                        on_share=None,
                    )
                    # Fix the row references in the callback after row is created
                    file_row.on_delete = callbacks[0](file_row.file_id,file_data["size"] ,file_row)
                    file_row.on_share = callbacks[2](file_row)

                    file_rows.append(file_row)
        except (ConnectionAbortedError, ConnectionError, ConnectionResetError):
            if header_field:
                self.work_event.clear()
                header_field.configure(text="Something went wrong with the server! Couldn't retrieve data from the cloud", text_color="red")
        finally:
            self.work_event.clear()
            return file_rows
       
    def sendfile(self,file: BinaryIO,folder_id:int ,callbacks: list[Callable], **kwargs) -> None:
        """Sending file to server.

        Args:
            file (BinaryIO): Opened file in 'rb' (Read-Binary) mode.
            callbacks (list[Callable]): callback functions: 0-delete, 1-save, 2- share
        """
        print("sendfile() started!")
        self.work_event.set()
        global FORMAT
        header_field: CTkLabel =  kwargs["header_field"]
        parent: CTkScrollableFrame = kwargs["parent"]
        bar = kwargs["bar"]

        header_field.configure(text_color="black")
        threading.Thread(target=kwargs["animate"]).start() # starting animation in GUI

       
        file_size: int = os.path.getsize(file.name) # file size in bytes.
        # if user doesn't have storage then display appropriate message
        if file_size + self.current_storage  > self.max_storage:
            header_field.configure(text= "You dont't have enough storage to upload this file")
            self.work_event.clear()
            return
        file_hash = self._hash_file(file)
        print(file_hash)
        payload: dict[str, Any] = {"cmd": "upload","filename":  file.name.split("/")[-1], "folder_id": folder_id,"filesize": file_size, "hash": file_hash}
        try:
            self._send_message(payload) # sending a data into

            # sending file in chunks
            while chunk := file.read(CHUNK_SIZE):
                encrypted_chunk = self.fernet.encrypt(chunk) 
                header = struct.pack(FORMAT, len(encrypted_chunk)) # calculating header
                self._conn.sendall(header + encrypted_chunk) # sending a packet; [header|encrypted chunk]
            self._conn.sendall(struct.pack(FORMAT, 0)) # sending EOF (End Of File) Packet
            file.close()

            response = self._get_message() # getting response

    
            if response["status"]:
                self.current_storage += file_size
                bar.set(self.current_storage/self.max_storage)
                header_field.configure(text=response["message"], text_color = "green")
                last_row = parent.grid_size()[1]  # next empty row
                file_row = FileRow(
                    parent, 
                    response["file_id"],
                    file.name.split("/")[-1],
                    file_size,
                    datetime.now().strftime("%Y-%m-%d"),
                    file_hash,
                    False,
                    self,
                    on_delete=callbacks[0](response["file_id"],file_size,None),
                    on_save=callbacks[1](response["file_id"], file.name.split("/")[-1]),
                    on_share=None,
                )

                # Fix the row references in the callback after row is created
                file_row.on_delete = callbacks[0](response["file_id"],file_size ,file_row)
                file_row.on_share = callbacks[2](file_row)
                file_row.grid(row =last_row,column=0 , sticky="ew", padx=12, pady=6)
                
        except (ConnectionResetError, ConnectionAbortedError, ConnectionError):
            header_field.configure(text="Something went wrong with the server! Couldn't fulfill the request.", text_color="red")
        finally:
            self.work_event.clear() # clearing working flag
    def _hash_file(self, file: BinaryIO, algorithm = "sha256", return_to_start=True) -> str:
        hasher = hashlib.new(algorithm)  
        BLOCKSIZE = io.DEFAULT_BUFFER_SIZE
        for chunk in iter(lambda: file.read(BLOCKSIZE),b''):
            hasher.update(chunk)
        if return_to_start:
            file.seek(0)
        return hasher.hexdigest()
    def delete_file(self,file_id: str,size:int ,**kwargs) -> dict[str, Any]:
        print(size,self.current_storage)
        self.work_event.set()
        header = kwargs["header_field"]
        bar = kwargs["bar"]
        payload = {"cmd": "delete","type": "file", "id": file_id}
        self._send_message(payload)
        response = self._get_message()
        print(response)
        if response["status"]:
            self.current_storage -= size
            print(self.current_storage)
            bar.set(self.current_storage/self.max_storage)
        self.work_event.clear()
    def delete_folder(self,folder_row,folder_rows: dict, **kwargs) -> None:
        self.work_event.set()
        header_field: CTkLabel | None = kwargs.get("header_field")
        progress_bar: CTkLabel | None = kwargs.get("bar")
        try:
            self._send_message({"cmd":"delete", "type": "folder", "id": folder_row.folder_id})

            response = self._get_message()

            if not response:
                raise ConnectionError
            if response["status"]:
                self.current_storage = response["current_storage"]
                del folder_rows[folder_row.folder_id]
                value = next(iter(folder_rows.values()))
                
                value.on_click()
                folder_row.destroy()
                del folder_row
            else:
                if header_field:
                    header_field.configure(text="The server could'nt this this folder", text_color="red")

        except (ConnectionAbortedError, ConnectionResetError,ConnectionError):
            if header_field:
                header_field.configure(text="Something went wrong with the server! Couldn't fulfill the request.", text_color="red")
            if progress_bar:
                progress_bar.set(self.current_storage/self.max_storage)

        finally:
            self.work_event.clear()

    def ReceiveFile(self, file_id:str, filename:str,save_path: str, **kwargs) -> None:
        self.work_event.set()
        header_field: CTkLabel =  kwargs["header_field"]
        self._send_message({"cmd": "save", "file_id": file_id})
        path = f"{save_path}/{filename}"
        try:
            with open(path,"wb") as f:
                while True:
                    header: int = struct.unpack(FORMAT, self._recv_exact(4))[0]
                    if header == 0:
                        header_field.configure(text=f"file saved on: '/{save_path}/{filename}'")
                        self.work_event.clear()
                        break
                    decrypted: bytes = self.fernet.decrypt(self._recv_exact(header))
                    f.write(decrypted)
        except (ConnectionAbortedError, ConnectionResetError):
            os.remove(path)
            header_field.configure(text="Something went wrong with the server! Couldn't fulfill the request.",text_color="red")
        finally:
            self.work_event.clear()
    @overload
    def _send_message(self, payload: str): ...
    @overload 
    def _send_message(self, payload: dict[str, Any]): ...
    def _send_message(self, payload: dict[str,Any] | str) -> bool:
        """sending Encrypted message to server

        Args:
            payload (dict[str,Any]): payload to send.
        """
        try:
            print(f"sending {payload}...")
            if isinstance(payload, str):
                encrypted = self.fernet.encrypt(payload.encode())
                Header = struct.pack(FORMAT,len(encrypted))
                print(f"Header Length: {Header}")
                self._conn.sendall(Header + encrypted)
            elif isinstance(payload, dict):    
                encrypted = self.fernet.encrypt(json.dumps(payload).encode())
                Header = struct.pack(FORMAT,len(encrypted))
                self._conn.sendall(Header + encrypted)
            else:
                raise ValueError(f"Type {type(payload)} isn't supported!")
        except (ConnectionResetError, ConnectionError):
            return False
        return True
    def _get_message(self) -> dict[str, Any] | None:
        """Receiving response frm server

        Returns:
            dict[str, Any]: message from server.
        """ 
        try:
            len_bytes: bytes = self._conn.recv(4)
            encrypted_payload = self._conn.recv(struct.unpack(FORMAT,len_bytes)[0])
        
            return json.loads(self.fernet.decrypt(encrypted_payload).decode())
        except (ConnectionAbortedError, ConnectionResetError):
            return None
    def _recv_exact(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            packet = self._conn.recv(size - len(data))
            if not packet:
                raise ConnectionError("Socket closed unexpectedly")
            data.extend(packet)
        return bytes(data)
    

