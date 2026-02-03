import socket
import struct
from shutil import rmtree
from typing import Any
from typing import Dict, Any, overload
import bcrypt
from datetime import datetime
from uuid6 import uuid7
import os
from uuid import uuid4
from cryptography.fernet import Fernet
import sqlite3
DB_PATH = "./mydb.db"
FORMAT = "!I"
CHUNK_SIZE = 1024 *64  # 64 KB
client_ids: list[int] = []
def get_encryption_key():
    if not os.path.exists("./key.bin"):
        key = Fernet.generate_key()
        with open("./key.bin","wb") as f:
            f.write(key)
            return key
    with open("./key.bin","rb") as f:
        return f.read() 
file_fernet = Fernet(get_encryption_key())
def username_exists(username: str, **kwargs) -> bool: 
    return kwargs["cursor"].execute("SELECT 1 FROM users WHERE username == ?",(username,)).fetchone() is not None
@overload
def getUser(login: int) -> dict[str, Any] | None:
    ...
@overload
def getUser(login: dict[str,Any]) -> dict[str, Any] | None: 
    ...
def getUser(login: dict | int) -> dict[str, Any] | None:
    """
    Retrieves a user record based on user ID or login credentials.
    Updates failed login attempts and disables the user after 3 failed tries.

    Args:
        login (dict | int): Either:
            - dict with 'username' and 'password' for login
            - int representing user_id

    Returns:
    """
    keys = ["user_id", "username", "password_hash", "max_storage", "curr_storage", "tries", "disabled"]
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        res: dict[str, Any] | None = None
        if isinstance(login, int):
            values = cur.execute("SELECT * FROM users WHERE user_id == ?",(login,)).fetchone()
            if not values:
                return None
        if isinstance(login, dict):
            values = cur.execute("SELECT * FROM users WHERE username == :username AND disabled = 0",login).fetchone()
            if not values:
                return None
            elif values[5] < 3:
                cur.execute("UPDATE users SET tries = tries + 1 WHERE user_id = ?",(values[0],))
            if not bcrypt.checkpw(login["password"].encode(),values[2]):
                cur.execute("UPDATE users SET tries = tries + 1 WHERE username = :username",login)
                return None
    return dict(zip(keys, values))
def InsertUser(user: Dict[str,Any]) -> tuple[dict[str, Any], None] | tuple[dict[str, Any], int]:
    """Insert a new user into the database.

    Args:
        user (Dict[str, Any]): A dictionary containing 'username' and 'password' keys.

    Returns:
        Dict: A dictionary with 'status' indicating success and 'response' message.
    """
    
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        if username_exists(user["username"],cursor=cur):
            return {"status":False, "message": "This username is already taken"}, None
        cur.execute(
            "INSERT INTO users(username, password_hash) VALUES (?, ?)",(
                user["username"],
                bcrypt.hashpw(user["password"].encode("utf-8"),bcrypt.gensalt())
            )
        )
        user_id: int = cur.execute("SELECT user_id FROM users WHERE username == :username", user).fetchone()[0]
        conn.commit()
    return {"status": True,"message": "Welcome to skyVault!","curr_storage": 0,"max_storage": 1073741824}, user_id
def files_by_id(uid: int)   -> list[dict[str, Any]]:
    with sqlite3.connect("./mydb.db") as conn:
        cur = conn.cursor()
        files = cur.execute("SELECT * FROM files WHERE user_id = ?",(uid,)).fetchall()
        keys = ["file_id", "filename", "size","modified", "user_id"]
        return [dict(zip(keys, file)) for file in files]
def UploadFile(payload: dict[str, Any], ClientHandler) -> dict[str,Any] | None:
    """Uploading a file to cloud
    Args:
        payload (dict[str, Any]): Containing 
        client (socket.socket): client socket object
        user (User): client user information

    Returns:
        dict[str,Any]: status response from server to client
    """
    fernet = ClientHandler._fernet
    client: socket.socket = ClientHandler.client
    file_id = str(uuid7())
    file_size = payload["filesize"]
    HEADER_SIZE = struct.calcsize(FORMAT) # Ensure FORMAT matches size
    
    save_path = f"./StorageFiles/{file_id}.encrypted"
    try:
        if not os.path.exists("StorageFiles"):
            os.mkdir("StorageFiles")
        with open(save_path,"ab") as f:
            while True:
                #  Read the length of the ENCRYPTED chunk
                header_bytes = recv_exact(client,HEADER_SIZE)
                header = struct.unpack(FORMAT, header_bytes)[0]
                if header == 0: break  #  Check for EOF (The 0 at the end)
                original_chunk = fernet.decrypt(recv_exact(client, header))
                file_encryption = file_fernet.encrypt(original_chunk)
                f.write(struct.pack("!I", len(file_encryption)) + file_encryption) # writing encryption bytes with length        
        print(f"file received from: {ClientHandler}.")
        cur: sqlite3.Cursor =  ClientHandler.db_conn.cursor()
        cur.execute("UPDATE users SET curr_storage = curr_storage + ? WHERE user_id = ? ", (payload["filesize"],ClientHandler.user_id))
        cur.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?,?)",(file_id,payload["filename"],payload["filesize"], int(datetime.now().timestamp()), payload["hash"].encode(), ClientHandler.user_id))
        ClientHandler.db_conn.commit()

    
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as e:
        try: os.remove(save_path)
        except FileNotFoundError: pass
        return None

    return {"status": True, "message": payload["filename"]+" Uploaded!","file_id":file_id}
