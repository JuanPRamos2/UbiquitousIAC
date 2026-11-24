-- =====================================================================
-- 011 — Sincronización desde los clientes, con idempotencia
--
-- QUÉ AGREGA, Y POR QUÉ NO ESTABA
-- --------------------------------
-- Las dos aplicaciones cliente —la de escritorio y la móvil— capturan
-- respuestas donde no siempre hay red: un turno de planta, una ruta de
-- reparto, una bodega. Hasta ahora cada una enviaba una respuesta por
-- petición y confiaba en que la petición llegaba.
--
-- Con red intermitente esa confianza es el problema entero, porque el
-- cliente NO PUEDE DISTINGUIR dos situaciones que se ven igual desde su
-- lado:
--
--     a) la petición no llegó al servidor;
--     b) la petición llegó, se aplicó, y la respuesta se perdió al volver.
--
-- En (a) hay que reenviar. En (b) reenviar duplica. Y como no se pueden
-- distinguir, el cliente razonable reenvía siempre, así que el servidor
-- tiene que ser quien haga que reenviar sea inofensivo. De ahí esta
-- migración: no agrega una tabla de «datos sincronizados», agrega la
-- memoria de QUÉ OPERACIONES YA SE APLICARON.
--
-- LAS CUATRO DECISIONES DEL MODELO
-- ---------------------------------
-- 1. LA IDEMPOTENCIA ES POR CLAVE DEL CLIENTE, NO POR CONTENIDO.
--    El cliente genera un identificador por operación, antes del primer
--    intento, y lo repite en cada reenvío. Comparar por contenido sería
--    lo intuitivo y estaría mal: dos personas del mismo turno pueden
--    contestar exactamente lo mismo, y con comparación por contenido la
--    segunda respuesta legítima se descartaría como duplicada. Un
--    identificador de operación distingue «lo mismo otra vez» de «otro
--    que contestó igual», que es la diferencia que importa.
--
-- 2. EL RESULTADO SE GUARDA, NO SOLO EL HECHO DE HABER PROCESADO.
--    Un reenvío tiene que recibir la MISMA respuesta que el primer
--    intento, no un «ya estaba». Si el cliente recibiera otra respuesta,
--    tendría que decidir qué hacer con la diferencia y volveríamos al
--    problema de origen. Por eso se guarda el estado y el mensaje.
--
-- 3. SE GUARDA TAMBIÉN LA OPERACIÓN RECHAZADA.
--    Un rechazo es un resultado y es idempotente igual: reenviar algo
--    mal formado tiene que volver a dar el mismo rechazo y no ocupar la
--    tubería otra vez. Además, un cliente que reenvía mil veces lo mismo
--    rechazado es un cliente roto, y sin registro no hay cómo verlo.
--
-- 4. EL LOTE NO ES TODO O NADA.
--    Cada renglón se resuelve por su cuenta. Un lote de cuarenta
--    respuestas con una mal formada no puede perder las otras treinta y
--    nueve: el cliente que las capturó sin red no tiene cómo recuperarlas
--    si el servidor las rechaza en bloque por culpa de otra.
--    (integration-service toma la decisión OPUESTA, y a propósito: un
--    árbol organizacional a medio importar queda incoherente, mientras
--    que treinta y nueve respuestas guardadas son treinta y nueve
--    respuestas guardadas.)
--
-- LO QUE ESTA MIGRACIÓN NO HACE
-- ------------------------------
-- No guarda las respuestas. Las respuestas siguen entrando por
-- `autoreporte.fn_registrar_autoreporte`, que es la única vía y la que
-- aplica las reglas de negocio (campaña abierta, consentimiento vigente,
-- una respuesta por campaña). Una tabla de «respuestas sincronizadas»
-- habría sido un segundo camino de entrada sin esas reglas, y el primero
-- que las saltara habría contaminado los agregados.
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS sincronizacion;

COMMENT ON SCHEMA sincronizacion IS
  'Memoria de operaciones aplicadas, para que reenviar sea inofensivo. '
  'No guarda datos de autoreporte: esos entran por '
  'autoreporte.fn_registrar_autoreporte y por ningun otro lado.';

