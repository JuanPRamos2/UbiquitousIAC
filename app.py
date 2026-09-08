"""Punto de entrada Flask del monorepo.

Desde la raíz de UbiquitousIAC:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    export FLASK_APP=app.py
    flask run --host=0.0.0.0 --port=5001

El microservicio vive en app/services/soap/app.py (catálogo del EG02,
SOAP y respuestas XML/JSON).
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOAP_DIR = ROOT / "app" / "services" / "soap"
SOAP_APP = SOAP_DIR / "app.py"

sys.path.insert(0, str(SOAP_DIR))

spec = importlib.util.spec_from_file_location("library_soap_app", SOAP_APP)
module = importlib.util.module_from_spec(spec)
sys.modules["library_soap_app"] = module
spec.loader.exec_module(module)

app = module.app
