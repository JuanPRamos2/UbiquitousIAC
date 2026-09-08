# Arquitectura políglota

PostgreSQL (negocio y catálogos) · MongoDB (encuestas y bitácora) · Redis (sesión, caché, locks).

La app Node orquesta las tres. No hay JOIN cruzado: se validan IDs en Postgres
y se persisten los mismos IDs en Mongo.

`consentimiento.seudonimo` es el único vínculo `empleado_id` ↔ `seudonimo_id`.
Las respuestas nunca guardan `empleado_id`. El documento Mongo incluye
`version_consentimiento` (decisión D-02).

La bitácora vive en MongoDB. Los códigos `accion`, `recurso` y `resultado`
se validan contra `auditoria.tipo_accion`, `auditoria.tipo_recurso` y
`auditoria.resultado_auditoria`.

Detalle de cumplimiento: [AUDITORIA.md](./AUDITORIA.md).
