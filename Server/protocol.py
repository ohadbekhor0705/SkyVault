# Core networking and data handling
import socket
import struct

# Type hints for Python
from typing import Any
from typing import Dict, Any, overload

# Security and cryptography
import bcrypt
from cryptography.fernet import Fernet

# Time and ID generation
from datetime import datetime
from uuid6 import uuid7
from uuid import uuid4

# File system and database operations
import os
from pathlib import Path
import sqlite3

# ==================== Configuration Constants ====================
DB_PATH = "./mydb.db"  # Path to SQLite database
FORMAT = "!I"  # Network format: big-endian unsigned int (4 bytes)
CHUNK_SIZE = 1024 * 64  # File transfer chunk size: 64 KB
connected_user_ids: list[int] = []  # Track currently active user sessions
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


# ==================== Encryption Utilities ====================
from dotenv import load_dotenv
import os

def load_encryption_key(env_path=".env", key_name="ENCRYPTION_KEY"):
    """
    Load the encryption key from a .env file.
    
    Args:
        env_path (str): Path to the .env file.
        key_name (str): The name of the key in the .env file.

    Returns:
        bytes: Encryption key as bytes.
    
    Raises:
        FileNotFoundError: If the .env file does not exist.
        ValueError: If the key is not found in the .env file.
    """
    # Load environment variables
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"{env_path} does not exist.")
    
    load_dotenv(dotenv_path=env_path)
    
    key = os.getenv(key_name)
    if not key:
        raise ValueError(f"{key_name} not found in {env_path}.")
    
    return key.encode()  # Return as bytes

# Initialize Fernet cipher for server-side file encryption
file_fernet = Fernet(load_encryption_key())

