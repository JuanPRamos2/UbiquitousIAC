-- =====================================================================
-- 015 — Las dos acciones que faltaban del ciclo de una intervención
--
-- QUÉ ESTABA PASANDO
-- ------------------
-- `interventions-service` registraba el cambio de estado y el avance de
-- un plan con el código `INTERVENCION_SEGUIMIENTO`. Ese código existe,
-- pero en `usuarios.permiso`: es un **permiso**, no una acción de
-- bitácora. En `auditoria.tipo_accion` no estaba.
--
-- `auditoria.bitacora` tiene llave foránea contra `auditoria.tipo_accion`,
-- así que el INSERT fallaba, y como va envuelto en un try para no tumbar
-- la operación principal, fallaba **en silencio**. El efecto: ni un
-- cambio de estado ni un avance quedaban registrados, y el ciclo de
-- aprobación de una intervención —que es la parte auditable del
-- proceso, la razón de que las transiciones estén declaradas— no tenía
-- rastro de ninguna de sus transiciones excepto la aprobación.
--
-- Es la tercera vez que este modo de falla aparece en el proyecto: la 007
-- fue por `RECHAZADO_PERMISO`, la 014 por `COMPONENTE_REINICIADO`, y esta.
-- Por eso ahora hay pruebas que recorren el código buscando códigos de
-- bitácora que no existan en la base, en lugar de confiar en acordarse.
--
-- POR QUÉ DOS ACCIONES Y NO UNA
-- ------------------------------
-- Lo cómodo habría sido declarar `INTERVENCION_SEGUIMIENTO` como acción y
-- dejar el código igual. No se hizo por dos motivos.
--
-- El primero: un código que es a la vez permiso y acción deja la bitácora
-- ambigua. Quien filtre por él no sabe si está viendo «alguien usó el
-- permiso de seguimiento» o «alguien registró un avance».
--
-- El segundo, y es el que importa: eran **dos eventos distintos**
-- metidos en el mismo código. Que un plan pase de APROBADA a EN_EJECUCION
-- es un hecho del ciclo de aprobación; que alguien escriba una nota de
-- avance es otro. Con un solo código, reconstruir cuándo se movió un plan
-- exige leer las notas y adivinar, y la auditoría del ciclo —que es para
-- lo único que existen las transiciones declaradas— se vuelve inútil.
-- =====================================================================

BEGIN;

INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('INTERVENCION_ESTADO_CAMBIADO',
   'Un plan de intervencion avanzo por una transicion declarada: de '
   'APROBADA a EN_EJECUCION, a FINALIZADA, o a CANCELADA desde cualquier '
   'estado vivo. Se separa de INTERVENCION_APROBADA porque aprobar exige '
   'un permiso distinto —quien detecta la necesidad no es quien autoriza '
   'el cambio organizacional— y porque la aprobacion es el punto del '
   'ciclo que de verdad se audita.',
   TRUE),
  ('INTERVENCION_AVANCE',
   'Se agrego una entrada al historial de avance de un plan. Las entradas '
   'no se editan ni se borran: un historial editable no sirve para '
   'reconstruir que se sabia en cada momento, que es para lo unico que '
   'existe.',
   FALSE)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;

-- Verificación:
--
--   SELECT codigo, sensible FROM auditoria.tipo_accion
--    WHERE codigo IN ('INTERVENCION_ESTADO_CAMBIADO', 'INTERVENCION_AVANCE');
--
--   -- Y que el registro de verdad entra, que es lo que el try esconde.
--   -- Despues de mover un plan y registrarle un avance:
--   SELECT accion, resultado, recurso_id FROM auditoria.bitacora
--    WHERE accion LIKE 'INTERVENCION%' ORDER BY fecha_hora DESC LIMIT 5;
