"""Flask en :5001 — SOAP + XML/JSON. Carga services/soap/app.py."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOAP_DIR = ROOT / "services" / "soap"
sys.path.insert(0, str(SOAP_DIR))

spec = importlib.util.spec_from_file_location("library_soap_app", SOAP_DIR / "app.py")
module = importlib.util.module_from_spec(spec)
sys.modules["library_soap_app"] = module
spec.loader.exec_module(module)

app = module.app
