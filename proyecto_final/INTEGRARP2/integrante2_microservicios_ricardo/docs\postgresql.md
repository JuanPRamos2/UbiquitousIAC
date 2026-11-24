# Integrante 2 – PostgreSQL (Fase 1)

Migración: [04_catalogos_crud.sql](../../db/postgres/04_catalogos_crud.sql). No destructiva e idempotente (`IF NOT EXISTS` / chequeo en `pg_constraint`); 01–03 intactos. Pivote con Mongo: `consentimiento.seudonimo` (sin JOIN entre motores).

## Baja lógica y auditoría de cambio
| Tabla | Columnas nuevas |
|---|---|
| catalogo.instrumento | fecha_actualizacion (`activo` ya existía) |
| catalogo.version_instrumento | fecha_creacion, fecha_actualizacion (`activo` ya existía) |
| catalogo.reactivo | fecha_creacion, fecha_actualizacion (`activo` ya existía) |
| catalogo.campania | fecha_actualizacion (flag existente: **`activa`**) |
| consentimiento.version_consentimiento | fecha_actualizacion |
| auditoria.tipo_accion | activo, fecha_actualizacion |
| auditoria.tipo_recurso, resultado_auditoria | activo |
| organizacion.unidad_organizacional | (ya tenía `activa` y `fecha_actualizacion`) |

Se usa el nombre `fecha_actualizacion` (no `updated_at`) para reutilizar `fn_actualizar_fecha_modificacion()`; se crean triggers `BEFORE UPDATE` en las tablas que lo ganan.
Nota: los flags son `activa` (unidad, campaña) y `activo` (resto).

## Unicidad
- `ux_instrumento_nombre` (lower(nombre)), `ux_campania_nombre` (lower(nombre))
- `ux_unidad_padre_nombre` (padre, lower(nombre))
- `ux_riv_orden` (instrumento_id, version, orden)

## CHECKs
`ck_version_instrumento_positiva`, `ck_reactivo_escala_orden` (min<max), `ck_riv_orden_positivo`, `ck_campania_unidad_fechas`, `ck_version_consent_fechas`.

## Índices
activo en instrumento/reactivo/tipo_accion, (instrumento_id, activo) en version_instrumento, `reactivo_instrumento_version(reactivo_id)`, campania(activa, fechas), campania(instrumento_id, version_instrumento), campania_unidad(unidad_organizacional_id).

## Guía para el CRUD (catalog-service-engineer)
- Baja = `UPDATE ... SET activo=FALSE` (no DELETE: FKs de campañas/Mongo referencian IDs).
- Duplicados → error `23505` → mapear a 409. FK → `23503` → 409/422. CHECK → `23514` → 422.
- SQL siempre parametrizado (`$1…`).
- Aplicar: `psql -f db/postgres/04_catalogos_crud.sql` (re-ejecutable). Si el volumen ya existe, el init de docker no la corre sola.

## Validación
Validado exitosamente contra contenedor `iac-postgres-1` (PostgreSQL 15-bookworm) con `04_catalogos_crud.sql` ejecutado sin errores (COMMIT). Todos los triggers, constraints e índices quedaron aplicados y son idempotentes.
