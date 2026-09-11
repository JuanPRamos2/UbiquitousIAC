"""Microservicio Flask pedido por la práctica: app/services/soap/app.py

Carga el mismo código canónico de services/soap/app.py (SOAP + XML/JSON).

    SOAP_DEMO=1 PYTHONPATH=services/soap python3 app/services/soap/app.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOAP_DIR = ROOT / "services" / "soap"
sys.path.insert(0, str(SOAP_DIR))

spec = importlib.util.spec_from_file_location("library_soap_app", SOAP_DIR / "app.py")
module = importlib.util.module_from_spec(spec)
sys.modules["library_soap_app"] = module
spec.loader.exec_module(module)

app = module.app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
