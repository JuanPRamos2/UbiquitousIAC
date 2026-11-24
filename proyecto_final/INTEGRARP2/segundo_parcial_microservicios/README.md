# Bienestar Nexum — Plataforma de Bienestar Laboral y Prevención de Burnout

Monorepo del Proyecto 4, Equipo 03 · Integración de Aplicaciones Computacionales · UDEM

| | |
|---|---|
| Emiliano Pascual Piñales Sánchez | #657657 |
| Gerardo Quiroga Ramírez | #650313 |
| Ricardo Arath Sánchez Aguirre | #583928 |
| Juan Pablo Ramos Salazar | #610248 |

---

## Qué es esto

Una plataforma para medir el riesgo de burnout por **unidad organizacional**,
sin que la organización pueda ver la respuesta de ninguna persona.

Esa frase no es una promesa de diseño: es una restricción que el motor de
base de datos hace cumplir. El rol con el que se conecta la aplicación
**no tiene permiso de lectura sobre las respuestas individuales**. La única
ruta desde la aplicación hacia esos datos pasa por una función que aplica
el mecanismo de Laplace de privacidad diferencial y descuenta presupuesto
de épsilon. Ver `db/migraciones/001_rol_motor_y_funciones_definer.sql`.

---

## Arranque rápido (ambiente developer)

```bash
cp infra/ambientes/developer.env.ejemplo infra/ambientes/developer.env
./scripts/ambiente.sh developer arriba
./scripts/ambiente.sh developer probar
```

Eso levanta PostgreSQL 16, Redis 7 y la aplicación, carga el esquema
completo con datos sintéticos de 1,161 colaboradores en 16 unidades, y
corre una prueba de humo de cinco pasos.

Para apagar: `./scripts/ambiente.sh developer abajo`
Para borrar también los datos: `./scripts/ambiente.sh developer borrar`

Si no puedes descargar imágenes de contenedor, la misma cadena de arranque
de la base corre contra un PostgreSQL ya instalado:

```bash
createdb bienestar_dev
./scripts/arranque_base.sh bienestar_dev --con-semilla
```

---

## Estructura del repositorio

```
apps/
  api/                    servicio de aplicación (Flask + Gunicorn)
    app/__init__.py       rutas: /salud, /listo, /agregado
    app/config.py         configuración exclusivamente por variables de entorno
    Dockerfile            una sola imagen para los tres ambientes
    gunicorn.conf.py      4 trabajadores: el número sobre el que se midió
  web/                    interfaz (módulos M01–M12, siguiente etapa)

db/
  esquema/
    00_rol_aplicacion.sh  crea el rol de la aplicación
    01_esquema.sql        esquema completo + catálogos + privacidad diferencial
    09_permisos.sh        permisos de menor privilegio
  semilla/
    02_volumen_sintetico.sql   1,161 colaboradores, 4 campañas, 19,020 reactivos
  migraciones/
    001_rol_motor_y_funciones_definer.sql

infra/
  compose/
    docker-compose.base.yml          lo común a los tres ambientes
    docker-compose.developer.yml     override de developer
    docker-compose.staging.yml       override de staging
    docker-compose.production.yml    override de production
  ambientes/*.env.ejemplo            plantillas de variables (sin contraseñas)
  nginx/                             proxy de staging y production
  secretos/                          vacío en el repositorio, por diseño

scripts/
  ambiente.sh             operar cualquier ambiente
  probar.sh               prueba de humo
  arranque_base.sh        cadena de arranque de la base sin Docker

docs/                     documentación del proyecto
```

---

## Los tres ambientes

Los tres usan **la misma imagen de contenedor**. Lo único que cambia son
las variables de entorno. Es lo que permite afirmar que lo probado en
staging es lo que corre en production.

| | developer | staging | production |
|---|---|---|---|
| Dónde corre | máquina de cada integrante | 1 VM e2-small | VM e2-small + VM e2-medium |
| Datos | sintéticos generados por script | copia anonimizada | reales de la organización |
| Puerto de PostgreSQL publicado | sí, 5432 | no | **no** |
| Procesos de Gunicorn | 1, con recarga automática | 1 | 4 |
| Detalle de errores al cliente | sí | no | no |
| Versión de la imagen | `local` | etiqueta | **obligatoria; el despliegue falla sin ella** |
| Respaldo | no | no | diario, retención 7 días |

Tres guardas están puestas a propósito para que un error de operación
falle en lugar de pasar desapercibido:

1. `scripts/ambiente.sh` rechaza levantar **production** sin `VERSION`.
   Desplegar `latest` o `local` en production está prohibido.
2. `docker-compose.production.yml` **no publica** el puerto de PostgreSQL.
   La ausencia de la sección `ports` es deliberada, y está comentada como tal.
3. La red `privada` está marcada `internal: true`: los contenedores de
   datos no tienen ruta de salida a Internet.

---

## Lo que el rol de la aplicación NO puede hacer

Comprobado, no supuesto:

| Intento | Resultado |
|---|---|
| `SELECT ... FROM autoreporte.respuesta_detalle` | `ERROR: permission denied for schema autoreporte` |
| `DELETE FROM auditoria.bitacora` | `ERROR: permission denied for table bitacora` |
| `UPDATE agregado.presupuesto_privacidad` | `ERROR: permission denied for table presupuesto_privacidad` |
| `SELECT * FROM agregado.fn_calcular_agregado_protegido(...)` | `PUBLICADO \| 179 \| 3.860 \| ε=1.0` |

La cuarta línea es la que hace útiles a las tres primeras: la aplicación
puede obtener el dato agregado, y **solamente** por la vía que aplica ruido
de Laplace y descuenta presupuesto.

---

## Documentación

Los documentos del primer parcial están en `docs/`. El de arquitectura de
hardware sostiene el dimensionamiento de los contenedores de este
repositorio con mediciones reales, no con estimaciones.
