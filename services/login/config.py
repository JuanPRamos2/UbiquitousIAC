from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def env(name, default=""):
    value = os.getenv(name, default)
    return default if value is None else value


HOST = env("LOGIN_HOST", "0.0.0.0")
PORT = int(env("LOGIN_PORT", "5000"))
SECRET_KEY = env("SECRET_KEY") or env("SESSION_SECRET") or "libreria-login-demo-secret"
SESSION_MINUTES = int(env("SESSION_MINUTES", "30"))
SESSION_GRACE_SECONDS = int(env("SESSION_GRACE_SECONDS", "60"))

# JWT_SECRET_KEY es la clave HMAC compartida. JWT_PASSWORD solo se usa si esa
# variable no está definida: su hash SHA-256 mantiene el contrato anterior.
JWT_PASSWORD = env("JWT_PASSWORD", "libreria-jwt-compartida")
JWT_MINUTES = int(env("JWT_MINUTES", "20"))
REFRESH_MINUTES = int(env("REFRESH_MINUTES", "1440"))
JWT_ISSUER = "login"
JWT_AUDIENCE = "libreria"
REDIS_URL = env("REDIS_URL", "")

DB_HOST = env("DB_HOST", "127.0.0.1")
DB_PORT = int(env("DB_PORT", "5433"))
DB_NAME = env("DB_NAME", "library_db")
DB_USER = env("DB_USER", "library_user")
DB_PASSWORD = env("DB_PASSWORD", "666")

MAIL_HOST = env("MAIL_HOST", "")
MAIL_PORT = int(env("MAIL_PORT", "587") or "587")
MAIL_USER = env("MAIL_USER", "")
MAIL_PASSWORD = env("MAIL_PASSWORD", "")
MAIL_FROM = env("MAIL_FROM", "noreply@libreria.local")
MAIL_STARTTLS = env("MAIL_STARTTLS", "1").strip().lower() in ("1", "true", "yes", "on")
VERIFICATION_HOURS = int(env("VERIFICATION_HOURS", "24"))

DSN = (
    f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
    f"user={DB_USER} password={DB_PASSWORD} connect_timeout=5"
)