# ==================== User Management Functions ====================
def username_exists(username: str, **kwargs) -> bool:
    # Check if username already exists in database
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
        dict[str, Any] | None: User record as dictionary or None if not found
    """
    keys = ["user_id", "username", "password_hash", "max_storage", "curr_storage", "tries", "disabled"]
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        res: dict[str, Any] | None = None
        if isinstance(login, int):
            # Fetch user by ID
            values = cur.execute("SELECT * FROM users WHERE user_id == ?",(login,)).fetchone()
            if not values:
                return None
        if isinstance(login, dict):
            # Fetch user by username
            values = cur.execute("SELECT * FROM users WHERE username == :username AND disabled = 0",login).fetchone()
            if not values:
                return None
            # Verify password hash
            elif not bcrypt.checkpw(login["password"].encode(),values[2]):
                # Increment failed attempts or disable account
                if values[5] < 3:
                    cur.execute("UPDATE users SET tries = tries + 1 WHERE username = :username",login)
                else:
                    cur.execute("UPDATE users SET disabled = 1 WHERE username = :username",login)
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
        # Check if username is already in use
        if username_exists(user["username"],cursor=cur):
            return {"status":False, "message": "This username is already taken"}, None
        # Hash password and insert new user
        cur.execute(
            "INSERT INTO users(username, password_hash) VALUES (?, ?)",(
                user["username"],
                bcrypt.hashpw(user["password"].encode("utf-8"),bcrypt.gensalt())
            )
        )
        # Retrieve newly created user ID
        user_id: int = cur.execute("SELECT user_id FROM users WHERE username == :username", user).fetchone()[0]
        # Create default 'main' folder as system folder for the new user
        cur.execute("INSERT INTO folders(folder_id,folder_name, is_system, user_id) VALUES (?,?,?,?)",(str(uuid7()),"main",True,user_id))
        conn.commit()
    # Return success response with user folders and default max storage (1 GB)
    return {"status": True,"message": "Welcome to skyVault!","curr_storage": 0,"max_storage": 1073741824, "folders": get_folders_by_id(user_id)}, user_id

def files_by_id(uid: int) -> list[dict[str, Any]]:
    """Retrieve all files for a specific user."""
    with sqlite3.connect("./mydb.db") as conn:
        cur = conn.cursor()
        # Fetch all files for the user
        files = cur.execute("SELECT * FROM files WHERE user_id = ?",(uid,)).fetchall()
        keys: list[str] = ["file_id", "filename", "size","modified","file_hash" ,"user_id","folder_id","share_link"]
        return [dict(zip(keys, file)) for file in files]

def get_folders_by_id(uid: int):
    """Retrieve all folders for a specific user."""
    keys = ["folder_id","folder_name","is_system", "user_id"]
    with sqlite3.connect("./mydb.db") as conn:
        cur = conn.cursor()
        # Fetch all folders for the user
        folders = cur.execute("SELECT * FROM folders WHERE user_id = ?",(uid,)).fetchall()
        return [dict(zip(keys, folder)) for folder in folders]

def UploadFile(payload: dict[str, Any], ClientHandler) -> dict[str,Any] | None:
    """Uploading a file to cloud
    Args:
        payload (dict[str, Any]): Containing file metadata
        ClientHandler: Handler object with client socket and encryption key

    Returns:
        dict[str,Any]: status response from server to client
    """
    fernet = ClientHandler._fernet
    client: socket.socket = ClientHandler.client
    file_id = str(uuid7())  # Generate unique file ID
    file_size = payload["filesize"]
    HEADER_SIZE = struct.calcsize(FORMAT)  # 4 bytes: unsigned int for chunk length
    
    # File stored with encryption in binary format
    save_path = f"./StorageFiles/{file_id}.bin"
    try:
        # Create storage directory if needed
        if not os.path.exists("StorageFiles"):
            os.mkdir("StorageFiles")
        with open(save_path,"ab") as f:
            while True:
                # Read chunk header (client-encrypted data length)
                header_bytes = recv_exact(client,HEADER_SIZE)
                header = struct.unpack(FORMAT, header_bytes)[0]
                if header == 0: break  # End of file marker (0 indicates EOF)
                # Decrypt client's encryption, then re-encrypt with server key for storage
                original_chunk = fernet.decrypt(recv_exact(client, header))
                file_encryption = file_fernet.encrypt(original_chunk)
                # Write: [4-byte length][encrypted data]
                f.write(struct.pack("!I", len(file_encryption)) + file_encryption)        
        print(f"file received from: {ClientHandler}.")
        # Update database: increment user's storage and record new file metadata
        cur: sqlite3.Cursor =  ClientHandler.db_conn.cursor()
        cur.execute("UPDATE users SET curr_storage = curr_storage + ? WHERE user_id = ? ", (payload["filesize"],ClientHandler.user_id))
        # Insert file record with metadata (hash for integrity, timestamp, folder association)
        cur.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?,?,?,?)",(file_id,payload["filename"],payload["filesize"], int(datetime.now().timestamp()), payload["hash"], ClientHandler.user_id, payload["folder_id"],0))
        ClientHandler.db_conn.commit()

    
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as e:
        # On connection failure, clean up partial file
        try: os.remove(save_path)
        except FileNotFoundError: pass
        return None

    return {"status": True, "message": payload["filename"]+" Uploaded!","file_id":file_id}

def SendFile(file_id: str, ClientHandler) -> None: 
    """Send an encrypted file to client in chunks.
    
    Args:
        file_id (str): ID of the file to send
        ClientHandler: Handler object with client socket and encryption key
    """
    client: socket.socket = ClientHandler.client
    try:
        ClientHandler.write_to_log(f"Sending file to {ClientHandler}...")
        with open(f"StorageFiles/{file_id}.bin", "rb") as f:
            while header := f.read(4):
                # Read encrypted chunk from storage
                chunk_size = struct.unpack(FORMAT, header)[0]
                original_chunk: bytes = file_fernet.decrypt(f.read(chunk_size))
                # Re-encrypt with client's encryption key and send
                encrypted: bytes = ClientHandler._fernet.encrypt(original_chunk)
                client.sendall(struct.pack(FORMAT, len(encrypted)) +encrypted)
            # Send EOF marker (0 indicates end of file)
            client.sendall(struct.pack(FORMAT,0))
        ClientHandler.write_to_log(f"finished sending file to {ClientHandler}!")
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        pass
    return None

def DeleteFile(file_id, ClientHandler)-> dict[str, Any]:
    """
    Delete a file and update user's current storage usage.

    Args:
        file_id (str): ID of file to delete
        ClientHandler: Handler object with database connection
        
    Returns:
        dict[str, Any]: Response status and message
    """ 
    try:
        cur: sqlite3.Cursor = ClientHandler.db_conn.cursor()
        # Use transaction to ensure atomic deletion and storage update
        cur.execute("BEGIN TRANSACTION;")
        # Subtract file size from user's current storage
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
        # Delete the file record from database
        cur.execute(
            """
            DELETE FROM files
            WHERE file_id = ?;
            """, (file_id,)
        )
        ClientHandler.db_conn.commit()
        # Remove physical file from storage
        os.remove(f"./StorageFiles/{file_id}.encrypted")
        return {"status": True, "message": "File deleted successfully!"}
    except Exception as e:
        print(e)
        return {"status": False, "message": "An Error occurred when the server was trying to delete this file"}


def rename(new_name: str, r_id: str | int, type_of_data: str, db:sqlite3.Connection):
    """Rename a file or folder."""
    cur = db.cursor()
    # Determine whether to update file or folder name
    if type_of_data == "file": 
        print("renaming file")
        cur.execute("UPDATE files SET filename = ? WHERE file_id = ?",(new_name, r_id))
    elif type_of_data == "folder":
        print("renaming folder")
        cur.execute("UPDATE folders SET folder_name = ? WHERE folder_id = ?",(new_name, r_id))
    db.commit()
    return {"status": True}

def get_files(folder_id: str, db_conn: sqlite3.Connection) -> dict[str, Any] | dict[str, bool]:
    """Retrieve all files in a specific folder."""
    try:
        cur = db_conn.cursor()
        # Fetch all files belonging to this folder
        file_rows =cur.execute("SELECT * FROM files where folder_id = ?",(folder_id,)).fetchall()
        keys: list[str] = ["file_id", "filename", "size","modified","file_hash" ,"user_id","folder_id"]
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
        # Generate unique folder ID using UUID v7
        new_folder_id = str(uuid7())
        # Create new user folder (not a system folder)
        cur.execute("INSERT INTO folders (folder_id, folder_name, is_system, user_id) VALUES (?,?,?,?)",(new_folder_id,"new_folder",False,uid))
        conn.commit()
        return {"status": True, "folder_id": new_folder_id}
    except sqlite3.DatabaseError:
         return {"status": False}

def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive exact number of bytes from socket connection.
    
    Blocks until all requested bytes are received or connection closes.

    Args:
        sock (socket.socket): Socket object to receive from
        size (int): Exact number of bytes to receive

    Raises:
        ValueError: If size is negative

    Returns:
        bytes: Received bytes (empty if connection closed)
    """
    if size < 0:
        raise ValueError("size must be non negative")
    if size == 0:
        return b''
    data = bytearray()
    try:
        # Keep receiving until we have all requested bytes
        while len(data) < size:
            packet: bytes = sock.recv(size - len(data))
            if not packet:
                # Connection closed or no more data
                return b''
            data.extend(packet)
    except socket.error:
        # Handle network errors gracefully
        return b''
    return bytes(data)

