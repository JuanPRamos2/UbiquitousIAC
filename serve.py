"""Sirve el mismo Flask en 5000 y 5001."""
import sys
from pathlib import Path
from threading import Thread

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "services" / "soap"))
from app import app  # noqa: E402


def _serve(port):
    make_server("0.0.0.0", port, app, threaded=True).serve_forever()


if __name__ == "__main__":
    print("Flask SOAP/JSON en http://127.0.0.1:5000 y http://127.0.0.1:5001")
    Thread(target=_serve, args=(5000,), daemon=True).start()
    _serve(5001)
