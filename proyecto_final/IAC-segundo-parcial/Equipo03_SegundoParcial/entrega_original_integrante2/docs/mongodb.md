# MongoDB — Integrante 2 (Fase 1)

Regla: el único pivote con identidad es `consentimiento.seudonimo` → `seudonimo_id`. Nunca `empleado_id` en Mongo.

## Colecciones e índices (`db/mongo/init.js`, idempotente)

| Colección | Índice | Campos |
|---|---|---|
| respuestas_encuesta | ux_seudonimo_campania (único) | seudonimo_id, campania_id |
| solicitudes_apoyo | ix_sol_seudonimo_fecha | seudonimo_id, fecha desc |
| solicitudes_apoyo | ix_sol_estado_fecha | estado, fecha desc |
| eventos_proceso (nueva, `$jsonSchema`) | ix_evt_seudonimo_ts | seudonimo_id, timestamp desc |
| eventos_proceso | ix_evt_correlacion | correlacion_id |
| eventos_proceso | ix_evt_tipo_ts | tipo, timestamp desc |

`eventos_proceso` requiere: seudonimo_id, correlacion_id, tipo, timestamp (date); `detalle` opcional (objeto).

## Funciones (src/modelos). `col` opcional = colección inyectada (tests)

- `Soporte.js`: `actualizarEstadoSolicitud({id, estado, actor_id, nota?}, col?)` (ABIERTA|EN_PROCESO|CERRADA, `$push` a `historial[]`), `solicitudesDeSeudonimo(seudonimoId, {limite}?, col?)`.
- `Encuesta.js`: `agregarRespuestasPorUnidadCampania({campaniaId?, desde?, hasta?}, col?)`.
- `Bitacora.js`: `conteoBitacoraPorAccion({desde?, hasta?}, col?)`, `bitacoraPorCorrelacion(correlacionId, col?)`.
- `EventosProceso.js`: `registrarEventoProceso({seudonimo_id, correlacion_id, tipo, detalle?, timestamp?}, col?)`, `eventosPorCorrelacion(id, col?)`, `eventosDeSeudonimo(seudonimoId, {limite}?, col?)`.
- `pipelinesMongo.js`: constructores puros de pipelines.

## Evidencia

```
mongosh "mongodb://localhost:27017" db/mongo/init.js
mongosh "mongodb://localhost:27017/bienestar_nexum" scripts/evidencia/mongo-01-crud-filtros.js
mongosh "mongodb://localhost:27017/bienestar_nexum" scripts/evidencia/mongo-02-agregaciones.js
```

Tests sin Mongo: `node --test tests/mongo-proceso.test.js`.
