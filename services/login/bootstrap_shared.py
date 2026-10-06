"""Localiza services/shared sin acoplar este proceso a otro microservicio."""
import sys
from pathlib import Path


def install():
    here = Path(__file__).resolve()
    for parent in here.parents:
        shared = parent / "services" / "shared"
        if (shared / "libreria_platform").is_dir():
            path = str(shared)
            if path not in sys.path:
                sys.path.insert(0, path)
            return path
    raise RuntimeError("No se encontró services/shared")


install()
