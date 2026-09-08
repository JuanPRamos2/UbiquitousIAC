# Auditoría del PMF — Bienestar Nexum (EQUIPO 03)

Auditoría contra los criterios de logro del primer parcial (SC3705) y las reglas
de la arquitectura políglota. Fecha de revisión: 2026-08-30.

Leyenda: **Cumple** · **Parcial** · **Faltaba (corregido en esta iteración)** · **Fuera de alcance del PMF**

## 1. Checklist de cumplimiento

### 1.1 Demostración técnica del sistema web mínimo funcional

| Criterio | Estado | Evidencia |
| --- | --- | --- |
| Inicio de sesión, cierre de sesión y JWT básico | **Cumple** | `POST /api/auth/login` firma JWT (`sub`, `perfil`, `jti`, 15 min). `POST /api/auth/logout` escribe `revoked:{jti}` y borra `session:{jti}`. Clave verificada en PostgreSQL con `pgcrypto` (`crypt` + Blowfish). |
| Acceso diferenciado por perfil (RBAC) | **Cumple** | `COLAB`, `LIDER_TURNO`, `AUDITOR`, `ADMIN_SISTEMA` en `usuarios.perfil`. Middleware `autorizar(...)` en cada ruta. El líder solo ve agregados de su unidad. COLAB no lee agregados ni bitácora. |
| Al menos dos catálogos conectados a PostgreSQL | **Cumple** | `GET /api/catalogos/unidades` (`organizacion.v_unidades_activas`) y `GET /api/catalogos/campanias` (`catalogo.campania`). Además: instrumentos y reactivos. |
| Proceso principal: encuesta (valida PG, inserta Mongo) | **Cumple** | Valida seudónimo, campaña, asignación a unidad, consentimiento vigente y escala de reactivos en PostgreSQL. Inserta `respuestas_encuesta` con array embebido `respuestas: [{reactivo_id, valor}]`. RN-01 con índice único Mongo. |
| Registro de auditoría en MongoDB | **Cumple** | `bitacora_auditoria` en segundo plano. Códigos validados contra catálogos `auditoria.*`. |
| Consulta de información almacenada | **Cumple** | Catálogos, agregados, bitácora, historial de consentimiento por `seudonimo_id`, `GET /api/auth/me`, `GET /api/salud`. |

Hallazgo crítico que estaba **roto** y se corrigió: `catalogo.servicio.js` llamaba `Catalogo.listarCampanias()` pero la función **no existía**. ADMIN y AUDITOR recibían 500 al listar campañas (catálogos, agregados y UI).

### 1.2 Integración de la arquitectura políglota

| Criterio | Estado | Notas |
| --- | --- | --- |
| Esquemas PostgreSQL `organizacion`, `usuarios`, `catalogo`, `consentimiento`, `agregado`, `auditoria` | **Cumple** | Definidos en `db/postgres/01_schema.sql`. El código consulta los seis. |
| Único vínculo identidad real ↔ operativa = `consentimiento.seudonimo` | **Cumple** | El JOIN `empleado_id` ↔ `seudonimo_id` ocurre solo en PostgreSQL. Mongo no recibe `empleado_id`. Las consultas de seudónimo ya no proyectan `empleado_id` hacia Node en el flujo de encuesta. |
| Mongo `respuestas_encuesta` con respuestas embebidas | **Cumple** | Incluye `version_consentimiento` (D-02) y `version_instrumento` (mapeo oficial del SQL). |
| Mongo `bitacora_auditoria` | **Cumple** | `actor_id`, `actor_perfil`, `accion`, `recurso`, `resultado`, `correlacion_id`, `timestamp`. |
| Sin JOINs simulados Mongo–Postgres | **Cumple** | Agregados leen Mongo por `unidad_organizacional_id` + `campania_id`. Postgres valida IDs y guarda el resultado en `agregado.agregado_calculado`. No se hidrata identidad desde Mongo. |
| Redis `session:{jti}` Hash TTL 15 min | **Cumple** | `HSET` + `EXPIRE` = `JWT_EXPIRES_SEC` (900). |
| Redis `revoked:{jti}` lista negra | **Cumple** | String `"1"` con TTL = vida restante del JWT. |
| Redis `cache:agregado:{unidad}:{campania}` TTL 5 min | **Cumple** | JSON, `EX` 300. Se invalida al crear una respuesta y al cambiar k. |
| Redis `contador:login_fallido:{usuario_id}` TTL 15 min | **Cumple** | 5 intentos → HTTP 423. El bloqueo ahora sí se audita. |
| Redis `lock:calculo_agregado:{unidad}` TTL 10 s | **Cumple** | `SET NX EX 10`. Reintento corto si otro cálculo está en curso. |

### 1.3 Infraestructura local y estándares

| Criterio | Estado | Notas |
| --- | --- | --- |
| Variables de entorno | **Cumple** | `.env.example` + `src/config/env.js` (carga `.env` local si existe). Compose inyecta las mismas claves. |
| Dockerfile + Docker Compose | **Cumple** | Imagen `node:22-bookworm-slim` (Debian). Postgres 15 y Redis 7 en Bookworm. Volúmenes nombrados. Healthchecks. Puerto host **5433** para no chocar con PostgreSQL local. |
| Convenciones y Git | **Cumple** | Capas en español (`controladores`, `servicios`, `modelos`, `rutas`). Nombres de tablas/campos alineados al SQL oficial. |

