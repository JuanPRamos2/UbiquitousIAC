# Consultas, reportes, Redis y Docker

Toda la documentación de esta parte está en esta carpeta: `proyecto_final/Redis, Docker, consultas y pruebas/`.

| Archivo | Para qué es |
| --- | --- |
| [cómo funciona](Arquitectura/como-funciona.md) | Qué hace cada cambio y dónde se ve |
| [integración con el equipo](Arquitectura/integracion-con-el-equipo.md) | Contrato para enganchar las partes 1, 2 y 3 |
| [servicio de consultas](Consultas/servicio-de-consultas.md) | Servicio de consultas |
| [servicio de reportes](Reportes/servicio-de-reportes.md) | Servicio de reportes |
| [Redis](Redis/redis.md) | Caché, TTL, contadores, rate limit y claves |
| [Docker](Docker/docker-y-despliegue.md) | Contenedores, red, puertos y comandos |
| [evidencias de pruebas](Pruebas/evidencias-de-pruebas.md) | Cómo probar cada endpoint y qué capturar |
| [matriz de trazabilidad](Arquitectura/matriz-de-trazabilidad.md) | Matriz de trazabilidad |
| [arquitectura](Arquitectura/arquitectura.md) | Diagrama y puertos |
| [conclusiones](Arquitectura/conclusiones.md) | Texto de cierre del parcial |
| [guion](Presentacion/guion-demostracion-y-video.md) | Guion presencial y guion de YouTube |
| [material para la presentación](Presentacion/material-completo-para-presentacion.md) | Texto completo para pasarle a otra IA y armar las láminas |
| [auditoría de requisitos](Arquitectura/auditoria-de-requisitos.md) | Tabla final de requisitos |
| [código de consultas](Consultas/codigo/) | Servicio, Dockerfile y pruebas de consultas |
| [código de reportes](Reportes/codigo/) | Servicio, Dockerfile y pruebas de reportes |
| [código compartido](Codigo-compartido/comun/) | JWT, Redis, JSON, XML, XSD y errores |
| [Docker](Docker/docker-compose.yml) | Compose, variables y Dockerfile de la web |
| [prueba de integración](Pruebas/integracion/flujos.test.js) | Prueba contra los contenedores |
| [cambios en la web](Aplicacion/) | Página de la gráfica y archivos del sistema que se tocaron |

Esta guía permite clonar el proyecto y ejecutar la parte del segundo parcial sin configuración oculta. El sistema sigue siendo Bienestar Nexum. No se creó una aplicación aparte.

## Requisitos

- Docker Engine y el plugin Compose v2
- Node.js 22 o superior, solo si se quieren correr las pruebas en el host
- Los puertos 3010, 3020, 5433, 6379 y 27017 libres
- El puerto de la web es `API_HOST_PORT`. En el `.env` actual vale 3001

## Configuración

```bash
cd proyecto_final
cp -n .env.example .env
```

No hace falta poner contraseñas reales. El valor de demostración de `JWT_SECRET` debe ser el mismo para `api`, `queries-service` y `reports-service`. Compose ya lo comparte. Dentro de la red Docker los servicios no usan `localhost`: usan `postgres`, `mongo` y `redis`.

El archivo `.env` del host puede decir `POSTGRES_PORT=5432`. Eso no cambia el contenedor. Compose publica PostgreSQL en **5433** para no chocar con un PostgreSQL local.

## Docker

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

## Ejecución

| Qué | URL |
| --- | --- |
| Web | http://127.0.0.1:3001 |
| Gráfica de reportes | http://127.0.0.1:3001/consultas-reportes.html |
| Swagger de consultas | http://127.0.0.1:3010/api/docs |
| Swagger de reportes | http://127.0.0.1:3020/api/docs |
| Salud de consultas | http://127.0.0.1:3010/health |
| Salud de reportes | http://127.0.0.1:3020/health |

Si la web está en 3000, abre ese puerto. El login de demostración es `mariana.solis@nexum.com.mx` / `demo123`.

No hay migraciones nuevas. El esquema lo carga `bienestar_nexum_v2.sql` la primera vez que se crea el volumen de PostgreSQL.

## Pruebas

```bash
npm test
npm run test:micro
INTEGRACION=1 npm run test:integracion
```

La integración usa los contenedores ya levantados. Resultado obtenido: 13 pruebas del monolito, 16 pruebas unitarias de esta parte y 3 pruebas de integración, todas en verde.

## Redis

```bash
docker compose exec redis redis-cli
```

Comandos de demostración en [Redis](Redis/redis.md).

## Swagger

Try it out funciona. Primero hay que obtener un JWT en la web o con:

```bash
curl -s -X POST http://127.0.0.1:3001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"correo":"mariana.solis@nexum.com.mx","contrasena":"demo123"}'
```

En Swagger se pulsa Authorize y se pega solo el token, sin la palabra Bearer si la interfaz ya la agrega. Para XML, en el header Accept se pone `application/xml`.

## Problemas frecuentes

- **401 en consultas.** El token no tiene sesión en Redis. Hay que entrar por `/api/auth/login` del monolito, no inventar un JWT suelto, salvo que también se escriba `session:{jti}`.
- **403.** El perfil no tiene ese permiso. Un colaborador no consulta auditoría ni el resumen organizacional. Un líder no consulta otra unidad.
- **429.** Se superó `RATE_LIMIT_REQUESTS` dentro de `RATE_LIMIT_WINDOW_SEC`. Esperar el `Retry-After` o subir el límite y reconstruir.
- **La gráfica no carga.** La página y los servicios tienen que estar arriba. La web debe poder llamar a los puertos 3010 y 3020; el Compose ya deja esos orígenes en la política de la aplicación.
- **PostgreSQL vacío o con el esquema viejo.** `docker compose down -v` borra el volumen y vuelve a cargar el SQL. Eso elimina datos locales.
