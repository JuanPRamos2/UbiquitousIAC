# Contenedor propio de configuration-service.
# El contexto de build es apps/microservicios/ para poder copiar la
# libreria comun, que los doce servicios comparten.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY comun /tmp/comun
RUN pip install --no-cache-dir /tmp/comun && rm -rf /tmp/comun

COPY configuration-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY configuration-service/ .

RUN useradd --create-home --shell /usr/sbin/nologin servicio && chown -R servicio /app
USER servicio

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live',timeout=2).status==200 else 1)"

CMD ["gunicorn","-b","0.0.0.0:8000","-w","2","-k","gthread","--threads","2","--access-logfile","-","app:app"]
