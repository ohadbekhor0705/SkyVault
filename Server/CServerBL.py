from typing import Any
import socket  # Import socket for networking
import threading  # Import threading for concurrent connections
import json  # Import json for message serialization
import os  # Import os for file system operations
from tkinter.ttk import Treeview  # Import Treeview for GUI client table
from typing import Callable, List, Tuple, Dict  # Type hints
from protocol import *  # Import protocol definitions
import bcrypt  # Import bcrypt for password hashing
from models import User,File,SessionLocal # Import db for Database operations
import struct
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography import fernet
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from run import run    



class CServerBL():
    def __init__(self) -> None:
        self._ip: str = "0.0.0.0"  # Server IP address
        self._port: int = 9999  # Server port
        self.server_socket: socket.socket | None = None  # Main server socket
        self.logger_box = None
        self.clientHandlers: List[CClientHandler] = []  # List of client handler threads
        self.event = threading.Event()  # Event flag for server loop
        self.main_thread: threading.Thread | None = None  # Main server thread
        self.web_server: threading.Thread = threading.Thread(target=run, daemon=True)
        storage_folder_name = "./StorageFiles"  # Folder for storage
        if not os.path.exists(storage_folder_name):  # Create folder if not exists
            os.mkdir(storage_folder_name)


        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()

        # Export public key to send to client
        self.pem_public = self.public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo)

    # Start the server
    def start_server(self) ->  None:
        FORMAT = "!I"
        """
        Start the TCP server and enter the accept loop.
        Initializes and binds a TCP socket to self._ip and self._port, sets self.event,
        and begins listening for incoming client connections.
        """
        #self.web_server = multiprocessing.Process(target=run)
        self.write_to_log(self)  # Log server start
        #self.web_server.start()
        try:
            self.event.set()  # Set event flag
            self.web_server.start()
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create socket
            self.server_socket.bind((self._ip, self._port))  # Bind socket to IP and port
            self.server_socket.listen(5)  # Listen for connections
            self.write_to_log(f"[SERVER] is running at \nIP: {socket.gethostbyname(socket.gethostname())} \nPORT: {self._port}")
            while self.event.is_set() and self.server_socket is not None:  # Main accept loop
                client, address = self.server_socket.accept()  # Accept new client
                header = struct.pack(FORMAT, len(self.pem_public))
                client.send(header + self.pem_public) # Sending public key to client
                

                encrypted_session_key_len_bytes = client.recv(4)
                encrypted_session_key = client.recv(struct.unpack(FORMAT,encrypted_session_key_len_bytes)[0])
                session_key = self.private_key.decrypt(encrypted_session_key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))

                f = fernet.Fernet(session_key)
                self.write_to_log(client)
                # getting payload from client
                payload_length_bytes: bytes = client.recv(4) 
                payload_bytes: bytes = f.decrypt(client.recv(struct.unpack(FORMAT,payload_length_bytes)[0])).decode()
                payload: dict = json.loads(payload_bytes.encode())
                self.write_to_log(f"[CClientBL] Authentication payload received: {payload}")
            
                response = {
                    "status": False,
                    "message": "<authentication Response from server>"
                }
                # Handle login command
                if payload["cmd"] == "login":
                    if (_user  := getUser(payload)):
                        self.createHandler(client, address,_user, f)  # Create handler thread
                        response = {"status": True, "message": f"Welcome back, {payload['username']}", "user": _user.toDict()}
                        uid: int = _user.user_id
                        files: list[dict[str, Any]] = files_by_id(uid)
                        response["files"] = files
                    else:
                        response = {"status": False, "message": "Username or password are Invalid!"}

                # Handle register command
                elif payload["cmd"] == "register":
                    payload["password_hash"] = bcrypt.hashpw(payload["password"].encode("utf-8"),bcrypt.gensalt()).decode()
                    response = InsertUser(payload)
                    if response["status"] == True:
                        user: User | None = getUser(payload)
                        response["user"] = user.toDict()
                        response["files"] = []
                        self.createHandler(client,address,user,f)
                
                # Send response to client 
                encrypted_response = f.encrypt(json.dumps(response).encode())
                client.send(struct.pack(FORMAT,len(encrypted_response)) + encrypted_response)
        except OSError as e:
            pass  # Ignore OS errors
        #except Exception as e:
        #    self.write_to_log(f"[ServerBL] Exception at start_server(): {e}")  # Log other exceptions

    def stop_server(self) -> None:
        """Stopping the server
        """        
        self.write_to_log(f"[ServerBL] stop_server() called")  # Log stop
        try:
            #self.web_server.kill()
            #self.web_server = None
            self.event.clear()  # Clear event flag
            self.write_to_log(f"[ServerBL] cleared flag!")
            for clientHandler in self.clientHandlers:
                if clientHandler:
                    clientHandler.client.send(b"!DIS") # sending connection
                    clientHandler.disconnect()  # Disconnect client
                    clientHandler.join()  # Wait for thread to finish
            self.clientHandlers = []  # Clear handler list
            
            if self.server_socket:
                self.server_socket.close()  # Close server socket
                self.server_socket = None
            
            self.main_thread = None  # Clear main thread
            self.write_to_log("[CServerBL] Closed server!")  # Log closed
        except Exception as e:
            self.write_to_log(f"[ServerBL] Exception at stop_server(): {e}")  # Log exceptions

    def createHandler(self, client_socket: socket.socket, client_address, user: User, f: fernet.Fernet) -> None:
        """Creating new ClientHandler to handle client requests

        Args:
            client_socket (socket.socket): client socket object
            client_address (_type_): client address
            user (User): user object containing client data
            f (Fernet): Fernet object to handle Encryption and Decryption. 
        """        
        client_handler: CClientHandler = CClientHandler(client_socket, client_address, user, f,  self.write_to_log)  # Create handler
        self.clientHandlers.append(client_handler)  # Add to handler list
        client_handler.start()  # Start handler thread
    
    def __repr__ (self) -> str:
        return f"<Server(ip={self._ip}, port={self._port}, flag={self.event.is_set()}, {self.server_socket})>"

    def write_to_log(self, msg: Any) -> None:
        if self.logger_box:
            self.logger_box.insert("end",f"{msg}\n")

