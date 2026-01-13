import socket
import struct
from shutil import rmtree
from typing import Any
from sqlalchemy.orm.session import Session
from sqlalchemy import and_, func, select
from typing import Dict, Any, overload
import bcrypt
from models import User, File, SessionLocal
from datetime import datetime
from uuid6 import uuid7
from models import File, User
import os
from dotenv import load_dotenv
FORMAT = "!I"
CHUNK_SIZE = 1024 *64  # 64 KB



def username_exists(username: str, db: Session | None = None) -> bool: 
    if db is None:
        db = SessionLocal()
    result: bool = db.query(User).filter(User.username == username).first() is not None
    return result
@overload
def getUser(login: int) -> User | None: ...
@overload
def getUser(login: Dict[str,Any]) -> User | None: ...

def getUser(login: dict | int) -> 'User | None':
    """
    Retrieves a user record based on user ID or login credentials.
    Updates failed login attempts and disables the user after 3 failed tries.

    Args:
        login (dict | int): Either:
            - dict with 'username' and 'password' for login
            - int representing user_id

    Returns:
        User | None: SQLAlchemy User object if found, otherwise None.
    """
    user: 'User | None' = None

    with SessionLocal() as db:
        # Fetch user
        if isinstance(login, int):
            user = db.query(User).filter(User.user_id == login).first()
        elif isinstance(login, dict):
            user = db.query(User).filter(
                and_(User.username == login["username"], User.disabled == False)
            ).first()
        if not user:
            return  None
        # Handle login password
        if isinstance(login, dict):
            password_correct: bool = bcrypt.checkpw(
                login["password"].encode(), user.password_hash.encode()
            )
            if not password_correct:
                user.tries = (user.tries or 0) + 1
                if user.tries >= 3:
                    user.disabled = True
                db.commit()  # commit changes while session is active
        # create a new User object that is NOT bound to the session
        detached_user = User(
            user_id=user.user_id,
            username=user.username,
            password_hash=user.password_hash,
            tries=user.tries,
            disabled=user.disabled,
            max_storage=user.max_storage,
            curr_storage=user.curr_storage
        )
        return detached_user  # safe to use anywhere           


    pass

def InsertUser(user: Dict[str,Any]) -> Dict:
    """Insert a new user into the database.

    Args:
        user (Dict[str, Any]): A dictionary containing 'username' and 'password' keys.

    Returns:
        Dict: A dictionary with 'status' indicating success and 'response' message.
    """
    db: Session = SessionLocal()
    try:
        if username_exists(user["username"],db):
          return {"status":False, "message": "This username is already taken"}

        db.add(User(username=user["username"],password_hash=user["password_hash"]))
        db.commit()
        return {
          "status": True,
          "message": f"Welcome to skyVault, {user["username"]}!"
        }

    except Exception as e:
        return {
          "status": False,
          "message": f"{e}"
        }
    finally:
        db.close()

def files_by_id(uid: int) -> list[dict[str,Any]]:
    with SessionLocal() as db:
        files  = db.query(File).filter(File.user_id == uid).all()
        if not files:
            return []
        return [ {"file_id": f.file_id ,"filename": f.filename, "filesize": f.filesize, "modified": f.modified} for f in files]

