from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(name, default=""):
    value = os.getenv(name, default)
    return value if value is not None else default


DB_HOST = _env("DB_HOST", "localhost")
DB_PORT = int(_env("DB_PORT", "5432"))
DB_NAME = _env("DB_NAME", "library_db")
DB_USER = _env("DB_USER", "soap_user")
DB_PASSWORD = _env("DB_PASSWORD", "")

SOAP_HOST = _env("SOAP_HOST", "0.0.0.0")
SOAP_PORT = int(_env("SOAP_PORT", "5001"))

SOAP_STATS_USERNAME = _env("SOAP_STATS_USERNAME", "soap_stats")
SOAP_STATS_PASSWORD_HASH = _env("SOAP_STATS_PASSWORD_HASH", "")

# Hash de laboratorio para el modo demostración (contraseña: laboratorio).
# No reutilizar en un servidor con PostgreSQL real.
DEMO_STATS_PASSWORD_HASH = (
    "pbkdf2_sha256$260000$a1b2c3d4e5f60718293a4b5c6d7e8f90$"
    "cd2755edc86e44a9e6ac963529f440b00ec262cf801bef2fd438428d676c40e6"
)

_demo_flag = _env("SOAP_DEMO", "").strip().lower()
if _demo_flag in ("1", "true", "yes", "on"):
    SOAP_DEMO = True
elif _demo_flag in ("0", "false", "no", "off"):
    SOAP_DEMO = False
else:
    SOAP_DEMO = not bool(DB_PASSWORD)

if SOAP_DEMO and not SOAP_STATS_PASSWORD_HASH:
    SOAP_STATS_PASSWORD_HASH = DEMO_STATS_PASSWORD_HASH

WSDL_PATH = BASE_DIR / "wsdl" / "library-classifier.wsdl"
TNS = "http://udem.edu.mx/iac/library-classifier"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"

ALLOWED_MODELS = ("IaaS", "PaaS", "SaaS", "FaaS")
