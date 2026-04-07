import socket
import struct
from typing import Any
from typing import Dict, Any, overload
import bcrypt
from datetime import datetime
from uuid6 import uuid7
import os
from uuid import uuid4
from cryptography.fernet import Fernet
import sqlite3
from pathlib import Path
DB_PATH = "./mydb.db"
FORMAT = "!I"
CHUNK_SIZE = 1024 *64  # 64 KB
client_ids: list[int] = []
BROWSER_DISPLAYABLE_MIME_MAP = {
    # Plain text / source
    ".txt":  "text/plain; charset=utf-8",
    ".py":   "text/plain; charset=utf-8",
    ".js":   "text/javascript; charset=utf-8",
    ".mjs":  "text/javascript; charset=utf-8",
    ".ts":   "text/javascript; charset=utf-8",
    ".tsx":  "text/javascript; charset=utf-8",
    ".jsx":  "text/javascript; charset=utf-8",  
    ".css":  "text/css; charset=utf-8",
    ".scss": "text/x-scss; charset=utf-8",
    ".sass": "text/x-sass; charset=utf-8",
    ".less": "text/css; charset=utf-8",
    ".md":   "text/markdown; charset=utf-8",
    ".log":  "text/plain; charset=utf-8",
    ".csv":  "text/csv; charset=utf-8",
    ".tsv":  "text/tab-separated-values; charset=utf-8",
    ".yaml": "application/x-yaml; charset=utf-8",
    ".yml":  "application/x-yaml; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map":  "application/json; charset=utf-8",
    ".xml":  "application/xml; charset=utf-8",
    ".rss":  "application/rss+xml; charset=utf-8",
    ".atom": "application/atom+xml; charset=utf-8",

    # HTML
    ".html": "text/html; charset=utf-8",
    ".htm":  "text/html; charset=utf-8",

    # Images
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".svg":  "image/svg+xml",
    ".bmp":  "image/bmp",
    ".ico":  "image/x-icon",
    ".avif": "image/avif",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff",

    # Audio
    ".mp3":  "audio/mpeg",
    ".wav":  "audio/wav",
    ".ogg":  "audio/ogg",
    ".oga":  "audio/ogg",
    ".m4a":  "audio/mp4",
    ".aac":  "audio/aac",
    ".flac": "audio/flac",

    # Video
    ".mp4":  "video/mp4",
    ".webm": "video/webm",
    ".ogv":  "video/ogg",
    ".mov":  "video/quicktime",
    ".mkv":  "video/x-matroska",

    # Documents
    ".pdf":  "application/pdf",
    ".wasm": "application/wasm",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls":  "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt":  "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",

    # Fonts
    ".woff":  "font/woff",
    ".woff2": "font/woff2",
    ".ttf":   "font/ttf",
    ".otf":   "font/otf",
    ".eot":   "application/vnd.ms-fontobject",

    # Archives (some browsers may download instead of render)
    ".zip":  "application/zip",
    ".tar":  "application/x-tar",
    ".gz":   "application/gzip",
    ".rar":  "application/vnd.rar",
    ".7z":   "application/x-7z-compressed",
}


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
            elif not bcrypt.checkpw(login["password"].encode(),values[2]):
                
                if values[5] < 3:
                    cur.execute("UPDATE users SET tries = tries + 1 WHERE username = :username",login)
                else:
                    cur.execute("UPDATE users SET disabled = 1 WHERE username = := username",login)
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
        cur.execute("INSERT INTO folders(folder_id,folder_name, root, user_id) VALUES (?,?,?,?)",(str(uuid7()),"root",True,user_id))
        conn.commit()
    return {"status": True,"message": "Welcome to skyVault!","curr_storage": 0,"max_storage": 1073741824, "folders": get_folders_by_id(user_id)}, user_id
def files_by_id(uid: int)   -> list[dict[str, Any]]:
    with sqlite3.connect("./mydb.db") as conn:
        cur = conn.cursor()
        files = cur.execute("SELECT * FROM files WHERE user_id = ?",(uid,)).fetchall()
        keys: list[str] = ["file_id", "filename", "size","modified","file_hash" ,"user_id","folder_id","share_link"]
        return [dict(zip(keys, file)) for file in files]
def get_folders_by_id(uid: int):
    keys = ["folder_id","folder_name","root", "user_id"]
    with sqlite3.connect("./mydb.db") as conn:
        cur = conn.cursor()
        folders = cur.execute("SELECT * FROM folders WHERE user_id = ?",(uid,)).fetchall()
        return [dict(zip(keys, folder)) for folder in folders]     
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
    
    save_path = f"./StorageFiles/{file_id}.bin"
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
        cur.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?,?,?,?)",(file_id,payload["filename"],payload["filesize"], int(datetime.now().timestamp()), payload["hash"], ClientHandler.user_id, payload["folder_id"],0))
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
        with open(f"StorageFiles/{file_id}.bin", "rb") as f:
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
def createLink(file_id: str, action: str, db: sqlite3.Connection)-> dict[str, Any]:
    print(file_id, action)
    value = 1 if action == "enable" else 0
    cur = db.cursor()
    cur.execute("UPDATE files SET share_link = ? WHERE file_id = ?",(value, file_id))
    db.commit()
    res = {"status": True}
    if bool(value):
        res["message"] = "Linked Copy to clipboard!"
        res["link"] = f'{socket.gethostbyname(socket.gethostname())}/view_file/{file_id}'
    else:
        res["message"] = "file linked has been disabled."
    return res
