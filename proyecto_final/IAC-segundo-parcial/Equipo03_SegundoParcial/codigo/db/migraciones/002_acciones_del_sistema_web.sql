-- =====================================================================
-- Migración 002 — Acciones de bitácora que introduce el sistema web
--
-- auditoria.bitacora tiene llave foránea contra auditoria.tipo_accion,
-- de modo que no se puede registrar una acción cuyo código no exista.
-- Eso es deliberado: impide que cada módulo invente sus propias
-- etiquetas y que la bitácora se vuelva ilegible.
--
-- El sistema web necesita registrar dos situaciones que aún no tenían
-- código. Se agregan aquí en lugar de reutilizar un código existente
-- con otro significado, porque una bitácora solo sirve si cada línea
-- dice exactamente lo que ocurrió.
-- =====================================================================

BEGIN;

INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('ACCESO_DENEGADO',
   'Intento de alcanzar una operacion sin el permiso necesario', TRUE),
  ('CATALOGO_MODIFICADO',
   'Alta o modificacion de un elemento de catalogo', FALSE)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;
