from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def env(name, default=""):
    value = os.getenv(name, default)
    return default if value is None else value


HOST = env("HOST", "0.0.0.0")
PORT = int(env("PORT", "5003"))
JWT_PASSWORD = env("JWT_PASSWORD", "libreria-jwt-compartida")
CACHE_TTL = int(env("AUTHORS_CACHE_TTL", "30") or "30")
SERVICE_NAME = "authors"
