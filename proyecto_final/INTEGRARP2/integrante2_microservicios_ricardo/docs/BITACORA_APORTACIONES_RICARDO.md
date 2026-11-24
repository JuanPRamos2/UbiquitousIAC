# Bitácora de Aportaciones Técnicas — Integrante 2 (Segundo Parcial)

**Proyecto:** Plataforma de Bienestar Laboral y Prevención de Burnout (Bienestar Nexum — EQUIPO 03)  
**Materia:** Integración de Aplicaciones Computacionales (IAC) — Universidad de Monterrey (UDEM)  
**Responsable:** Ricardo Arath Sánchez Aguirre (#583928)  
**Rol asignado:** Integrante 2 — Lógica de negocio y persistencia de datos (Proceso Principal + Catálogos, PostgreSQL + MongoDB)  
**Rama de trabajo:** `feature/integrante2-proceso-principal-mongo` (aislada de `main`, sin merge preventivo)

---

## 1. Resumen Ejecutivo de la Responsabilidad

De acuerdo con el documento oficial de **División del Trabajo – Segundo Parcial**:

| Integrante | Responsabilidad Principal | Microservicios Asignados | Responsabilidad Adicional |
|---|---|---|---|
| **Integrante 2 (Ricardo Sánchez)** | **Lógica de negocio y datos** | **`main-process-service` y `catalog-service`** | **PostgreSQL + MongoDB** |

El Integrante 2 tiene la encomienda de entregar la columna vertebral del negocio: la persistencia estructurada y no estructurada, las operaciones transaccionales de catálogos y el proceso principal de captura de respuestas/solicitudes bajo el principio de no revinculación de identidad.

---

## 2. ¿Qué estamos haciendo?

Estamos construyendo e independizando los componentes de negocio y persistencia asignados al Integrante 2:

1. **Persistencia Estructurada (PostgreSQL):**
   - Creación de la migración no destructiva e idempotente [`db/postgres/04_catalogos_crud.sql`](../../db/postgres/04_catalogos_crud.sql).
   - Normalización de auditoría de modificaciones con `fecha_actualizacion` y triggers automáticos `BEFORE UPDATE` reutilizando `fn_actualizar_fecha_modificacion()`.
   - Incorporación de baja lógica segura (`activo` / `activa = FALSE`) en catálogos organizacionales y de auditoría para no romper integridad referencial con encuestas previas.
   - Definición de restricciones de unicidad (`lower(nombre)`) y reglas de integridad `CHECK` (escalas de reactivos, versiones > 0, coherencia cronológica de campañas y consentimientos).
   - Creación de índices optimizados para filtrado activo y consultas por unidad organizacional.

2. **Persistencia No Estructurada y Eventos (MongoDB):**
   - Ampliación de [`db/mongo/init.js`](../../db/mongo/init.js) con índices compuestos idempotentes para optimizar consultas por seudónimo y fecha.
   - Creación de la nueva colección documental `eventos_proceso` validada con esquema estricto `$jsonSchema` (requiere `seudonimo_id`, `correlacion_id`, `tipo`, `timestamp` y prohíbe `empleado_id`).
   - Implementación de operaciones documentales completas en [`src/modelos/`](../../src/modelos/):
     - **Actualización con historial:** `$set` de nuevo estado y `$push` en arreglo de trazabilidad `historial[]` en [`Soporte.js`](../../src/modelos/Soporte.js).
     - **Agregaciones analíticas:** Pipelines con `$match`, `$group` y `$sort` en [`Encuesta.js`](../../src/modelos/Encuesta.js) y [`Bitacora.js`](../../src/modelos/Bitacora.js) implementados mediante constructores puros en [`pipelinesMongo.js`](../../src/modelos/pipelinesMongo.js).
     - **Recuperación por identificadores relacionados:** Consultas por `seudonimo_id` y `correlacion_id` verificadas mediante planes de ejecución (`IXSCAN`).

3. **Garantía Innegociable de Privacidad:**
   - Preservación de la decisión arquitectónica D-01: **Cero JOINs entre PostgreSQL y MongoDB**.
   - El único pivote operativo entre la identidad y las evaluaciones es el token `consentimiento.seudonimo`. Jamás se almacena `empleado_id` en MongoDB ni en eventos de soporte.

4. **Microservicios Autónomos (Fase 2 en curso):**
   - `catalog-service`: Microservicio REST versionado (`/api/v1/catalogos/...`) con soporte de salida JSON y XML, validación de parámetros, caché Redis e invalidación al escribir, y endpoint `/health`.
   - `main-process-service`: Microservicio del proceso central de encuestas y solicitudes de apoyo (`/api/v1/encuestas/...`, `/api/v1/solicitudes/...`) con emisión de eventos correlacionados.

---

## 3. ¿Por qué lo estamos haciendo?

### Justificación Académica y Rúbrica
- **Reparto equitativo y demostración individual:** La rúbrica del 2.° Parcial exige que cada estudiante pueda defender y demostrar una pieza única del sistema. En la defensa final, el Integrante 2 debe ejecutar una operación real del proceso de negocio y demostrar en vivo cómo se persiste en PostgreSQL y en MongoDB.
- **Microservicios independientes:** Se supera la etapa monolítica dividiendo responsabilidades en contenedores dedicados con contratos explícitos.

### Justificación de Ingeniería y Arquitectura
- **¿Por qué PostgreSQL para Catálogos y Usuarios?:** Los catálogos de unidades organizacionales, instrumentos psicométricos, campañas y versiones de consentimiento requieren rigidez transaccional (ACID), claves foráneas inviolables y unicidad garantizada. Un error en un catálogo corrompería la validez metodológica del diagnóstico.
- **¿Por qué MongoDB para Respuestas y Eventos?:**
  - **Flexibilidad:** Cada instrumento de evaluación (burnout, estrés laboral, clima) maneja diferente número y tipo de reactivos. Modelarlo en tablas SQL causaría dispersión de columnas nulas o antipatrones EAV (Entity-Attribute-Value).
  - **Carga de escritura masiva:** Las encuestas y las bitácoras de auditoría son de escritura intensiva. Aislar esta carga en MongoDB evita bloquear las tablas relacionales de PostgreSQL.
- **¿Por qué Baja Lógica (`activo = false`)?:** Si un administrador elimina una unidad o un reactivo, un `DELETE` físico causaría errores de llave foránea o dejaría huérfanas miles de respuestas históricas en MongoDB. La baja lógica preserva la trazabilidad histórica.
- **¿Por qué estricto desacoplamiento con `seudonimo_id`?:** Para cumplir la NOM-035-STPS-2018 y la Ley Federal de Protección de Datos Personales (LFPDPPP). Si un atacante o auditor interno extrae un volcado de MongoDB, es matemáticamente imposible que identifique al colaborador porque no existe ningún vínculo de identidad en esa base de datos.

---

## 4. ¿Cómo lo estamos haciendo?

### Metodología de Trabajo
1. **Clan de Subagentes Especializados:**  
   Se definieron agentes con roles acotados para garantizar calidad y separación de funciones:
   - `postgres-data-steward`: Encargado del DDL, migraciones SQL idempotentes e índices en Postgres.
   - `mongo-data-architect`: Encargado de los esquemas documentales, índices y aggregation pipelines en Mongo.
   - `catalog-service-engineer`: Encargado del desarrollo del microservicio de catálogos.
   - `main-process-service-engineer`: Encargado del microservicio del proceso de encuestas.
   - `qa-docs-evidence-lead`: Encargado de pruebas unitarias, scripts de evidencia y documentación técnica.

2. **Control de Versiones y Aislamiento en Git:**  
   - Todo el trabajo se realiza en la rama local `feature/integrante2-proceso-principal-mongo`, creada a partir de `origin/main`.
   - **Regla estricta:** No se realiza `push` ni `merge` a `main` sin validación previa y aprobación explícita del usuario, permitiendo que los otros 3 integrantes trabajen simultáneamente en sus ramas sin colisiones de código.

3. **Ejecución y Verificación Real en Contenedores (Docker):**  
   - Se levantaron los servicios oficiales (`iac-postgres-1`, `iac-mongo-1`, `iac-redis-1`) mediante Docker Compose.
   - Se ejecutó `04_catalogos_crud.sql` contra PostgreSQL real, validando la ausencia de errores sintácticos.
   - Se ejecutaron los scripts [`scripts/evidencia/mongo-01-crud-filtros.js`](../../scripts/evidencia/mongo-01-crud-filtros.js) y [`scripts/evidencia/mongo-02-agregaciones.js`](../../scripts/evidencia/mongo-02-agregaciones.js) contra MongoDB 7 real usando `mongosh`, comprobando el uso de índices (`IXSCAN`).

4. **Pruebas Automatizadas:**  
   - Pruebas unitarias mediante `node:test` ([`tests/mongo-proceso.test.js`](../../tests/mongo-proceso.test.js)) utilizando colecciones inyectadas (mocks) para garantizar que la lógica de negocio funcione independientemente de la base de datos externa.

---

## 5. Trazabilidad de Artefactos Producidos por Ricardo

| Artefacto / Archivo | Tipo | Propósito y Contenido |
|---|---|---|
| [`db/postgres/04_catalogos_crud.sql`](../../db/postgres/04_catalogos_crud.sql) | SQL / Migración | Triggers de actualización, columnas `activo`/`fecha_actualizacion`, constraints e índices. |
| [`db/mongo/init.js`](../../db/mongo/init.js) | JS / Mongo Init | Índices de `solicitudes_apoyo`, colección `eventos_proceso` con `$jsonSchema` e índices compuestos. |
| [`src/modelos/Soporte.js`](../../src/modelos/Soporte.js) | JS / Modelo Mongo | Actualización de estado con `$push` de historial y consulta por seudónimo. |
| [`src/modelos/Encuesta.js`](../../src/modelos/Encuesta.js) | JS / Modelo Mongo | Agregación de respuestas por unidad y campaña usando aggregation pipeline. |
| [`src/modelos/Bitacora.js`](../../src/modelos/Bitacora.js) | JS / Modelo Mongo | Conteo analítico por acción y búsqueda por identificador de correlación. |
| [`src/modelos/EventosProceso.js`](../../src/modelos/EventosProceso.js) | JS / Modelo Mongo | Registro y trazabilidad de eventos del flujo operativo sin identidad. |
| [`src/modelos/pipelinesMongo.js`](../../src/modelos/pipelinesMongo.js) | JS / Utilidad | Constructores puros y reutilizables de pipelines de agregación. |
| [`tests/mongo-proceso.test.js`](../../tests/mongo-proceso.test.js) | JS / Test Unitario | Suite de 5 pruebas unitarias (`node:test`) para validar modelos sin base externa. |
| [`scripts/evidencia/mongo-01-crud-filtros.js`](../../scripts/evidencia/mongo-01-crud-filtros.js) | JS / Mongosh | Demostración reproducible de inserción, actualización, filtrado y explain de índices. |
| [`scripts/evidencia/mongo-02-agregaciones.js`](../../scripts/evidencia/mongo-02-agregaciones.js) | JS / Mongosh | Demostración reproducible de pipelines analíticos de agregación en Mongo. |
| [`docs/integrante2/postgresql.md`](postgresql.md) | Markdown / Doc Técnica | Especificación de diseño de base de datos relacional y guía para el CRUD. |
| [`docs/integrante2/mongodb.md`](mongodb.md) | Markdown / Doc Técnica | Especificación de esquemas documentales, índices y justificación de colecciones. |
| [`docs/integrante2/BITACORA_APORTACIONES_RICARDO.md`](BITACORA_APORTACIONES_RICARDO.md) | Markdown / Evidencia | Bitácora integral que responde qué, por qué y cómo se construyó la solución. |
| [`services/catalog-service/`](../../services/catalog-service/) | Microservicio | Microservicio independiente de catálogos con PostgreSQL, Dockerfile, Swagger y tests. |
| [`services/catalog-service/openapi.yaml`](../../services/catalog-service/openapi.yaml) | OpenAPI 3.0 | Contrato de API de catálogos con ejemplos en JSON y XML. |
| [`services/catalog-service/Dockerfile`](../../services/catalog-service/Dockerfile) | Dockerfile | Imagen de contenedor Node 20-alpine con healthcheck para catalog-service. |
| [`services/catalog-service/tests/catalog-service.test.js`](../../services/catalog-service/tests/catalog-service.test.js) | JS / Test Unitario | Suite de tests para serialización dual JSON/XML y mapeo de errores SQL. |
| [`services/main-process-service/`](../../services/main-process-service/) | Microservicio | Microservicio independiente del proceso principal con MongoDB, Dockerfile, Swagger y tests. |
| [`services/main-process-service/openapi.yaml`](../../services/main-process-service/openapi.yaml) | OpenAPI 3.0 | Contrato de API del proceso principal y soporte con ejemplos JSON y XML. |
| [`services/main-process-service/Dockerfile`](../../services/main-process-service/Dockerfile) | Dockerfile | Imagen de contenedor Node 20-alpine con healthcheck para main-process-service. |
| [`services/main-process-service/tests/main-process-service.test.js`](../../services/main-process-service/tests/main-process-service.test.js) | JS / Test Unitario | Suite de tests para serialización XML, regla D-01 y transiciones de estado. |

---

## 6. Estado de Avance: Fase 2 Culminada con Éxito

1. **Microservicio `catalog-service` Completado:**
   - Endpoints REST versionados `/api/v1/catalogos/...` implementando CRUD completo de unidades, instrumentos, reactivos y campañas.
   - Soporte dual JSON y XML (`Accept: application/xml` o `?format=xml`).
   - Baja lógica implementada (`activa=false` / `activo=false`) con triggers y fechas de actualización automáticas.
   - Caché Redis con invalidación en operaciones de escritura.
   - Endpoint `/health`, `Dockerfile` propio y especificación `openapi.yaml`.

2. **Microservicio `main-process-service` Completado:**
   - Endpoints REST versionados `/api/v1/encuestas/respuestas` y `/api/v1/solicitudes-apoyo`.
   - Estricto cumplimiento de regla D-01: validación en Postgres e inserción de respuestas y eventos en MongoDB sin persistir jamás `empleado_id`.
   - Transiciones de estado de solicitudes (`ABIERTA` -> `EN_PROCESO` -> `CERRADA`) con historial `$push`.
   - Endpoint `/health`, `Dockerfile` propio y especificación `openapi.yaml`.

3. **Pruebas y Verificación:**
   - 29 pruebas unitarias pasando al 100% (`npm test`).
   - Montaje retrocompatible en el monolito (`/api/v1/...`) para no romper vistas existentes.

---

## 7. Homogeneización con Avances del Equipo (Google Drive - Parcial 2)

Tras la revisión de la carpeta compartida de Google Drive (`Nuevo/Parcial 2/`), se identificaron los avances de los Integrantes 1 y 3 (`Contratos_JSON_XML_y_Swagger_Equipo03.docx` y `segundo_parcial_microservicios.zip`). Para asegurar máxima interoperabilidad y uniformidad:

1. **Adopción del Namespace Común:**
   - Se configuró el namespace canónico `xmlns="http://nexum.com.mx/bienestar/v1"` en las respuestas XML generadas por `catalog-service` y `main-process-service`.
2. **Estructura Estándar de Errores y Paginación:**
   - Los manejadores de error fueron alineados con [`contratos/xml/comun.xsd`](../../contratos/xml/comun.xsd) y [`contratos/json/Error.schema.json`](../../contratos/json/Error.schema.json), envolviendo errores bajo `error_respuesta` en XML y `{ error: { codigo, mensaje } }` en JSON.
3. **Esquemas XSD para el Integrante 2:**
   - Se crearon los esquemas formales [`contratos/xml/catalogos.xsd`](../../contratos/xml/catalogos.xsd) y [`contratos/xml/proceso.xsd`](../../contratos/xml/proceso.xsd) importando `comun.xsd`.
4. **Orquestación en Contenedores:**
   - Se creó [`docker-compose.microservicios.yml`](../../docker-compose.microservicios.yml) para que el Integrante 4 pueda levantar los microservicios del Integrante 2 (`catalog-service` en 3002 y `main-process-service` en 3003) sin conflictos de red ni puertos.

