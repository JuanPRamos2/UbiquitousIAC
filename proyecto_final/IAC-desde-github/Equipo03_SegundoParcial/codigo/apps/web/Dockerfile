# Una sola imagen para los tres ambientes.
# Lo unico que cambia entre developer, staging y production son las
# variables de entorno que se le inyectan al contenedor.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Las dependencias se instalan antes de copiar el codigo para que un
# cambio de codigo no invalide la capa de dependencias.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# El servicio no corre como root. Requisito de la politica de seguridad
# declarada en el documento de arquitectura de hardware.
RUN useradd --create-home --shell /usr/sbin/nologin bienestar \
 && chown -R bienestar:bienestar /app
USER bienestar

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/salud',timeout=2).status==200 else 1)"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