def rename(new_name: str, r_id: str | int, type_of_data: str, db:sqlite3.Connection):
    cur = db.cursor()
    print(type_of_data)
    if type_of_data == "file": 
        print("renaming file")
        cur.execute("UPDATE files SET filename = ? WHERE file_id = ?",(new_name, r_id))
    elif type_of_data == "folder":
        print("renaming folder")
        cur.execute("UPDATE folders SET folder_name = ? WHERE folder_id = ?",(new_name, r_id))
    db.commit()
    return {"status": True}
def get_files(folder_id: str, db_conn: sqlite3.Connection) -> dict[str, Any] | dict[str, bool]:
    try:
        cur = db_conn.cursor()
        file_rows =cur.execute("SELECT * FROM files where folder_id = ?",(folder_id,)).fetchall()
        keys: list[str] = ["file_id", "filename", "size","modified","file_hash" ,"user_id","folder_id","share_link"]
        return {"status": True, "files": [dict(zip(keys, file_row)) for file_row in file_rows]}
    except sqlite3.DatabaseError:
        return {"status": False}
def createFolder(conn: sqlite3.Connection, uid: int):
    """creating folder for a user

    Args:
        conn (sqlite3.Connection): sqlite3 db connection
        uid (int): user id

    Returns:
        dict: response dictionary
    """



    try:
        cur = conn.cursor()
        new_folder_id = str(uuid7())
        cur.execute("INSERT INTO folders (folder_id, folder_name, root, user_id) VALUES (?,?,?,?)",(new_folder_id,"new_folder",False,uid))
        conn.commit()
        return {"status": True, "folder_id": new_folder_id}
    except sqlite3.DatabaseError:
         return {"status": False}
def recv_exact(sock: socket.socket, size: int) -> bytes:
    """receiving exact number of bytes from connection

    Args:
        sock (socket.socket): socket object
        size (int): number of bytes

    Raises:
        ValueError: Error when the size is negative.

    Returns:
        bytes: bytes from connection.
    """
    if size < 0:
        raise ValueError("size must be non negative")
    if size == 0:
        return b''
    data = bytearray()
    try:
        while len(data) < size:
            packet: bytes = sock.recv(size - len(data))
            if not packet:
                return b''
            data.extend(packet)
    except socket.error:
        return b''
    return bytes(data)
def DeleteFolder(folder_id: str,user_id: int, db_conn: sqlite3.Connection):
    try:
        cur = db_conn.cursor()
        affected_rows = cur.execute("UPDATE users SET curr_storage = curr_storage - COALESCE((SELECT SUM(size) from files WHERE folder_id = ?),0) WHERE user_id = ?",(folder_id, user_id)).rowcount
        file_ids: list[str] = cur.execute("SELECT file_id FROM files where folder_id = ?",(folder_id,)).fetchall()
        cur.execute("DELETE FROM folders WHERE folder_id = ?",(folder_id,))
        cur.execute("DELETE FROM files where folder_id = ?",(folder_id,))
        db_conn.commit()


        current_storage = cur.execute("SELECT curr_storage from users WHERE user_id = ?", (user_id,)).fetchone()[0] or 0
        for file_id in file_ids:
            file_path = f"./StorageFiles/{file_ids}.bin"
            Path(file_path).unlink(missing_ok=True)

    except (sqlite3.InternalError, OSError):
        return {"status": False,"message": "Could'nt fullfill the request."}
    return {"status": True, "current_storage": current_storage}
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
    db_conn: sqlite3.Connection = ClientHandler.db_conn
    match payload["cmd"]:
        case "login":
            if _user := getUser(payload):
                response = {
                    "status": True,
                    "message": "Welcome back"+payload["username"]+"!",
                    "folders": get_folders_by_id(_user["user_id"]),
                    "curr_storage": _user["curr_storage"],
                    "max_storage": _user["max_storage"],
                }
                ClientHandler.user_id = _user["user_id"]
            else:
                response = {"status": False, "message": "Invalid username or password!"}
        case "register":
            response, user_id = InsertUser(payload)
            if response["status"]: 
                ClientHandler.user_id = user_id
        case "upload":
            response = UploadFile(payload,ClientHandler)
        case "delete":
            if payload["type"] == "file":
                response = DeleteFile(payload["id"], ClientHandler)
            if payload["type"] == "folder":
                response = DeleteFolder(payload["id"],ClientHandler.user_id, db_conn)
        case "save":
            response = SendFile(payload["file_id"], ClientHandler)
        case "handlelink":
            response = createLink(payload["file_id"],payload["action"],db_conn)
        case "rename":
            response = rename(payload["name"], payload["id"],payload["type"], db_conn)
        case "create_folder":
            response = createFolder(db_conn,ClientHandler.user_id)
        case "get_files":
            response = get_files(payload["folder_id"], db_conn)
        case _:
            response = {"status": False, "message": "Invalid command"}
    return response