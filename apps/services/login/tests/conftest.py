import os

os.environ["REDIS_URL"] = "memory://"

from app import app  # noqa: E402


def client():
    app.config["TESTING"] = True
    return app.test_client()
