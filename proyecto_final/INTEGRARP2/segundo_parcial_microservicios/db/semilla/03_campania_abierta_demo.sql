-- =====================================================================
-- Campaña abierta para la demostración
--
-- El volumen sintético de 02 deja las cuatro campañas anteriores
-- respondidas, que es lo que permite medir tendencias y presupuesto de
-- privacidad con datos realistas. Pero deja el sistema sin nada que
-- responder, y el proceso principal de negocio —responder la encuesta con
-- consentimiento— no se podría demostrar.
--
-- Esta quinta campaña queda abierta y sin respuestas a propósito: es la
-- que se usa en la demostración. Solo se carga en developer y staging.
-- =====================================================================

BEGIN;

INSERT INTO catalogo.campania
    (campania_id, nombre, instrumento_id, version_instrumento,
     fecha_inicio, fecha_fin, estado, secuencia)
SELECT 'CAMP-2026-S5', 'Medicion semana 5', c.instrumento_id,
       c.version_instrumento, CURRENT_DATE - 1, CURRENT_DATE + 6, 'ABIERTA', 5
  FROM catalogo.campania c
 WHERE c.campania_id = 'CAMP-2026-S4'
ON CONFLICT (campania_id) DO UPDATE
   SET estado = 'ABIERTA',
       fecha_inicio = EXCLUDED.fecha_inicio,
       fecha_fin = EXCLUDED.fecha_fin;

-- La campaña se dirige a las mismas unidades que la anterior.
INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id)
SELECT 'CAMP-2026-S5', cu.unidad_organizacional_id
  FROM catalogo.campania_unidad cu
 WHERE cu.campania_id = 'CAMP-2026-S4'
ON CONFLICT DO NOTHING;

-- La campaña anterior se cierra: dos campañas abiertas a la vez sobre el
-- mismo instrumento confundirían a quien responde.
UPDATE catalogo.campania SET estado = 'CERRADA'
 WHERE campania_id = 'CAMP-2026-S4' AND estado = 'ABIERTA';

COMMIT;
