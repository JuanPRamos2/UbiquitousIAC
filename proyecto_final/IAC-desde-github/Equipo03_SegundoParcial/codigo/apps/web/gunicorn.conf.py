"""
Configuración de Gunicorn.

El numero de procesos de trabajo se fija por variable de entorno y no por
formula automatica: la medicion del documento de arquitectura de hardware
se hizo con cuatro trabajadores, y los umbrales de escalamiento estan
expresados contra ese numero. Cambiarlo invalida esos umbrales.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PUERTO', '8000')}"
workers = int(os.environ.get("GUNICORN_WORKERS", "4"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 20
max_requests = 1000          # recicla procesos para acotar fugas de memoria
max_requests_jitter = 100    # evita que los cuatro reinicien a la vez
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("NIVEL_BITACORA", "info").lower()
