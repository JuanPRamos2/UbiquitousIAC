-- =====================================================================
-- 014 — La acción que faltaba para registrar un reinicio
--
-- QUÉ AGREGA, Y POR QUÉ ES UN ARCHIVO ENTERO PARA UNA FILA
-- ---------------------------------------------------------
-- `monitoring-service` detecta que un componente se reinició comparando
-- la identidad de instancia que ese componente reporta en
-- `/health/live`. Cuando lo detecta, lo escribe en la bitácora con la
-- acción `COMPONENTE_REINICIADO`.
--
-- `auditoria.bitacora` tiene llave foránea contra `auditoria.tipo_accion`.
-- Un código que no esté declarado hace fallar la inserción, y como el
-- registro va envuelto en un try para no tumbar la petición, **falla en
-- silencio**.
--
-- Eso importa más aquí que en otros sitios. Redis recorta su propia
-- ventana de reinicios, así que la bitácora es el único lugar donde queda
-- rastro de un bucle de reinicios de ayer. Sin esta fila, la supervisión
-- de contenedores funcionaría en la pantalla y no guardaría nada, que es
-- el peor resultado posible: se ve bien y no sirve.
--
-- Es el mismo error que costó todos los rechazos de permiso antes de la
-- migración 007, y por eso ahora hay una prueba
-- (`test_todo_resultado_que_se_escribe_existe_en_la_base`) que lo busca.
-- =====================================================================

BEGIN;

INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('COMPONENTE_REINICIADO',
   'Un componente reporto una identidad de instancia distinta de la que '
   'se le habia visto: su proceso se reinicio. Se registra porque las '
   'sondas de salud NO ven un reinicio —cada sonda le llega a un proceso '
   'recien arrancado, que contesta que esta bien— y porque la ventana que '
   'guarda Redis se recorta sola: sin este registro, un bucle de '
   'reinicios de ayer no se puede reconstruir hoy.',
   FALSE)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;

-- Verificación:
--
--   SELECT codigo FROM auditoria.tipo_accion
--    WHERE codigo = 'COMPONENTE_REINICIADO';
--
--   -- Y que el registro de verdad entra, que es lo que el try esconde:
--   SELECT accion, resultado, recurso_id, fecha_hora
--     FROM auditoria.bitacora
--    WHERE accion = 'COMPONENTE_REINICIADO'
--    ORDER BY fecha_hora DESC LIMIT 5;