def DeleteFolder(folder_id: str,user_id: int, db_conn: sqlite3.Connection):
    """Delete a folder and all files within it, updating user storage."""
    try:
        cur = db_conn.cursor()
        # Subtract total size of all files in folder from user's storage
        cur.execute("UPDATE users SET curr_storage = curr_storage - COALESCE((SELECT SUM(size) from files WHERE folder_id = ?),0) WHERE user_id = ?",(folder_id, user_id))
        # Get all file IDs in folder for cleanup
        file_ids: list[str] = cur.execute("SELECT file_id FROM files where folder_id = ?",(folder_id,)).fetchall()
        # Delete folder and all associated files from database
        cur.execute("DELETE FROM folders WHERE folder_id = ?",(folder_id,))
        cur.execute("DELETE FROM files where folder_id = ?",(folder_id,))
        db_conn.commit()

        # Get updated storage for response
        current_storage = cur.execute("SELECT curr_storage from users WHERE user_id = ?", (user_id,)).fetchone()[0] or 0
        # Remove physical files from storage
        for file_id in file_ids:
            file_path = f"./StorageFiles/{file_id}.bin"
            Path(file_path).unlink(missing_ok=True)

    except (sqlite3.InternalError, OSError):
        return {"status": False,"message": "Couldn't fulfill the request."}
    return {"status": True, "current_storage": current_storage}

def handle_client_request(payload: dict[str, Any],ClientHandler) -> dict[str, Any] | None:
    """Route client request to appropriate handler function."""
    
    response: dict[str, Any] | None = {}
    ClientHandler.write_to_log(f"fetching {ClientHandler}'s Request: "+payload["cmd"])
    db_conn: sqlite3.Connection = ClientHandler.db_conn
    # Route to appropriate handler based on command
    match payload["cmd"]:
        case "login":
            # Authenticate user with username/password
            if _user := getUser(payload):
                # Check if user not already logged in
                if _user["user_id"] not in connected_user_ids:
                    response = {
                        "status": True,
                        "message": "Welcome back"+payload["username"]+"!",
                        "folders": get_folders_by_id(_user["user_id"]),
                        "curr_storage": _user["curr_storage"],
                        "max_storage": _user["max_storage"],
                    }
                    # Track active session
                    connected_user_ids.append(_user["user_id"])
                    ClientHandler.user_id = _user["user_id"]
                else:
                    # Prevent simultaneous login on same account
                    response = {"status": False, "message": "this accounts is already in use"}
            else:
                response = {"status": False, "message": "Invalid username or password!"}
        case "register":
            # Create new user account
            response, user_id = InsertUser(payload)
            if response["status"]: 
                # Auto-login new user
                ClientHandler.user_id = user_id
                connected_user_ids.append(user_id)
        case "logout":
            # Remove user from active sessions
            if ClientHandler.user_id in connected_user_ids:
                connected_user_ids.remove(ClientHandler.user_id)
            response = {"status": True}
        case "upload":
            # Receive and store encrypted file
            response = UploadFile(payload,ClientHandler)
        case "delete":
            # Delete file or folder and update storage
            if payload["type"] == "file":
                response = DeleteFile(payload["id"], ClientHandler)
            if payload["type"] == "folder":
                response = DeleteFolder(payload["id"],ClientHandler.user_id, db_conn)
        case "save":
            # Send encrypted file to client
            response = SendFile(payload["file_id"], ClientHandler)
        case "rename":
            # Rename file or folder
            response = rename(payload["name"], payload["id"],payload["type"], db_conn)
        case "create_folder":
            # Create new folder
            response = createFolder(db_conn,ClientHandler.user_id)
        case "get_files":
            # Retrieve all files in folder
            response = get_files(payload["folder_id"], db_conn)
        case "ping":
            # Respond to client ping
            response = {"status": True, "message": "Pong!"}
        case _:
            # Unknown command
            response = {"status": False, "message": "Invalid command"}
    return response