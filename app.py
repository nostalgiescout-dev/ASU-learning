from kechafa_app import create_app
import os
import socket

# Module-level application object so Gunicorn can find it:
#   gunicorn app:application
application = create_app(os.environ.get("FLASK_ENV", "production"))

if __name__ == "__main__":
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", 5000))
    ssl_mode = os.environ.get("FLASK_SSL_MODE", "").strip().lower()
    ssl_cert = os.environ.get("SSL_CERT_FILE", "").strip()
    ssl_key = os.environ.get("SSL_KEY_FILE", "").strip()
    ssl_context = None

    if ssl_mode == "adhoc":
        ssl_context = "adhoc"
    elif ssl_cert and ssl_key:
        ssl_context = (ssl_cert, ssl_key)

    scheme = "https" if ssl_context else "http"

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        print(f"Running on {scheme}://{host}:{port} (local IP: {scheme}://{local_ip}:{port})")
    except Exception:
        pass

    application.run(host=host, port=port, debug=True, ssl_context=ssl_context)