def SendFile(file_id: str, ClientHandler) -> None: 
    """_summary_

    Args:
        client (socket.socket): _description_
        filename (str): _description_

    Returns:
        dict[str, Any]: _description_
    """
    client: socket.socket = ClientHandler.client
    try:
        ClientHandler.write_to_log(f"Sending file to {ClientHandler}...")
        with open(f"StorageFiles/{file_id}.encrypted", "rb") as f:
            while header := f.read(4):
                print(header)
                original_chunk: bytes = file_fernet.decrypt(f.read(struct.unpack(FORMAT,header)[0]))
                encrypted: bytes = ClientHandler._fernet.encrypt(original_chunk)
                client.sendall(struct.pack(FORMAT, len(encrypted)) +encrypted)
            client.sendall(struct.pack(FORMAT,0))
        ClientHandler.write_to_log(f"finished sending file to {ClientHandler}!")
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        pass
    return None
def DeleteFile(file_id, ClientHandler)-> dict[str, Any]:
    print(file_id)
    """Deleting files by file ids and updating current storage of user

    Args:
        file_id str: file_id To delete
        user (User): User Object.
    Returns:
        dict[str, Any]: Response from server.
    """ 
    try:
        cur: sqlite3.Cursor = ClientHandler.db_conn.cursor()
        cur.execute("BEGIN TRANSACTION;")
        cur.execute(
            """
            UPDATE users
            SET curr_storage = curr_storage - (
                SELECT size FROM files WHERE file_id = ?
            )
            WHERE user_id = (
                SELECT user_id FROM files WHERE file_id = ?
            );
            """, (file_id, file_id)
        )
        cur.execute(
            """
            DELETE FROM files
            WHERE file_id = ?;
            """, (file_id,)
        )
        ClientHandler.db_conn.commit()
        os.remove(f"./StorageFiles/{file_id}.encrypted")
        return {"status": True, "message": "File deleted successfully!"}
    except Exception as e:
        print(e)
        return {"status": False, "message": "An Error occurred when the server was trying to delete this file"}
def createLink(file_id: str)-> dict[str, Any]:
    try:
        return {"status": True,"message": "Share link created!", "link": ""}
    except:
        return {"status": False,"message": "Couldn't Create share link."}
def handle_client_request(payload: dict[str, Any],ClientHandler, **kwargs) -> dict[str, Any] | None:
    """Handling clients requests

    Args:
        payload (dict[str, Any]): client's requests with parameters.
         client (socket.socket): client socket object.
        user (User): client's user data.

    Returns:
        dict[str, Any] | None: Server Response.
    """ 
    response: dict[str, Any] | None = {}
    ClientHandler.write_to_log(f"fetching {ClientHandler}'s Request: "+payload["cmd"])
    match payload["cmd"]:
        case "login":
            if _user := getUser(payload):
                response = {
                    "status": True,
                    "message": "Welcome back"+payload["username"]+"!",
                    "files": files_by_id(_user["user_id"]),
                    "curr_storage": _user["curr_storage"],
                    "max_storage": _user["max_storage"]
                }
                ClientHandler.user_id = _user["user_id"]
            else:
                response = {"status": False, "message": "Invalid username or password!"}
        case "register":
            response, user_id = InsertUser(payload)
            if response["status"]: 
                response["files"] = []
                ClientHandler.user_id = user_id
        case "upload":
            response = UploadFile(payload,ClientHandler)
        case "delete":
            response = DeleteFile(payload["id"], ClientHandler)
        case "save":
            response = SendFile(payload["file_id"], ClientHandler)
        case "createLink":
            response = createLink(payload["file_id"], ClientHandler.db)
        case _:
            response = {"status": False, "message": "Invalid command"}
    return response
def recv_exact(sock: socket.socket, size: int) -> bytes:
    if size < 0:
        raise ValueError("size must be non negative")
    data = bytearray()
    while len(data) < size:
        packet: bytes = sock.recv(size - len(data))
        if not packet:
            raise ConnectionError("Socket closed unexpectedly")
        data.extend(packet)
    return bytes(data)