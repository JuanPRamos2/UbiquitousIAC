-- =====================================================================
-- Migración 006 — Acciones de bitácora del motor de reglas
--
-- auditoria.bitacora tiene llave foránea contra auditoria.tipo_accion, de
-- modo que un servicio nuevo que escriba en la bitácora falla en silencio
-- hasta que su código se declara aquí. Eso es deliberado: impide que cada
-- componente invente sus propias etiquetas y que la bitácora se vuelva
-- ilegible.
--
-- POR QUÉ TRES Y NO UNA
-- ---------------------
-- Correr el motor, consultar una detección y simular un umbral son tres
-- hechos distintos, y a un comité de privacidad le importan por razones
-- distintas:
--
--   * DETECCION_EVALUADA es una escritura: crea detecciones que después
--     justifican planes de intervención sobre equipos reales.
--   * DETECCION_CONSULTADA es una lectura de información sensible sobre
--     una unidad, y por eso se marca sensible.
--   * UMBRAL_SIMULADO no escribe nada, pero sí revela los valores
--     publicados de todas las unidades a la vez. Alguien que simule
--     veinte umbrales distintos está explorando los datos, y el rastro
--     tiene que existir aunque la operación sea de solo lectura.
--
-- Reutilizar un solo código para los tres volvería ese rastro inútil.
-- =====================================================================

BEGIN;

INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('DETECCION_EVALUADA',
   'Corrida del motor de reglas sobre una campania: crea detecciones',
   FALSE),
  ('DETECCION_CONSULTADA',
   'Consulta de detecciones de riesgo de una unidad organizacional',
   TRUE),
  ('UMBRAL_SIMULADO',
   'Simulacion de un umbral de regla: no escribe, pero revela los valores '
   'publicados de las unidades',
   TRUE)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;