class CClientHandler(threading.Thread):
    """
    A client handler class that manages individual client connections in separate threads.
    This class inherits from threading.Thread to handle each client connection concurrently.
    It maintains the client socket connection, processes client requests, and manages
    disconnection events.
    Attributes:
        client (socket.socket): The client's socket connection
        address (Tuple[str,int]): Client's address info (IP, port)
        connected (bool): Connection status flag
        table_callback (Callable): Callback function to update client table
    Methods:
        run(): Main thread execution method that handles client communication
        disconnect(): Closes client connection and cleanup
        __repr__(): String representation of the client handler
        get_message(): Getting Encryption message from client and doing Decryption.
        send_message(): Sending Encryption message to client
    Args:
        client_socket (socket.socket): Socket object for client connection
        client_address (Tuple[str,int]): Client's address information
    """
    
    def __init__(self, client_socket: socket.socket, client_address, user: User, f: fernet.Fernet, write_to_log) -> None:
        super().__init__()
        self.client: socket.socket | None= client_socket
        self.address: Tuple[str,int]  = client_address
        self.client: socket.socket = client_socket
        self.connected = True
        self.user: User = user
        self.daemon = True
        self.write_to_log = write_to_log
        self.f: fernet.Fernet = f

        if not os.path.exists("./StorageFiles"):
            os.mkdir("./StorageFiles")
    # This code run for every client in a different thread
    def run(self) -> None:
        # Server functionality here
        self.write_to_log(f"[CClientBl] {threading.active_count() - 1} Are currently connected!")
        while True:
            try:
                message: str | None = self.get_message()
                if message:
                    if message == "!DIS": break
                    payload: dict[str, Any] = json.loads(message)
                    response: dict[str, Any] | None = handle_client_request(payload,self)
                    if response: self.send_message(response)
                else:  break
            except ConnectionResetError:
                self.write_to_log("[ClientHandler -> run()] client was forced closed!")
                break
            except ConnectionAbortedError:
                self.write_to_log("ClientHandler -> run()] client connection Aborted!")
                break
        self.disconnect()

    def get_message(self) -> str | None:
        header = self.client.recv(4)
        message_length: int = struct.unpack("!I",header)[0]
        encrypted  =self.client.recv(message_length)
        return self.f.decrypt(encrypted).decode() # the error is here
    
    def send_message(self, data: dict[str,Any]):
        encrypted_data = self.f.encrypt(json.dumps(data).encode())
        header = struct.pack(FORMAT,len(encrypted_data)) # calculating header
        self.client.send(header + encrypted_data) # sending header with encrypted data
    
    def disconnect(self) -> None:
        self.write_to_log(f"[SERVER-BL] {self} disconnected")
        self.connected = False
        if self.client:
            self.client.close()
        self.client = None
        del self
     
    def __repr__(self) -> str: return f"<ClientHandler({self.address=}, {socket.gethostbyaddr(self.address[0])}>"

if __name__ == "__main__":
        print("Press Ctrl + C to exit.")
        server = CServerBL()
        server.start_server()
        try:
            from time import sleep
            while True:
                sleep(1)
        except KeyboardInterrupt:
            server.stop_server()