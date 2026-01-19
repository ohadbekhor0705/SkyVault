from typing import Literal
from flask import render_template, request, jsonify, Flask, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy.orm.session import Session
from models import File
from protocol2 import *
from copy import copy
def register_routes(app: Flask, tokens: dict):
    """Creating routes for Flask Application.

    Args:
        app (Flask): flask app.
    """    

    @app.route("/")
    def Home() -> str: return render_template("index.html")


    @app.route("/Login")
    def Login(): return render_template("Login.html")

    @app.route("/handle_login", methods=["POST"])
    def HandleLogin() -> tuple[Literal[''], Literal[200]] | tuple[Literal[''], Literal[401]]:
        payload = request.get_json()
        if _user :=getUser(payload): 
            login_user(_user)
            return "", 200
        else: return jsonify({"message": "Invalid Password or Username!"}), 401
    @login_required
    @app.route('/logout')
    def Logout(): return logout_user()

    @app.route("/Browse")
    @login_required
    def Browse():
        files: list[File] | None
        with SessionLocal() as db:
            files = db.query(File)\
            .filter(User.user_id == current_user.user_id).all()
        return render_template("Browse.html",files=files)
    
    @app.route("/file_viewer/<file_id>")
    def file_viewer(file_id: str) -> str:
        db: Session = SessionLocal()
        file: File = copy(db.query(File).filter(File.file_id == file_id).one())
        # check if the select file from DB is owned by the connected user. 
        owner: bool = current_user.is_authenticated and file.user_id == current_user.user_id 
        db.close()
        return render_template("ViewFile.html",file=file,owner=owner)
    