-- ---------------------------------------------------------------------
-- El lote: una entrega de un cliente, con su resumen
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sincronizacion.lote (
    lote_id             BIGSERIAL PRIMARY KEY,
    lote_cliente_id     VARCHAR(80)  NOT NULL,
    origen              VARCHAR(20)  NOT NULL,
    actor_usuario_id    VARCHAR(20)  REFERENCES usuarios.usuario(usuario_id),
    formato             VARCHAR(10)  NOT NULL DEFAULT 'JSON',
    recibidas           INT          NOT NULL DEFAULT 0,
    aplicadas           INT          NOT NULL DEFAULT 0,
    duplicadas          INT          NOT NULL DEFAULT 0,
    rechazadas          INT          NOT NULL DEFAULT 0,
    en_conflicto        INT          NOT NULL DEFAULT 0,
    correlacion_id      VARCHAR(40),
    fecha_recepcion     TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_lote_origen
        CHECK (origen IN ('ESCRITORIO', 'MOVIL', 'WEB', 'OTRO')),
    CONSTRAINT ck_lote_formato
        CHECK (formato IN ('JSON', 'XML')),
    -- El mismo lote reenviado NO crea un segundo renglón: es la
    -- idempotencia a nivel de lote, y es lo que hace que el cliente
    -- pueda reenviar el lote completo sin pensar.
    CONSTRAINT ux_lote_cliente UNIQUE (lote_cliente_id)
);

COMMENT ON COLUMN sincronizacion.lote.lote_cliente_id IS
  'Identificador que genera el CLIENTE antes del primer envio. Es lo que '
  'permite que un reenvio se reconozca como el mismo lote.';

-- ---------------------------------------------------------------------
-- La operación: el renglón que de verdad sostiene la idempotencia
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sincronizacion.operacion (
    operacion_id        BIGSERIAL PRIMARY KEY,
    operacion_cliente_id VARCHAR(80) NOT NULL,
    lote_id             BIGINT       NOT NULL
                                     REFERENCES sincronizacion.lote(lote_id),
    tipo                VARCHAR(30)  NOT NULL,
    -- El seudónimo, nunca el empleado. Esta tabla la lee el rol de la
    -- aplicación, y si guardara `empleado_id` tendría el vínculo que el
    -- resto del sistema se cuida de no tener en ningún lado accesible.
    seudonimo_id        VARCHAR(64),
    campania_id         VARCHAR(40)  REFERENCES catalogo.campania(campania_id),
    estado              VARCHAR(30)  NOT NULL,
    mensaje             TEXT,
    reintentable        BOOLEAN      NOT NULL DEFAULT false,
    -- Huella del contenido, solo para DETECTAR que un mismo
    -- identificador de operación llegó con contenido distinto. No se usa
    -- para deduplicar (ver decisión 1 del encabezado).
    huella_contenido    CHAR(64),
    intentos            INT          NOT NULL DEFAULT 1,
    fecha_primera       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fecha_ultima        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_operacion_tipo
        CHECK (tipo IN ('AUTOREPORTE', 'CONSENTIMIENTO', 'EVIDENCIA')),
    CONSTRAINT ck_operacion_estado
        CHECK (estado IN ('APLICADA', 'RECHAZADA', 'EN_CONFLICTO',
                          'DUPLICADA', 'ERROR_TEMPORAL')),
    -- La restricción que hace todo el trabajo: un identificador de
    -- operación se aplica UNA vez, y el segundo intento encuentra el
    -- resultado guardado en lugar de aplicar otra vez.
    CONSTRAINT ux_operacion_cliente UNIQUE (operacion_cliente_id)
);

CREATE INDEX IF NOT EXISTS idx_operacion_lote
    ON sincronizacion.operacion (lote_id);
CREATE INDEX IF NOT EXISTS idx_operacion_estado
    ON sincronizacion.operacion (estado, fecha_ultima DESC);
