from flask import Flask
from models import User
from protocol import *
from flask_login import LoginManager
from routes import  register_routes
import os
def create_app(tokens: dict = {}) -> Flask:

    app = Flask(__name__)
    app.config['SECRET_KEY'] = str(os.urandom(24))


    register_routes(app, tokens)

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(uid: int) -> User | None:
        with SessionLocal() as db:
            return db.query(User).filter(User.user_id == uid).first()
    return app