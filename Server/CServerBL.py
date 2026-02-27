from pathlib import Path
from typing import Any
import socket  # Import socket for networking
import threading  # Import threading for concurrent connections
import json  # Import json for message serialization
import os  # Import os for file system operations
from typing import Callable, List, Tuple, Dict
from flask import Flask, Response, abort, stream_with_context
from protocol2 import *  # Import protocol definitions
import bcrypt  # Import bcrypt for password hashing
import struct
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography import fernet
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import sqlite3
from time import sleep


class CServerBL():
    def _create_tables(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users(
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    password_hash BLOB,
                    max_storage INTEGER DEFAULT 1073741824,
                    curr_storage INTEGER DEFAULT 0,
                    tries INTEGER DEFAULT 0,
                    disabled BOOLEAN NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS files(
                    file_id TEXT PRIMARY KEY,
                    filename TEXT,
                    size INTEGER,
                    modified INTEGER,
                    file_hash TXT,
                    user_id INTEGER,
                    share_link BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
            """
            )

    def _register_routes(self) -> None:
        @self.app.route("/view_file/<file_id>")
        def view_file(file_id: str):
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                row = cur.execute(
                    "SELECT filename FROM files WHERE file_id = ? AND share_link = 1",
                    (file_id,)
                ).fetchone()

                if row is None:
                    abort(404)

                filename: str = row[0]
                suffix = Path(filename).suffix.lower()  #  getting suffix

            mime = BROWSER_DISPLAYABLE_MIME_MAP.get(suffix)

            if mime is None:
                mime = "application/octet-stream"
                disposition = "attachment"
            else:
                disposition = "inline"

            def generate():
                with open(f"StorageFiles/{file_id}.encrypted", "rb") as f:
                    while (header := f.read(4)):
                        size = struct.unpack(">I", header)[0]
                        chunk = f.read(size)
                        yield file_fernet.decrypt(chunk)

            return Response(
                stream_with_context(generate()),
                mimetype=mime,
                headers={
                    "Content-Disposition": disposition,
                    "X-Content-Type-Options": "nosniff",
                },
            )           
    def _run_flask(self) -> None:
        self.app.run("0.0.0.0",80, use_reloader=False)
        
    def __init__(self) -> None:
        self._api_thread: threading.Thread | None = None
        self._create_tables()
        self._ip: str = "0.0.0.0"  # Server IP address
        self._port: int = 5050  # Server port
        self._server_socket: socket.socket | None = None  # Main server socket
        self.logger_box = None
        self.clientHandlers: list[ClientHandler] = []  # List of client handler threads
        self._event = threading.Event()  # Event flag for server loop
        _storage_folder_name = "./StorageFiles"  # Folder for storage
        if not os.path.exists(_storage_folder_name):  # Create folder if not exists
            os.mkdir(_storage_folder_name)


        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()

        # Export public key to send to client
        self.pem_public = self.public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo)

        self.app = Flask(__name__)
        self._register_routes()

    # Start the server
    def start_server(self) ->  None:
        FORMAT = "!I"
        """
        Start the TCP server and enter the accept loop.
        Initializes and binds a TCP socket to self._ip and self._port, sets self._event,
        and begins listening for incoming client connections.
        """
        self.write_to_log(self)  # Log server start
        try:
            self._api_thread = threading.Thread(target=self._run_flask, daemon=True)
            self._api_thread.start()
            self.clientHandlers
            self._event.set()  # Set event flag
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create socket
            self._server_socket.bind((self._ip, self._port))  # Bind socket to IP and PORT
            self._server_socket.listen(5)  # Listen for connections
            self.write_to_log(f"[SERVER] is running at \nIP: {socket.gethostbyname(socket.gethostname())} \nPORT: {self._port}")
            while self._event.is_set() and self._server_socket is not None:  # Main accept loop
                client, address = self._server_socket.accept()  # Accept new client
                header = struct.pack(FORMAT, len(self.pem_public))
                client.sendall(header + self.pem_public) # Sending public key to client
                

                encrypted_session_key_len_bytes = client.recv(4)
                encrypted_session_key = client.recv(struct.unpack(FORMAT,encrypted_session_key_len_bytes)[0])
                session_key = self.private_key.decrypt(encrypted_session_key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))

                f = fernet.Fernet(session_key)
                self.write_to_log(client)

                new_client_handler = ClientHandler(client, address, f, self.write_to_log, self._event)
                new_client_handler.start()
                self.clientHandlers.append(new_client_handler)

        except OSError as e:
            pass  # Ignore OS errors
        #except Exception as e:9
        #    self.write_to_log(f"[ServerBL] Exception at start_server(): {e}")  # Log other exceptions
    def stop_server(self) -> None:
        """Stopping the server
        """        
        self.write_to_log(f"Shuting down server...")  # Log stop
        try:
            self._event.clear()  # Clear event flag
            self._api_thread = None
            self.write_to_log(f"[ServerBL] cleared flag!")
            for client_handler in self.clientHandlers:
                self.write_to_log(f"[SERVER] Disconnecting {client_handler}....")
                if client_handler and client_handler.is_alive():
                    client_handler.disconnect()  # Disconnect client
                    client_handler.join()  # Wait for thread to finish
            self.clientHandlers = []  # Clear handler list
            
            if self._server_socket:
                self.server_socket.close()  # Close server socket
                self.server_socket = None
            self._event.clear()
            self.main_thread = None  # Clear main thread
            self.write_to_log("[CServerBL] Closed server!")  # Log closed
            self._api_thread = None
        except Exception as e:
            self.write_to_log(f"[ServerBL] Exception at stop_server(): {e}")  # Log exceptions
    def __repr__ (self)  -> str:
        return  f'{socket.gethostbyname(socket.gethostname())}:5050'
    def write_to_log(self, msg: Any) -> None:
        if self.logger_box:
            self.logger_box.insert("end",f"{msg}\n")
        print(msg)
class ClientHandler(threading.Thread):
    """
    A client handler class that manages individual client connections in separate threads.
    This class inherits from threading.Thread to handle each client connection concurrently.
    It maintains the client socket connection, processes client requests, and manages
    disconnection events.
    Attributes:
        client (socket.socket): The client's socket connection
        address (Tuple[str,int]): Client's address info (IP, port)

        Methods:
        run(): Main thread execution method that handles client communication
        _disconnect(): Closes client connection and cleanup
        __repr__(): String representation of the client handler
        _get_message(): Getting Encryption message from client and doing Decryption.
        _send_message(): Sending Encryption message to client
    Args:
        client_socket (socket.socket): Socket object for client connection
        client_address (Tuple[str,int]): Client's address information
    """
    
    def __init__(
        self, 
        client_socket: socket.socket,
        client_address,
        f: fernet.Fernet,
        write_to_log,
        event: threading.Event
    ) -> None:
        super().__init__()
        self.db_conn: sqlite3.Connection | None = None
        self.client: socket.socket | None= client_socket
        self.address: Tuple[str,int]  = client_address
        self.client: socket.socket = client_socket
        self.daemon = True
        self.write_to_log = write_to_log
        self._fernet: fernet.Fernet = f
        self._event = event
        self.user_id: int = -1
        
        if not os.path.exists("./StorageFiles"):
            os.mkdir("./StorageFiles")
    # This code run for every client in a different thread
    def run(self) -> None:
        self.db_conn = sqlite3.connect(DB_PATH)

        # Server functionality here
        self.write_to_log(f"[+] client connection! {self} from device: {socket.gethostname()}")
        self.write_to_log(f"[SERVER] {threading.active_count() - 2} Are currently connected!")
        i = 1
        while self._event.is_set():
            try:
                json_string: str | None = self._get_message()
                if json_string:
                    request: dict[str, Any] = json.loads(json_string)
                    print(request)
                    response: dict[str, Any] | None = handle_client_request(request,self)
                    if response:
                        if response.get("cmd") == "!DIS":
                            break 
                        self._send_message(response)
                else:  
                    break
            except ConnectionResetError:
                self.write_to_log("client was forced closed!")
                break
            except ConnectionAbortedError:
                self.write_to_log("ClientHandler -> run()] client connection Aborted!")
                break
            i+=1
        self._disconnect()
    def _get_message(self) -> str | None:
        """getting message from client
        
        Keyword arguments:
        Return: json string (str) , if client disconnected then returns None
        """
        
        self.write_to_log(f"Getting message from: {self}")
        header: bytes = recv_exact(self.client, 4)
        if not header:
            raise ConnectionAbortedError()
        message_length: int = struct.unpack("!I",header)[0]
        encrypted: bytes = recv_exact(self.client ,message_length)
        return self._fernet.decrypt(encrypted).decode()
    def _send_message(self, data: dict[str,Any]):
        print(data)
        encrypted_data: bytes = self._fernet.encrypt(json.dumps(data).encode())
        header: bytes = struct.pack(FORMAT,len(encrypted_data)) # calculating header
        self.client.sendall(header + encrypted_data) # sending header with encrypted data
    def _disconnect(self) -> None:
        """
        Disconnects the client handler from the client.
        Closes the client socket and the database connection, and logs the disconnection.
        """
        self.write_to_log(f"[SERVER-BL]: {self} disconnect requested")
        if self.client:
            try:
                # Attempt to shut down the socket for both reading and writing
                self.client.shutdown(socket.SHUT_RDWR)
            except OSError:
                # Socket may already be closed or not connected
                pass
            finally:
                try:
                    # Close the socket connection
                    self.client.close()
                except OSError:
                    # Ignore errors if socket is already closed
                    pass
                self.client = None
                self.write_to_log(f"[-] {self} Disconnected from server! ")
        # Close the database connection
        self.db_conn.close()
        self.db_conn = None
    def __repr__(self) -> str: return f"{self.address[0]}:{self.address[1]}" # String representation

if __name__ == "__main__":
    print("Press Ctrl + C to exit.")
    server = CServerBL()
    server.start_server()
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        server.stop_server()