## 2. Evaluación estricta de la arquitectura políglota

### PostgreSQL

Uso correcto de esquemas:

- Autenticación: `usuarios.usuario` + `usuarios.usuario_perfil` + `usuarios.perfil`.
- Unidad operativa: `usuarios.empleado` ⋈ `consentimiento.seudonimo` (único pivote).
- Catálogos: `organizacion.*`, `catalogo.campania`, `catalogo.instrumento`, `catalogo.reactivo`.
- Consentimiento: `consentimiento.v_consentimiento_vigente` antes de insertar en Mongo.
- Agregados: lectura de `agregado.parametro_global` (k) y upsert en `agregado.agregado_calculado`.
- Auditoría de catálogo: validación de códigos contra `auditoria.tipo_*` (los logs no viven en PG).

Regla de seudonimización: respetada. `empleado_id` no viaja a Mongo ni a las respuestas JSON de autenticación (`payloadPublicoUsuario`).

Hueco de diseño del esquema oficial: `auditoria.tipo_recurso` no incluía `USUARIO`. Login/logout se etiquetaban como `SEUDONIMO`, lo cual es incorrecto (un ADMIN no opera con seudónimo). Se añadió `db/postgres/03_recurso_usuario.sql`.

### MongoDB

Inserción de encuesta:

```
seudonimo_id, instrumento_id, version_instrumento, campania_id,
unidad_organizacional_id, version_consentimiento, fecha_respuesta,
respuestas: [{ reactivo_id, valor }]
```

Antes faltaba `version_consentimiento` (D-02 del SQL). Corregido.

La agregación **no** hace lookup a Postgres por cada documento: filtra por IDs ya persistidos y proyecta `{ seudonimo_id: 0 }` para no filtrar identidad en el cálculo.

### Redis

Contrato de claves cumplido. Mejora: invalidación de `cache:agregado:*` para no servir un `GRUPO_INSUFICIENTE` obsoleto durante 5 minutos tras una nueva respuesta o un cambio de k.

## 3. Qué estaba a medias o faltaba (y qué se hizo)

| Hueco | Impacto en el parcial | Acción |
| --- | --- | --- |
| `listarCampanias` inexistente | ADMIN/AUDITOR no podían leer el segundo catálogo | Función añadida |
| Sin `version_consentimiento` en Mongo | Incumple mapeo D-02 | Campo añadido |
| Login auditado como recurso `SEUDONIMO` | Catálogo `auditoria` mal usado | Recurso `USUARIO` |
| Códigos de bitácora sin validar en PG | Esquema `auditoria` ornamental | Validación contra las tres tablas |
| Caché de agregado obsoleta | Demostración de Redis incompleta | Invalidación |
| Bloqueo de login sin bitácora | Auditoría de `LOGIN_FALLIDO` incompleta | Evento al HTTP 423 |
| Sin `CONSULTA_HISTORIAL_CONSENTIMIENTO` | Acción existe en PG y no se ejercía | `GET /api/auditoria/consentimientos/:seudonimoId` |
| Dockerfile Alpine / sin `.dockerignore` / puerto 5432 | Choque con Postgres del host; build pesado | Debian, ignore, 5433, volúmenes, healthcheck API |
| UI mínima (JSON crudo, sin salud, sin RN-01 visible) | Demostración pobre | Salud, sliders, aviso k, consentimiento, estado de encuesta |
| Token en `localStorage` | XSS persistente | `sessionStorage` + CSP de Helmet |

## 4. Áreas de mejora que quedan fuera del PMF

No son requisitos del primer parcial. No bloquean la demostración.

1. JWT en almacenamiento del navegador sigue siendo sensible a XSS. El siguiente paso sería cookie `HttpOnly` + `SameSite`.
2. Contraseñas demo (`demo123`) y `JWT_SECRET` por defecto. Aceptable en laboratorio; inaceptable en un despliegue real.
3. `cors({ origin: false })` asume monolito same-origin. Si se separa el front, hay que reabrir CORS de forma explícita.
4. La validación de bitácora cachea catálogos en memoria del proceso: un `INSERT` nuevo en `auditoria.tipo_accion` no se ve hasta reiniciar la API.
5. No hay TLS ni reverse proxy. En Debian de demostración basta Compose en localhost.
6. Tests unitarios no levantan Postgres/Mongo/Redis. La demo sigue siendo `docker compose` + los cuatro perfiles.
7. `ADMIN_SISTEMA` no tiene fila en `usuarios.empleado`; es coherente (no responde encuestas) pero hay que explicarlo en la defensa oral.

## 5. Cómo demostrar el parcial

```bash
docker compose down -v   # recrea volúmenes para aplicar 03_recurso_usuario.sql
docker compose up --build
```

Abrir http://127.0.0.1:3000

| Correo | Perfil | Qué mostrar |
| --- | --- | --- |
| ana.perez@empresa.com | COLAB | Login JWT, encuesta → Mongo, RN-01 al repetir |
| lucia.hernandez@empresa.com | LIDER_TURNO | Agregado `GRUPO_INSUFICIENTE` (n &lt; 5) |
| roberto.garcia@empresa.com | AUDITOR | Bitácora + historial de consentimiento sin `empleado_id` |
| carlos.ramirez@empresa.com | ADMIN_SISTEMA | Tres catálogos PG + cambio de k |

Health: `GET /api/salud` debe devolver `postgres`, `mongo` y `redis` en `true`.