-- Para ver un cliente que reenvía lo mismo sin parar, que es un cliente
-- roto y no se nota de otra forma.
CREATE INDEX IF NOT EXISTS idx_operacion_intentos
    ON sincronizacion.operacion (intentos DESC)
    WHERE intentos > 3;

COMMENT ON COLUMN sincronizacion.operacion.reintentable IS
  'Si el cliente DEBE volver a intentarlo. Un rechazo por datos mal '
  'formados no es reintentable —volvera a fallar igual— y una falla '
  'temporal si lo es. Sin esta distincion el cliente reintenta lo que '
  'nunca va a pasar, o abandona lo que si habria pasado.';

COMMENT ON COLUMN sincronizacion.operacion.huella_contenido IS
  'SHA-256 del contenido normalizado. Solo para detectar que un mismo '
  'operacion_cliente_id llego con contenido distinto, que significa un '
  'cliente que reusa identificadores: no se aplica el segundo contenido, '
  'y queda registrado.';

-- ---------------------------------------------------------------------
-- Lo que el rol de la aplicación puede hacer aquí
-- ---------------------------------------------------------------------
-- Sin DELETE: una operación aplicada no se borra. Si se pudiera borrar,
-- un reenvío posterior la volvería a aplicar y la idempotencia duraría
-- lo que durara la fila.
GRANT USAGE ON SCHEMA sincronizacion TO bienestar_app;
GRANT SELECT, INSERT, UPDATE ON sincronizacion.lote TO bienestar_app;
GRANT SELECT, INSERT, UPDATE ON sincronizacion.operacion TO bienestar_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sincronizacion TO bienestar_app;

-- ---------------------------------------------------------------------
-- Acciones y resultados nuevos en la bitácora
-- ---------------------------------------------------------------------
-- auditoria.bitacora tiene llave foránea contra auditoria.tipo_accion y
-- contra auditoria.resultado. Un código que no esté aquí hace fallar la
-- inserción, y como el registro va envuelto en un try para no tumbar la
-- operación principal, falla EN SILENCIO. Ya pasó una vez: se perdieron
-- todos los rechazos de permiso hasta que la migración 007 lo arregló.
INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('SINCRONIZACION_RECIBIDA',
   'Un cliente entrego un lote de operaciones para aplicar.',
   FALSE),
  ('SINCRONIZACION_REENVIADA',
   'Un cliente reenvio un lote ya aplicado. No se aplico nada otra vez: '
   'se devolvio el resultado guardado. Es el caso normal con red '
   'intermitente, no una anomalia.',
   FALSE),
  ('OPERACION_EN_CONFLICTO',
   'Una operacion choco con una regla que no se resuelve sobrescribiendo '
   '—una campania ya respondida, por ejemplo— y se conservo lo que ya '
   'estaba. Importa registrarlo: sobrescribir habria cambiado un dato que '
   'quizas ya entro en un agregado publicado.',
   TRUE),
  ('IDENTIFICADOR_REUSADO',
   'Un mismo identificador de operacion llego con contenido distinto. '
   'Describe un cliente roto, y sin registro no hay como verlo.',
   TRUE)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO auditoria.resultado (codigo, descripcion) VALUES
  ('DUPLICADA',
   'La operacion ya se habia aplicado; se devolvio el resultado guardado '
   'sin volver a aplicar.'),
  ('EN_CONFLICTO',
   'Choco con un dato que ya existia y que no se sobrescribe.'),
  ('PARCIAL',
   'Parte del lote se aplico y parte no. Es el resultado NORMAL de un '
   'lote, no una falla: cada renglon se resuelve por su cuenta.')
ON CONFLICT (codigo) DO NOTHING;

COMMIT;

-- Verificación:
--
--   SELECT codigo FROM auditoria.resultado
--    WHERE codigo IN ('DUPLICADA','EN_CONFLICTO','PARCIAL');
--
--   -- Que reenviar sea inofensivo depende de estas dos restricciones:
--   SELECT conname FROM pg_constraint
--    WHERE conname IN ('ux_lote_cliente','ux_operacion_cliente');
