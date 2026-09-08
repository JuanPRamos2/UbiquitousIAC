# Instrucciones: Google Cloud, GitHub y Ubiquitous

Este documento cubre lo que **no se puede hacer solo con código local**: base de datos en el servidor, despliegue del módulo SOAP, repositorio y publicación del reporte.

Estudiante: Juan Pablo Ramos Salazar · matrícula **610248**  
URL del reporte: `https://ubiquitous.udem.edu/~iac-610248/ejercicio03/`

El PDF de clase menciona `ejercicio03` en la parte 11 y `ejercicio04` en un encabezado. Este trabajo se publica como **ejercicio03**.

No se suben `.env`, contraseñas, hashes reutilizables de producción ni dumps con datos personales.

El sitio vive en `UbiquitousIAC`. No se reorganizan `ejercicio01/`, `ejercicio02/`, `tareas/` ni `proyecto_final/`. El ejercicio 03 es una carpeta hermana.

---

## 0. Qué ya está listo en `UbiquitousIAC` (no hace falta rehacerlo)

| Pieza | Ruta |
| --- | --- |
| Monolito Node.js (sin cambios) | `ejercicio02/library/` |
| Reporte web del EG3 | `ejercicio03/index.html` |
| Módulo SOAP Flask | `ejercicio03/library_soap_service/` |
| SQL de tablas SOAP | `ejercicio03/sql/soap_module.sql` |
| App de escritorio con modo SOAP | `ejercicio03/desktop_classifier/` |
| Cliente zeep | `ejercicio03/clients/zeep/` |

Apache en ubiquitous **no ejecuta** Flask. El servicio corre en la VM; el reporte es HTML/CSS/XML/SQL.

---

## 1. PostgreSQL en Google Cloud (misma BD del monolito)

El módulo SOAP **comparte la base** del monolito. No se crea otra instancia “de SOAP”. Sí se crea el rol `soap_user`.

### Opción A — PostgreSQL en la VM de Compute Engine (como el ejercicio 2)

Si la librería ya corre en una VM CentOS/Debian:

```bash
gcloud compute ssh NOMBRE_VM --zone=ZONA
sudo -u postgres psql -c '\l'
```

Usa la misma base (`library_db` o el nombre que ya tengas).

### Opción B — Cloud SQL

Si el monolito apunta a Cloud SQL:

```bash
gcloud sql instances describe INSTANCE
gcloud sql connect INSTANCE --user=postgres --database=library_db
```

Autoriza la IP de la VM SOAP (o usa Auth Proxy). No abras `5432` a `0.0.0.0/0`.

### Aplicar el esquema SOAP (una sola vez)

Desde la máquina que sí tiene `psql` contra esa base:

```bash
psql -h HOST -U postgres -d library_db -f ejercicio03/sql/soap_module.sql
```

Cambia la clave del rol de inmediato (el script deja un placeholder):

```sql
ALTER ROLE soap_user PASSWORD 'una-clave-larga-que-no-va-en-github';
```

Comprueba privilegios:

```sql
SET ROLE soap_user;
SELECT * FROM v_catalogo_conceptos LIMIT 3;
-- Debe fallar:
SELECT * FROM users;
```

### Variables del módulo SOAP

En el servidor, archivo `/etc/library-soap.env` (permisos 600, dueño del servicio):

```
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=library_db
DB_USER=soap_user
DB_PASSWORD=...la misma del ALTER ROLE...
SOAP_STATS_USERNAME=soap_stats
SOAP_STATS_PASSWORD_HASH=...generado con soap.security.hash_password...
```

Generar el hash **en tu laptop**, no en un ticket ni en el HTML:

```bash
cd ejercicio03/library_soap_service
python3 -c "from soap.security import hash_password; print(hash_password('tu-clave-stats'))"
```

La clave de laboratorio local `IacSoapLab2026` **no** debe reutilizarse en GCP.

---

## 2. Desplegar Flask en la VM (gunicorn + nginx)

No publiques el puerto 5000 a Internet.

```bash
sudo useradd -r -s /usr/sbin/nologin soapapp || true
sudo mkdir -p /opt/library_soap_service
sudo rsync -a ejercicio03/library_soap_service/ /opt/library_soap_service/
sudo python3 -m venv /opt/library_soap_service/.venv
sudo /opt/library_soap_service/.venv/bin/pip install -r /opt/library_soap_service/requirements.txt
```

Unit systemd `/etc/systemd/system/library-soap.service`:

