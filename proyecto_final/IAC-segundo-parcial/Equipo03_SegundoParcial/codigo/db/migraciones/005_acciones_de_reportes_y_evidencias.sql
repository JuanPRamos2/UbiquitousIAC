-- =====================================================================
-- Migración 005 — Acciones de bitácora de reportes y de evidencias
--
-- auditoria.bitacora tiene llave foránea contra auditoria.tipo_accion,
-- así que no se puede registrar una acción cuyo código no exista. Eso es
-- deliberado: impide que cada microservicio invente sus propias etiquetas
-- y que la bitácora se vuelva ilegible. El efecto práctico es que un
-- servicio nuevo que escriba en la bitácora falla en silencio hasta que su
-- código se declara aquí.
--
-- POR QUÉ ESTAS SEIS
-- ------------------
-- reports-service y la carga de evidencias introducen operaciones que
-- antes no existían, y las tres de reportes tienen que ser distinguibles
-- entre sí: generar un reporte de bitácora, descargarlo y verificar su
-- sello son tres hechos diferentes, y un auditor que investiga una fuga
-- necesita saber cuál de los tres ocurrió. Reutilizar
-- 'BITACORA_CONSULTADA' para las tres volvería ese rastro inútil.
--
-- REPORTE_DESCARGADO es sensible, REPORTE_GENERADO no: generar un reporte
-- lo deja guardado del lado del servidor, mientras que descargarlo es el
-- momento en que la información sale del sistema. Esa es la línea que a un
-- comité de privacidad le importa.
-- =====================================================================

BEGIN;

INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('REPORTE_GENERADO',
   'Generacion y sellado de un reporte a partir de resultados publicados',
   FALSE),
  ('REPORTE_DESCARGADO',
   'Descarga del contenido de un reporte en JSON, CSV o XML: es el momento '
   'en que la informacion sale del sistema',
   TRUE),
  ('REPORTE_VERIFICADO',
   'Confrontacion del sello SHA-256 de un reporte contra el registrado',
   FALSE),
  ('EVIDENCIA_CARGADA',
   'Carga de un archivo de evidencia asociado a una intervencion o campania',
   FALSE),
  ('EVIDENCIA_DESCARGADA',
   'Descarga de un archivo de evidencia previamente cargado',
   TRUE),
  ('NOTIFICACION_LEIDA',
   'El destinatario marco como leida una notificacion interna',
   FALSE)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;
