"""Entry point: `python run.py` starts the development server."""

from app import create_app

# Build the Flask application using the factory function.
app = create_app()

if __name__ == "__main__":
    # Debug mode comes from FLASK_DEBUG in .env (see app/config.py).
    # It reloads on code changes and shows tracebacks in the browser,
    # so it must stay off anywhere other than a developer's machine.
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEBUG"])
