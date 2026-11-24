-- =====================================================================
-- Migración 007 — Resultados de bitácora que faltaban
--
-- EL FALLO QUE CORRIGE
-- --------------------
-- auditoria.bitacora tiene llave foránea contra auditoria.resultado, igual
-- que contra auditoria.tipo_accion. El catálogo traía cinco códigos:
-- EXITO, RECHAZADO, ERROR_TECNICO, GRUPO_INSUFICIENTE y
-- PRESUPUESTO_AGOTADO.
--
-- El código de las aplicaciones escribía además RECHAZADO_PERMISO, que no
-- existía. La inserción fallaba por llave foránea, y como el registro en
-- bitácora va envuelto en un try para que un problema de auditoría no
-- tumbe la operación principal, fallaba EN SILENCIO.
--
-- Lo que se perdía es justamente lo que un auditor busca primero: todos
-- los accesos denegados por falta de permiso. El sistema negaba el acceso
-- correctamente —el 403 llegaba al usuario— y no quedaba rastro de que
-- hubiera ocurrido. Una bitácora a la que le faltan precisamente los
-- intentos rechazados da una impresión peor que no tener bitácora, porque
-- parece completa.
--
-- Se descubrió mirando los registros del portal mientras se verificaban
-- las pantallas una por una: el mensaje de error estaba ahí desde hacía
-- tiempo, en el nivel ERROR, y nadie lo había leído.
--
-- POR QUÉ DOS CÓDIGOS Y NO UNO GENÉRICO
-- -------------------------------------
--   * RECHAZADO_PERMISO distingue «te lo negué porque tu perfil no lo
--     tiene» de RECHAZADO, que cubre una regla de negocio incumplida. Son
--     dos hechos distintos: el primero puede significar que alguien está
--     probando dónde están los límites; el segundo, que el sistema hizo su
--     trabajo con una petición legítima pero inválida.
--
--   * PARCIAL cubre un caso real del motor de reglas: la evaluación se
--     hizo y su resultado se entregó, pero no se pudo archivar porque
--     MongoDB no respondía. Marcarlo EXITO mentiría —la corrida no está en
--     el historial— y marcarlo ERROR_TECNICO también, porque el usuario SÍ
--     obtuvo su resultado.
--
-- DENEGADO, que reports-service usaba, NO se agrega: significa lo mismo
-- que RECHAZADO_PERMISO y dos etiquetas para el mismo hecho vuelven la
-- bitácora imposible de consultar. Se unificó el código en su lugar.
-- =====================================================================

BEGIN;

INSERT INTO auditoria.resultado (codigo, descripcion) VALUES
  ('RECHAZADO_PERMISO',
   'La operación se negó porque el perfil del actor no tiene el permiso '
   'requerido. Se distingue de RECHAZADO, que cubre una regla de negocio '
   'incumplida: aquí el actor no tenía derecho a intentarlo.'),
  ('PARCIAL',
   'La operación se completó y su resultado se entregó, pero una parte '
   'accesoria no se pudo persistir (por ejemplo, archivar la corrida en '
   'MongoDB cuando el almacén no responde). No es éxito, porque algo '
   'falta; no es error, porque quien la pidió sí obtuvo su resultado.')
ON CONFLICT (codigo) DO NOTHING;

COMMIT;

-- Verificación: los cinco originales más los dos nuevos.
--   SELECT codigo FROM auditoria.resultado ORDER BY codigo;
