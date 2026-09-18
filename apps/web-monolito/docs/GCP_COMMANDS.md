# Comandos GCP SDK CLI

No se publican llaves, tokens ni secretos. Sustituya `PROJECT`, zona y cuenta de servicio locales.

## Proyecto y autenticación

```bash
gcloud auth login
gcloud config set project PROJECT_ID
gcloud config set compute/zone us-central1-a
```

## Instancia CentOS Stream 10

Dimensionamiento: `e2-medium` (2 vCPU, 4 GB) es suficiente para Node + PostgreSQL + Apache/NGINX en un ejercicio académico. `e2-small` también funciona si el presupuesto es más estricto; se evitó `f1-micro` porque PostgreSQL y Node juntos saturan 0.6 GB.

```bash
gcloud compute instances create library-monolith \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=centos-stream-10 \
  --image-project=centos-cloud \
  --boot-disk-size=30GB \
  --tags=http-server,library-ssh
```

## Firewall

```bash
gcloud compute firewall-rules create allow-http-library \
  --allow=tcp:80 \
  --target-tags=http-server \
  --description="HTTP para reverse proxy /library"

# SSH suele existir como default-allow-ssh. No abrir TCP/3000 a 0.0.0.0/0.
```

## Conexión y software base (en la VM)

```bash
gcloud compute ssh library-monolith --zone=us-central1-a

sudo dnf update -y
sudo dnf install -y postgresql-server postgresql contrib nginx nodejs git
```

Node debe quedar escuchando en `127.0.0.1:3000`. El tráfico público entra por el puerto 80 del reverse proxy.

## Qué no hacer

- No crear reglas `tcp:3000` hacia Internet.
- No pegar JSON de service accounts en este archivo.
- No copiar `~/.ssh/id_rsa` a ubiquitous.
