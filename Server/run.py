from app import create_app


def run():
    app.run("0.0.0.0",443, ssl_context='adhoc')
if __name__ == "__main__":
    
    app = create_app()
    app.run("0.0.0.0",80,debug=True)