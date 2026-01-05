from app import create_app



def run():
    PORT = 443
    app = create_app()
    app.run("127.0.0.1",PORT, ssl_context='adhoc')


if __name__ == "__main__":
    app = create_app()
    app.run("0.0.0.0",80,debug=True)