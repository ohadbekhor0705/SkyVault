from typing import Any
from sqlalchemy.sql.schema import Column
from typing import Dict, Tuple, Any, overload
from sqlalchemy import (
create_engine, Column, Integer, String, Boolean, ForeignKey, Text, BigInteger )
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, scoped_session
from flask_login import UserMixin
# -------------------------
# Database setup
# -------------------------
Base = declarative_base()

class User(Base, UserMixin):
    """
    ORM model for a user in the system.
    Attributes:
        user_id (int): Primary key, auto-incremented.
        username (str): Username of the user.
        password_hash (str): Hashed password.
        max_storage (int): Maximum allowed storage in bytes.
        curr_storage (int): Current storage used.
        tries (int): Login or action attempt count.
        disabled (bool): Whether the user is disabled.
        files (list[File]): Relationship to File objects.
    """
    __tablename__: str = "users"

    user_id: Column[int] = Column(Integer, primary_key=True, autoincrement=True)
    username: Column[str] = Column(String(255), nullable=False)
    password_hash: Column[str] = Column(Text, nullable=False)
    max_storage: Column[int] = Column(BigInteger, default=1073741824)
    curr_storage: Column[int] = Column(BigInteger, default=0)
    tries: Column[int] = Column(Integer, default=0)
    disabled: Column[bool] = Column(Boolean, default=False)

    files= relationship("File", back_populates="user", cascade="all, delete-orphan")
    def get_id(self):
        # Return the specific field used for your primary key as a string
        return str(self.user_id)
    def __repr__(self):
        return f"<User id={self.user_id} username='{self.username}'>"
    def toDict(self):# -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "max_storage": self.max_storage,
            "curr_storage": self.curr_storage,
            "tries":self.tries
        }

class File(Base, UserMixin):
    """
    ORM model for a file uploaded by a user.

    Attributes:
        file_id (str): Primary key, unique ID of the file.
        filename (str): Name of the file.
        filesize (int): Size in bytes.
        modified (int): Timestamp or integer representing last modification.
        user_id (int): Foreign key linking to User.
        user (User): Relationship to owning User.
    """
    __tablename__: str = "files"

    file_id: Column[str] = Column(String(255), primary_key=True)
    filename: Column[str] = Column(String(255), nullable=False)
    filesize: Column[int] = Column(Integer, nullable=False)
    modified: Column[int] = Column(Integer, nullable=False)
    user_id: Column[int] = Column(Integer, ForeignKey("users.user_id"))
    user = relationship("User", back_populates="files")


# SQLite engine (thread-safe)
engine = create_engine(
    "sqlite:///mydb.db", echo=False, connect_args={"check_same_thread": False}
)
Base.metadata.create_all(engine)

# Thread-safe session
SessionLocal = scoped_session(sessionmaker(bind=engine))