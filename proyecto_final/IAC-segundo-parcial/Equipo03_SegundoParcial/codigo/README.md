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

## Arranque rápido

Un comando, sin variables que recordar:

```bash
docker compose up -d --build
docker compose ps
```

El `docker-compose.yml` de la raíz trae los valores de developer a la
vista. Levanta PostgreSQL 16, Redis 7, MongoDB 7, el sistema web y los
veinticuatro microservicios; carga el esquema, las diecisiete migraciones y los datos
sintéticos; y declara los índices y validadores de la base documental.

| Qué | Dónde |
|---|---|
| Portal | <http://localhost:8000> |
| Swagger de cada servicio | <http://localhost:8101/docs> … `:8124` |
| PostgreSQL | `localhost:5432` (solo en developer) |

Usuarios de demostración, todos con contraseña `demo123`:
`ana.perez@` (colaborador), `lucia.hernandez@` (líder, alcance
UO-CC-TURNO-B), `mariana.solis@` (especialista), `roberto.garcia@`
(auditor), `carlos.ramirez@` (administrador), todos en `nexum.com.mx`.

Ese archivo es el camino corto para revisar el proyecto o levantarlo en la
máquina de un integrante. **No sirve para staging ni production**: tiene
contraseñas triviales a la vista y publica los puertos de las bases. Para
cualquier otra cosa se usan los cuatro archivos de `infra/compose/`:

```bash
cp infra/ambientes/developer.env.ejemplo infra/ambientes/developer.env
./scripts/ambiente.sh developer arriba
./scripts/ambiente.sh developer probar
```

Lo que el atajo **no** relaja: los veinticuatro componentes se conectan a
PostgreSQL con el rol `bienestar_app` y nunca con el superusuario. Un
compose que conectara los servicios como `postgres` dejaría la garantía
central del proyecto en el papel y no en el motor.

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
  web/                    sistema web (Flask + Jinja2 + Gunicorn), módulos M01–M12
    app/rutas/            publico, sesion, portal, panel, catalogos, campanias,
                          intervenciones, evidencias, gobierno, notificaciones,
                          administracion, perfiles
    plantillas/           vistas; estaticos/ con Highcharts servido localmente
  microservicios/         módulo del segundo parcial: veinticuatro servicios
    comun/                biblioteca compartida de los catorce en Python
    comun-node/           la misma, para los dos servicios en Node
    auth-service/         Integrante 1 — tokens
    users-service/        Integrante 1 — usuarios, perfiles y alcance
    catalog-service/      Integrante 2 — catálogos (Node)
    main-process-service/ Integrante 2 — proceso de encuesta y apoyo (Node)
    documents-service/    Gerardo — evidencias, avisos y archivos
    notifications-service/ Gerardo — notificaciones internas
    queries-service/      Emiliano — lectura con caché, sin gastar épsilon
    reports-service/      Emiliano — generación, sellado y descarga
    algorithms-service/   Emiliano — motor de reglas sobre lo ya publicado
    trends-service/       Emiliano — cambio real contra ruido
    interventions-service/ Emiliano — planes organizacionales y su evaluación
    export-service/       Emiliano — egreso controlado de agregados
    sync-service/         Gerardo — sincronización con red intermitente
    configuration-service/ Gerardo — parámetros, umbrales y presupuestos
    monitoring-service/   Gerardo — salud, latencia, alertas y reinicios
    integration-service/  Gerardo — puerta hacia el sistema corporativo
  escritorio/             aplicación de escritorio (Tkinter), consume solo XML
    cliente.py            la capa de red, sin Tkinter: por eso se puede probar
    app.py                la ventana
  movil/                  aplicación Android (Kotlin + Compose), consume solo JSON

contratos/
  xml/                    12 esquemas XSD; comun.xsd lo incluyen los demás
  json/                   58 esquemas JSON Schema 2020-12 (generados)
  generar_json.py         los deriva de los contratos OpenAPI
  generar_openapi_node.py genera el openapi.yaml de los dos servicios de Node

