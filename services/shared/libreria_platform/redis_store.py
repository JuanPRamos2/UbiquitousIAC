"""Cliente Redis con tiempos de espera, autenticación por URL y modo memoria.

REDIS_URL tiene la forma redis://:password@host:6379/0.
memory:// sirve para pruebas: no abre la red.
Las lecturas de caché pueden seguir si Redis no responde.
Sesión, revocación y autorización no: si Redis falla, la operación se rechaza.
"""
import fnmatch
import os
import threading
import time


class RedisUnavailable(Exception):
    """Redis no respondió. La operación que depende de él debe abortarse."""


class MemoryBackend:
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def _alive(self, key):
        item = self._data.get(key)
        if item is None:
            return None
        expires = item["expires"]
        if expires is not None and expires <= time.time():
            del self._data[key]
            return None
        return item

    def ping(self):
        return True

    def get(self, key):
        with self._lock:
            item = self._alive(key)
            return None if item is None else item["value"]

    def setex(self, key, ttl, value):
        with self._lock:
            self._data[key] = {"value": str(value), "expires": time.time() + int(ttl)}

    def delete(self, *keys):
        with self._lock:
            removed = 0
            for key in keys:
                if key in self._data:
                    del self._data[key]
                    removed += 1
            return removed

    def keys(self, pattern):
        with self._lock:
            found = []
            for key in list(self._data):
                if self._alive(key) is not None and fnmatch.fnmatch(key, pattern):
                    found.append(key)
            return found

    def incr(self, key):
        with self._lock:
            item = self._alive(key)
            current = int(item["value"]) if item else 0
            current += 1
            self._data[key] = {"value": str(current), "expires": None}
            return current


class RedisStore:
    def __init__(self):
        self._client = None
        self._url = None
        self._lock = threading.Lock()
        self.errors = 0
        self.hits = 0
        self.misses = 0

    def url(self):
        value = os.getenv("REDIS_URL", "").strip()
        if not value:
            raise RedisUnavailable("Falta REDIS_URL. La sesión y la revocación no pueden continuar.")
        return value

    def backend(self):
        url = self.url()
        with self._lock:
            if self._client is not None and self._url == url:
                return self._client
            if url.startswith("memory://"):
                self._client = MemoryBackend()
            else:
                import redis

                self._client = redis.Redis.from_url(
                    url,
                    socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "2")),
                    socket_timeout=float(os.getenv("REDIS_TIMEOUT", "2")),
                    health_check_interval=30,
                    decode_responses=True,
                )
            self._url = url
            return self._client

    def ping(self):
        try:
            client = self.backend()
            if isinstance(client, MemoryBackend):
                return True
            return bool(client.ping())
        except Exception:
            self.errors += 1
            self._client = None
            return False

    def _call(self, fn, optional):
        try:
            return fn(self.backend())
        except RedisUnavailable:
            self.errors += 1
            self._client = None
            if optional:
                return None
            raise
        except Exception as exc:
            self.errors += 1
            self._client = None
            if optional:
                return None
            raise RedisUnavailable("Redis no está disponible.") from exc

    def get(self, key, optional=False):
        value = self._call(lambda client: client.get(key), optional)
        return value

    def setex(self, key, ttl, value, optional=False):
        saved = self._call(lambda client: client.setex(key, int(ttl), value) or True, optional)
        return bool(saved) if optional else saved is not None or saved is True

    def delete(self, *keys, optional=False):
        if not keys:
            return 0
        removed = self._call(lambda client: client.delete(*keys), optional)
        return 0 if removed is None else removed

    def delete_pattern(self, pattern, optional=False):
        def _wipe(client):
            if isinstance(client, MemoryBackend):
                found = client.keys(pattern)
                return client.delete(*found) if found else 0
            removed = 0
            cursor = 0
            while True:
                cursor, found = client.scan(cursor=cursor, match=pattern, count=200)
                if found:
                    removed += client.delete(*found)
                if cursor == 0:
                    break
            return removed

        result = self._call(_wipe, optional)
        return 0 if result is None else result

    def incr(self, key, optional=True):
        return self._call(lambda client: client.incr(key), optional)

    def mark_hit(self):
        self.hits += 1
        self.incr("metrics:cache:hits")

    def mark_miss(self):
        self.misses += 1
        self.incr("metrics:cache:misses")

    def snapshot(self):
        connected = self.ping()
        payload = {
            "connected": connected,
            "errors": self.errors,
            "cacheHits": self.hits,
            "cacheMisses": self.misses,
        }
        if not connected:
            payload["status"] = "error"
            return payload
        try:
            hits = self.get("metrics:cache:hits", optional=True)
            misses = self.get("metrics:cache:misses", optional=True)
            if hits is not None:
                payload["cacheHits"] = int(hits)
            if misses is not None:
                payload["cacheMisses"] = int(misses)
        except Exception:
            pass
        payload["status"] = "ok"
        return payload


store = RedisStore()
