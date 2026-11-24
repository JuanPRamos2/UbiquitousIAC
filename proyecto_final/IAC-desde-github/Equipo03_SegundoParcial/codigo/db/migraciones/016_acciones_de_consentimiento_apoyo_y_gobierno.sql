-- =====================================================================
-- Migración 016 — Códigos de bitácora de los servicios 8110-8119
--
-- auditoria.bitacora tiene llave foránea contra auditoria.tipo_accion.
-- Un código que no esté aquí hace fallar el INSERT, y como el registro
-- va envuelto en un try para no tumbar la operación, fallaría en silencio.
--
-- Es idempotente: el arranque de CI aplica las migraciones dos veces.
-- =====================================================================

INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
 ('SOLICITUD_APOYO_CREADA',
  'Alta de una solicitud de apoyo guardada contra el seudonimo, no contra la persona.',
  TRUE),
 ('SOLICITUD_APOYO_ACTUALIZADA',
  'Cambio de estado de una solicitud de apoyo. El historial no se reescribe.',
  TRUE),
 ('UNIDAD_MODIFICADA',
  'Alta o cambio de una unidad organizacional (jerarquia o plantilla).',
  FALSE),
 ('GOBERNANZA_CONSULTADA',
  'Consulta de la matriz de minimizacion, la retencion o las garantias.',
  TRUE),
 ('DATO_BAJA_REGISTRADA',
  'Quedo registrada una solicitud de baja. No borra el dato en el momento: '
  'la retencion declarada sigue vigente hasta que vence.',
  TRUE)
ON CONFLICT (codigo) DO NOTHING;