def UploadFile(payload: dict[str, Any], ClientHandler) -> dict[str,Any] | None:
    """Uploading a file

    Args:
        payload (dict[str, Any]): Containing 
        client (socket.socket): client socket object
        user (User): client user information

    Returns:
        dict[str,Any]: status response from server to client
    """
    fernet = ClientHandler.f
    client: socket.socket = ClientHandler.client
    file_id = str(uuid7())
    file_size = payload["filesize"]
    HEADER_SIZE = struct.calcsize(FORMAT) # Ensure FORMAT matches (e.g., "!I")
    received_unencrypted_bytes = 0
    
    save_path = f"./StorageFiles/{file_id}"
    try:
        if not os.path.exists(save_path):
            os.mkdir(save_path)
        while True:
            #  Read the length of the ENCRYPTED chunk
            header_bytes = recv_exact(client,HEADER_SIZE)
            header = struct.unpack(FORMAT, header_bytes)[0]
            print(f"header: {header}")
            if header == 0: break  #  Check for EOF (The 0 at the end)
            chunk = fernet.decrypt(recv_exact(client, header))
            


        print(f"file file received from: {ClientHandler}")

    
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as e:
        print(e)
        try: os.remove(f"./StorageFiles/{file_id}.encrypted")
        except FileNotFoundError: pass
        return None

    db = SessionLocal()
    user_in_session: User = db.merge(ClientHandler.user)
    user_in_session.curr_storage += payload["filesize"]
    uploaded_file =  File(
            file_id=file_id,
            filename=payload["filename"],
            filesize=file_size,
            modified=int(datetime.now().timestamp()),
            chunks=chunks,
            user_id=ClientHandler.user.user_id
        )
    db.add(uploaded_file)
    db.commit()
    db.close()
    return {"status": True, "message": payload["filename"]+" Uploaded!","file_id":file_id}


def SendFile(file_id: str, ClientHandler) -> None:
    """_summary_

    Args:
        client (socket.socket): _description_
        filename (str): _description_

    Returns:
        dict[str, Any]: _description_
    """
    global CHUNK_SIZE
    client: socket.socket = ClientHandler.client
    try:
        return None

    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        pass
    return None

def DeleteFile(file_ids: list[str], ClientHandler)-> dict[str, Any]:
    """Deleting files by file ids and updating current storage of user

    Args:
        file_ids (list[str]): A list of file ids.
        user (User): User Object.
    Returns:
        dict[str, Any]: Response from server.
    """    
    try:
        with SessionLocal() as db:
            print(file_ids)
            # get the total size of all deleted files:
            # generates SELECT SUM(filesize) FROM Files WHERE file_id IN {file_ids}
            total_size: int = db.query(func.sum(File.filesize))\
                                .filter(File.file_id.in_(file_ids))\
                                .scalar() or 0
            # delete all the files from the db
            db.query(File)\
            .filter(File.file_id.in_(file_ids))\
            .delete(synchronize_session=False)
            # attach user to the session
            user_in_session: User = db.merge(ClientHandler.user)
            user_in_session.curr_storage = user_in_session.curr_storage - total_size
            db.commit()
        for file_id in file_ids:
            rmtree(f"./StorageFiles/{file_id}")
        return {"status": True, "message": "File(s) deleted successfully"}
    except Exception as e:
        print(e)
        return {"status": False, "message": "The server Couldn't delete this file(s)."}

def createLink(file_id: str)-> dict[str, Any]:
    try:
        with SessionLocal() as db:
            file: File = db.query(File).filter(File.file_id == file_id).one()
        return {"status": True,"message": "Share link created!", "link": ""}
    except:
        return {"status": False,"message": "Couldn't Create share link."}

def get_file_names(directory: str) -> list[str]:
    """Return a list of file names in the given directory (non-recursive)."""
    with os.scandir(directory) as entries:
        return [entry.name for entry in entries if entry.is_file()]

def handle_client_request(payload: dict[str, Any],ClientHandler) -> dict[str, Any] | None:
    """Handling clients requests

    Args:
        payload (dict[str, Any]): client's requests with parameters.
        client (socket.socket): client socket object.
        user (User): client's user data.

    Returns:
        dict[str, Any] | None: Server Response.
    """    
    response: dict[str, Any] | None = {}
    match payload["cmd"]:
        case "upload":
            response = UploadFile(payload,ClientHandler)
        case "delete":
            response = DeleteFile(payload["ids"], ClientHandler)
        case "save":
            response = SendFile(payload["file_id"], ClientHandler)
        case "createLink":
            response = createLink(payload["file_id"])
        case _:
            response = {"status": False, "message": "Invalid command"}
    return response

def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            raise ConnectionError("Socket closed unexpectedly")
        data += packet
    return data