```
[Unit]
Description=Library SOAP module
After=network.target postgresql.service

[Service]
User=soapapp
Group=soapapp
EnvironmentFile=/etc/library-soap.env
WorkingDirectory=/opt/library_soap_service
ExecStart=/opt/library_soap_service/.venv/bin/gunicorn --bind 127.0.0.1:5000 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now library-soap
```

Nginx (fragmento): el WSDL y el POST en `/soap/` hacia `http://127.0.0.1:5000/soap`.

Firewall GCP: HTTP/HTTPS al reverse proxy. **No** crear regla `tcp:5000` ni `tcp:5432` a Internet.

Prueba:

```bash
curl -s http://127.0.0.1:5000/soap?wsdl | head
```

El monolito en el puerto 3000 **no se toca**.

---

## 3. GitHub

El código del EG3 ya está dentro de `UbiquitousIAC/ejercicio03/`. Usa el remoto que ya tenga el sitio (o uno privado nuevo). No subas secretos.

```gitignore
.env
**/.env
.venv/
**/__pycache__/
*.class
node_modules/
```

```bash
cd /home/bold/Documents/UbiquitousIAC
git status   # confirma que NO aparece .env
```

No subas un hash de WS-Security que sigas usando en GCP. El ejemplo publicado es un placeholder.

---

## 4. Publicar el reporte en ubiquitous.udem.edu

El servidor de evidencias **no ejecuta Flask ni PostgreSQL**. Solo Apache con HTML, CSS, XML, SQL y ZIP.

Sincroniza el sitio (o al menos `ejercicio03/` más `index.html`, `ejercicios/` y `style.css` para que el hub apunte al EG3):

```bash
cd /home/bold/Documents/UbiquitousIAC
rsync -av --delete \
  --exclude 'ejercicio03/library_soap_service/.env' \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude 'proyecto_final/node_modules' \
  ./ iac-610248@ubiquitous.udem.edu:~/html/
```

Si sólo quieres el ejercicio:

```bash
rsync -av --delete ejercicio03/ iac-610248@ubiquitous.udem.edu:~/html/ejercicio03/
```

En ese segundo caso también hay que subir `index.html` y `ejercicios/index.html` para que el menú del sitio enlace el EG3.

Comprueba en el navegador:

`https://ubiquitous.udem.edu/~iac-610248/ejercicio03/`

Debe verse el índice, el diagrama SVG, el WSDL en `wsdl/` y las evidencias XML.

---

## 5. Capturas que aún debes tomar en vivo (laboratorio)

El código y los XML de ejemplo ya están. El profesor espera **tus** pantallas:

1. GUI clasificando un concepto real y mostrando la respuesta SOAP.
2. GUI ante Fault 409 (registrar el mismo concepto dos veces).
3. `psql` con `SELECT * FROM clasificaciones_cloud;` y `SELECT * FROM clientes_servidos;`
4. `curl` de `ObtenerEstadisticasPorModelo` con UsernameToken correcto e incorrecto (tacha la contraseña).
5. Cliente zeep imprimiendo `ObtenerConceptosPendientes`.

Guarda las PNG en `ejercicio03/img/` y vuelve a sincronizar ubiquitous.

Consulta de verificación:

```sql
SELECT isbn, concept_id, modelo, tipo_cliente, created_at
FROM clasificaciones_cloud
ORDER BY id;

SELECT tipo_cliente, identificador, peticiones, ultima_peticion
FROM clientes_servidos;
```

---

## 6. Cliente de escritorio contra el servidor

```bash
cd ejercicio03/desktop_classifier
javac cloudclassifier/*.java cloudclassifier/*/*.java
java cloudclassifier.CloudClassifierApp
```

En la GUI, endpoint:

- Laboratorio local: `http://localhost:5000/soap`
- VM con nginx: `https://TU_HOST/soap` (si configuraste TLS) o la URL interna de clase

La app **nunca** lleva usuario/contraseña de PostgreSQL.

---

## 7. Lista corta de “ya quedó” vs “lo hago yo en la nube”

| Tarea | ¿Código local? | ¿Tú en GCP/GitHub/Ubiquitous? |
| --- | --- | --- |
| WSDL, Flask, SQL, GUI, zeep, reporte | Hecho | — |
| `psql -f soap_module.sql` en la BD real | — | Sí |
| `ALTER ROLE soap_user PASSWORD` | — | Sí |
| gunicorn + nginx + firewall | — | Sí |
| Push a GitHub sin `.env` | — | Sí |
| `rsync` del sitio a ubiquitous | — | Sí |
| Capturas de GUI y `psql` | — | Sí |
