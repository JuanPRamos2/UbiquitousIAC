"""Microservicio de catálogo: reexporta la app Flask del ejercicio 03."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOAP_DIR = ROOT / "ejercicio03" / "library_soap_service"
SOAP_APP = SOAP_DIR / "app.py"
sys.path.insert(0, str(SOAP_DIR))

spec = importlib.util.spec_from_file_location("library_soap_app", SOAP_APP)
module = importlib.util.module_from_spec(spec)
sys.modules["library_soap_app"] = module
spec.loader.exec_module(module)

app = module.app