db/
  esquema/
    00_rol_aplicacion.sh  crea el rol de la aplicación
    01_esquema.sql        esquema completo + catálogos + privacidad diferencial
    09_permisos.sh        permisos de menor privilegio
  semilla/
    02_volumen_sintetico.sql   1,161 colaboradores, 4 campañas, 19,020 reactivos
    03_campania_abierta_demo.sql, 04_agregados_y_riesgo_demo.sql,
    05_intervencion_demo.sql
  migraciones/
    001_rol_motor_y_funciones_definer.sql   rol motor y funciones SECURITY DEFINER
    002_acciones_del_sistema_web.sql
    003_registrar_autoreporte.sql           la única vía de escritura de respuestas
    004_catalogos_crud_y_permisos.sql       baja lógica y tres permisos nuevos
    005_acciones_de_reportes_y_evidencias.sql
    006_acciones_del_motor_de_reglas.sql    acciones del motor de reglas
  mongo/
    init.js               índices y validadores $jsonSchema de las 7 colecciones

infra/
  compose/
    docker-compose.base.yml          lo común a los tres ambientes
    docker-compose.developer.yml     override de developer
    docker-compose.staging.yml       override de staging
    docker-compose.production.yml    override de production
    docker-compose.microservicios.yml  los veinticuatro servicios + MongoDB
  ambientes/*.env.ejemplo            plantillas de variables (sin contraseñas)
  nginx/                             proxy de staging y production
  secretos/                          vacío en el repositorio, por diseño

pruebas/                  499 pruebas: servicios, contratos, clientes y pantallas

scripts/
  ambiente.sh             operar cualquier ambiente
  probar.sh               prueba de humo
  arranque_base.sh        cadena de arranque de la base sin Docker
  arrancar_microservicios.sh  levanta los veinticuatro servicios sin Docker
  evidencia/              guiones de mongosh para evidenciar índices y agregaciones

docs/                     documentación del proyecto
```

---

## Los veinticuatro microservicios

Dieciocho en Python y seis en Node. Un cliente no puede notar la diferencia:
los veinticuatro firman el JWT con el mismo secreto, leen la misma sesión en
Redis, autorizan contra `usuarios.perfil_permiso` en cada petición,
devuelven el mismo sobre de error y serializan XML con las mismas reglas.

| Servicio | Responsable | Lenguaje | Puerto |
|---|---|---|---|
| `auth-service` | Juan Pablo (1) | Python | 8101 |
| `users-service` | Juan Pablo (1) | Python | 8102 |
| `catalog-service` | Ricardo (2) | Node | 8103 |
| `main-process-service` | Ricardo (2) | Node | 8104 |
| `documents-service` | Gerardo (4) | Python | 8105 |
| `notifications-service` | Gerardo (4) | Python | 8106 |
| `queries-service` | Emiliano (3) | Python | 8107 |
| `reports-service` | Emiliano (3) | Python | 8108 |
| `algorithms-service` | Emiliano (3) | Python | 8109 |
| `consent-service` | Juan Pablo (1) | Python | 8110 |
| `privacy-service` | Juan Pablo (1) | Python | 8111 |
| `survey-service` | Ricardo (2) | Node | 8112 |
| `indicators-service` | Ricardo (2) | Node | 8113 |
| `trends-service` | Emiliano (3) | Python | 8114 |
| `interventions-service` | Emiliano (3) | Python | 8115 |
| `support-service` | Ricardo (2) | Node | 8116 |
| `organizational-service` | Ricardo (2) | Node | 8117 |
| `audit-service` | Juan Pablo (1) | Python | 8118 |
| `data-governance-service` | Juan Pablo (1) | Python | 8119 |
| `sync-service` | Gerardo (4) | Python | 8120 |
| `export-service` | Emiliano (3) | Python | 8121 |
| `configuration-service` | Gerardo (4) | Python | 8122 |
| `monitoring-service` | Gerardo (4) | Python | 8123 |
| `integration-service` | Gerardo (4) | Python | 8124 |

Detalle, decisiones y cómo levantarlos: `apps/microservicios/README.md`.

### Dos decisiones opuestas, y por qué

`sync-service` e `integration-service` resuelven el mismo problema
—recibir datos de fuera— y toman la decisión **contraria** sobre lo mismo.
Conviene tenerlo claro porque es lo primero que parece una incoherencia:

| | `sync-service` | `integration-service` |
|---|---|---|
| ¿Un lote parcial se aplica? | **Sí**, renglón por renglón | **No**, todo o nada |

El motivo es la naturaleza de lo que llega. Un lote de cuarenta
autoreportes con uno mal formado, aplicado a medias, son treinta y nueve
respuestas guardadas: un resultado útil, y el cliente que las capturó sin
red no tiene cómo recuperarlas si se rechazan en bloque. Un árbol
organizacional aplicado a medias son unidades huérfanas, y el alcance de
todos los perfiles se calcula recorriendo ese árbol: un árbol roto
significa gente viendo datos de áreas que no le tocan, o no viendo los
suyos.

```bash
python3 -m pytest pruebas/ -q      # 499 pruebas recogidas; ver abajo
```

De las 499, **452 pasan sin nada más levantado**, y se comprobó corriendo
la suite dos veces seguidas con el mismo resultado. Las 47 restantes viven
en tres archivos que necesitan algo que no es parte del repositorio. Se
nombran aquí en lugar de esconderlas, y la mayoría **se salta sola** en
lugar de fallar:

| Archivo | Pruebas | Necesita | Sin eso |
|---|---|---|---|
| `test_servicios_node.py` | 27 | `npm install` en los dos servicios de Node | 1 corre igual (compara las constantes de Node contra la base) y 26 se saltan |
| `test_movil.py` | 17 | El proyecto Android compilado | Se saltan |
| `test_degradacion_web.py` | 3 | Los microservicios levantados y apagables | Se saltan |

Una más se salta sola donde el intérprete no trae Tkinter, que es el caso
de varios contenedores de Python.

Para correr solo las que no necesitan nada:

```bash
python3 -m pytest pruebas/ -q \
  --ignore=pruebas/test_servicios_node.py \
  --ignore=pruebas/test_degradacion_web.py \
  --ignore=pruebas/test_movil.py
```

---

## Las dos aplicaciones cliente

Dos aplicaciones que atienden **procesos distintos**, hablan **formatos
distintos** y comparten el mismo backend. Que las dos funcionen contra los
mismos servicios es lo que demuestra que la negociación de formato existe
de verdad y no es una bandera que nadie ejercita.

| | Escritorio | Móvil |
|---|---|---|
| Proceso | atender solicitudes y leer el tablero | responder la encuesta y pedir apoyo |
| Quién | especialista de bienestar | colaborador |
| Formato | **XML exclusivamente** | **JSON exclusivamente** |
| Tecnología | Python + Tkinter | Kotlin + Jetpack Compose |
| Servicios que consume | 6 | 5 |

```bash
# escritorio — necesita Tkinter (en Debian/Ubuntu: apt-get install python3-tk)
./scripts/arrancar_microservicios.sh     # los veinticuatro servicios, sin Docker
./scripts/arrancar_web.sh                # el portal, en :8000
python3 apps/escritorio/app.py
```

La móvil se abre en Android Studio desde `apps/movil/`. Instrucciones y
limitaciones: `apps/movil/LEEME.md`.

La aplicación de escritorio **valida toda respuesta contra su XSD antes de
leerla**. Hacerlo destapó seis defectos de contrato que llevaban ahí desde
el principio porque ningún cliente validaba: un listado que ignoraba
`?formato=xml` y devolvía JSON siempre, un pluralizador que producía
`<intervenciones_sugerida>`, un campo declarado booleano que en realidad
tiene tres situaciones, un elemento que ningún esquema declaraba, dos
órdenes distintos para la misma entidad según el endpoint, y un número mal
escrito que llegaba a PostgreSQL como `NaN`. Ninguno se habría encontrado
leyendo el código.

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

En `docs/`:

| Documento | Qué cubre |
|---|---|
| `Reporte_Tecnico_Integrado_Equipo03.docx` | **El documento general**: problema, actores, base de datos con privacidad diferencial, sistema web, los microservicios, el motor de reglas, las dos aplicaciones cliente, contratos, ambientes y pruebas |
| `Manual_Tecnico_y_Demostracion_Equipo03.docx` | Manual técnico de operación y el guión de la demostración integrada, en catorce pasos |
| `Modulo_Microservicios_Completo_Equipo03.docx` | El módulo del segundo parcial en detalle, incluida la integración de las piezas de cada integrante |
| `Seguridad_JWT_y_Servicios_Equipo03.docx` | Seguridad y servicios del Integrante 1 |
| `Contratos_JSON_XML_y_Swagger_Equipo03.docx` | Contratos del Integrante 3 |
| `Monorepo_y_Ambientes_Equipo03.docx` | Monorepo y los tres ambientes |
| `Arquitectura_de_Hardware_Equipo03.docx` | Dimensionamiento con mediciones reales, no estimaciones |
