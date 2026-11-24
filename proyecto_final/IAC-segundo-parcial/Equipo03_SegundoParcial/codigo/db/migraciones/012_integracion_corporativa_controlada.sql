-- =====================================================================
-- 012 — Integración corporativa controlada
--
-- QUÉ AGREGA, Y POR QUÉ NO ESTABA
-- --------------------------------
-- La estructura organizacional se cargaba a mano con una semilla. Eso
-- sirve para una demostración y no para operar: en una organización real
-- las áreas se parten, se fusionan y cambian de plantilla todos los
-- meses, y quien tiene ese dato es el sistema corporativo de recursos
-- humanos, no esta plataforma.
--
-- Pero conectar un sistema de recursos humanos a una plataforma de
-- bienestar es exactamente el momento donde este proyecto se puede
-- romper, y no por un error técnico: el sistema corporativo TIENE los
-- nombres, los puestos, los sueldos y las fechas de nacimiento, y la vía
-- de integración es por donde entrarían. Casi siempre entran sin que
-- nadie lo decida, porque el sistema de origen manda su registro
-- completo y el de destino guarda «lo que venga, por si acaso».
--
-- De ahí la forma de esta migración: no es un espejo del padrón
-- corporativo. Es una puerta estrecha con registro de lo que pasó por
-- ella y de lo que se rechazó.
--
-- LAS CINCO DECISIONES DEL MODELO
-- --------------------------------
-- 1. LA INTEGRACIÓN NUNCA CREA PERSONAS.
--    Es la decisión más importante y la menos obvia. Una persona creada
--    por una importación no tendría registro de consentimiento, y en este
--    sistema el consentimiento es lo que habilita que su respuesta cuente
--    (RN-02, `fn_registrar_autoreporte`). Una persona creada por
--    integración podría empezar a aparecer en agregados sin haber
--    aceptado nada. Por eso un identificador externo que no corresponda a
--    un seudónimo ya existente es un HALLAZGO, no un alta.
--
-- 2. SOLO ENTRA LA ESTRUCTURA, Y LOS CAMPOS DE PERSONA SE RECHAZAN.
--    No se ignoran: se rechazan con error. Ignorarlos sería lo cómodo y
--    tiene una consecuencia mala: el sistema de origen sigue mandándolos,
--    nadie se entera, y el día que alguien «mejore» el importador para no
--    desperdiciar datos, ya están llegando. Un rechazo ruidoso obliga a
--    arreglar el origen.
--
-- 3. VALIDAR Y APLICAR SON DOS MODOS, Y VALIDAR NO ESCRIBE NADA.
--    Quien integra necesita poder preguntar «¿esto pasaría?» sin
--    arriesgarse. Sin modo de validación, la única forma de saber si un
--    archivo sirve es aplicarlo.
--
-- 4. APLICAR ES TODO O NADA.
--    Aquí sí, y es la decisión OPUESTA a la de sync-service (migración
--    011), a propósito. Un lote de autoreportes a medio aplicar son
--    respuestas guardadas, que es un resultado útil. Un árbol
--    organizacional a medio aplicar son unidades huérfanas: el alcance de
--    los perfiles se calcula recorriendo ese árbol, y un árbol roto
--    significa gente viendo datos de áreas que no le tocan, o no viendo
--    los suyos.
--
-- 5. LA JERARQUÍA IMPORTADA TIENE QUE CUADRAR.
--    La plantilla de una unidad padre debe ser la suma de sus hijas. No
--    es una pulcritud: el control de inferencia resta la plantilla del
--    padre menos la de las hijas conocidas para detectar si alguien está
--    aislando un grupo por debajo del umbral k. Con un árbol que no
--    cuadra, ese resto da cualquier cosa y el control deja de servir.
--    Esto ya pasó en este proyecto: la semilla creaba padres con
--    plantilla propia y el control de inferencia quedó neutralizado hasta
--    que se arregló en la migración 008. Una importación sin esta
--    validación lo volvería a romper, y esta vez desde fuera.
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS integracion;

COMMENT ON SCHEMA integracion IS
  'Puerta de entrada para datos del sistema corporativo. Admite '
  'estructura organizacional e identificadores seudonimizados, y nada '
  'mas. No crea personas: ver la decision 1 de la migracion 012.';

-- ---------------------------------------------------------------------
-- Las fuentes corporativas registradas
-- ---------------------------------------------------------------------
-- Una fuente no registrada no puede integrar. Parece obvio y no lo es:
-- lo normal es aceptar de cualquiera que traiga un token válido, y
-- entonces cualquier componente con credenciales de la organización
-- puede reescribir el árbol organizacional.
CREATE TABLE IF NOT EXISTS integracion.fuente (
    fuente_id         VARCHAR(40)  PRIMARY KEY,
    nombre            VARCHAR(140) NOT NULL,
    descripcion       TEXT         NOT NULL,
    -- Qué tiene permitido mandar esta fuente. Que sea explícito por
    -- fuente evita el caso en que una integración creada para una cosa
    -- se usa después para otra sin que nadie lo revise.
    admite_estructura BOOLEAN      NOT NULL DEFAULT false,
    admite_identificadores BOOLEAN NOT NULL DEFAULT false,
    activa            BOOLEAN      NOT NULL DEFAULT true,
    motivo            TEXT         NOT NULL,
    fecha_registro    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Cada corrida de integración
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS integracion.ingesta (
    ingesta_id        BIGSERIAL PRIMARY KEY,
    fuente_id         VARCHAR(40)  NOT NULL
                                   REFERENCES integracion.fuente(fuente_id),
    tipo              VARCHAR(30)  NOT NULL,
    modo              VARCHAR(10)  NOT NULL,
    formato           VARCHAR(10)  NOT NULL,
    actor_usuario_id  VARCHAR(20)  REFERENCES usuarios.usuario(usuario_id),
    renglones         INT          NOT NULL DEFAULT 0,
    aplicados         INT          NOT NULL DEFAULT 0,
    errores           INT          NOT NULL DEFAULT 0,
    advertencias      INT          NOT NULL DEFAULT 0,
    veredicto         VARCHAR(20)  NOT NULL,
    -- Sello del contenido recibido. Sin él, dos corridas con el mismo
    -- resultado no se pueden distinguir de una corrida repetida, y
    -- nadie puede demostrar qué archivo se aplicó.
    sello_sha256      CHAR(64),
    correlacion_id    VARCHAR(40),
    fecha_ingesta     TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_ingesta_tipo
        CHECK (tipo IN ('ESTRUCTURA', 'IDENTIFICADORES')),
    CONSTRAINT ck_ingesta_modo
        CHECK (modo IN ('VALIDAR', 'APLICAR')),
    CONSTRAINT ck_ingesta_formato
        CHECK (formato IN ('JSON', 'XML')),
    CONSTRAINT ck_ingesta_veredicto
        CHECK (veredicto IN ('ACEPTADA', 'RECHAZADA', 'SOLO_VALIDADA'))
);

CREATE INDEX IF NOT EXISTS idx_ingesta_fuente
    ON integracion.ingesta (fuente_id, fecha_ingesta DESC);

COMMENT ON COLUMN integracion.ingesta.modo IS
  'VALIDAR no escribe nada: contesta si el archivo pasaria. Sin este '
  'modo, la unica forma de saber si un archivo sirve seria aplicarlo.';

COMMENT ON COLUMN integracion.ingesta.veredicto IS
  'SOLO_VALIDADA es el veredicto de una corrida en modo VALIDAR que '
  'habria pasado. Se distingue de ACEPTADA a proposito: confundirlas '
  'haria creer que el arbol ya se actualizo cuando no se toco.';

-- ---------------------------------------------------------------------
-- Los hallazgos: por qué se rechazó, renglón por renglón
-- ---------------------------------------------------------------------
-- Un rechazo sin detalle obliga a adivinar. Y quien tiene que arreglar
-- el archivo no es quien opera esta plataforma, es el equipo del sistema
-- corporativo: si el error no dice el renglón y el campo, el arreglo
-- pasa por una cadena de correos.
CREATE TABLE IF NOT EXISTS integracion.hallazgo (
    hallazgo_id       BIGSERIAL PRIMARY KEY,
    ingesta_id        BIGINT       NOT NULL
                                   REFERENCES integracion.ingesta(ingesta_id)
                                   ON DELETE CASCADE,
    renglon           INT,
    campo             VARCHAR(80),
    codigo            VARCHAR(40)  NOT NULL,
    severidad         VARCHAR(12)  NOT NULL,
    detalle           TEXT         NOT NULL,

    CONSTRAINT ck_hallazgo_severidad
        CHECK (severidad IN ('ERROR', 'ADVERTENCIA'))
);

CREATE INDEX IF NOT EXISTS idx_hallazgo_ingesta
    ON integracion.hallazgo (ingesta_id, severidad);

COMMENT ON COLUMN integracion.hallazgo.severidad IS
  'ERROR impide aplicar; ADVERTENCIA no. La distincion existe porque sin '
  'ella todo se vuelve error y la integracion se vuelve inusable, o todo '
  'se vuelve advertencia y deja de proteger.';

-- ---------------------------------------------------------------------
-- La correspondencia de identificadores seudonimizados
-- ---------------------------------------------------------------------
-- Esta tabla guarda DOS CADENAS OPACAS y nada más: el identificador que
-- usa el sistema corporativo y el seudónimo interno. No hay nombre, ni
-- correo, ni empleado_id, ni unidad. El vínculo con la persona real vive
-- en el sistema corporativo, y el vínculo seudónimo→empleado vive en
-- `consentimiento.seudonimo`, al que esta tabla no se une nunca.
--
-- Juntar las tres cosas en un solo lugar sería reconstruir la
-- identificación completa, que es justo lo que la seudonimización
-- existe para evitar.
CREATE TABLE IF NOT EXISTS integracion.identificador_externo (
    fuente_id          VARCHAR(40) NOT NULL
                                   REFERENCES integracion.fuente(fuente_id),
    identificador_externo VARCHAR(80) NOT NULL,
    seudonimo_id       VARCHAR(30)  NOT NULL
                       REFERENCES consentimiento.seudonimo(seudonimo_id),
    activo             BOOLEAN      NOT NULL DEFAULT true,
    fecha_vinculo      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (fuente_id, identificador_externo),
    -- Y al revés: un seudónimo interno no puede corresponder a dos
    -- identificadores de la misma fuente. Si pudiera, la misma persona
    -- entraría dos veces y contaría doble en cualquier conteo.
    CONSTRAINT ux_identificador_seudonimo UNIQUE (fuente_id, seudonimo_id)
);

COMMENT ON TABLE integracion.identificador_externo IS
  'Dos cadenas opacas y nada mas. Sin nombre, sin correo, sin '
  'empleado_id, sin unidad. Nunca se une con consentimiento.seudonimo: '
  'juntar las dos cosas reconstruiria la identificacion completa.';

-- ---------------------------------------------------------------------
-- La validación de la jerarquía, como función de la base
-- ---------------------------------------------------------------------
-- Está aquí y no en el servicio porque la invariante es de los datos, no
-- de un componente. Si viviera solo en Python, cualquier otra vía de
-- escritura —una semilla, un arreglo manual, otro servicio— podría
-- dejar el árbol sin cuadrar, y el control de inferencia se apagaría sin
-- que nadie lo notara. Ya pasó así una vez (migración 008).
CREATE OR REPLACE FUNCTION integracion.fn_validar_arbol_propuesto(
    p_unidades JSONB   -- [{"unidad_organizacional_id":..,"unidad_padre_id":..,"plantilla_declarada":..}, ...]
) RETURNS TABLE (codigo VARCHAR, campo VARCHAR, detalle TEXT)
LANGUAGE plpgsql
STABLE
SET search_path = integracion, organizacion, pg_temp
AS $$
BEGIN
    -- 1. Un padre que no viene en el archivo ni existe ya: unidad huérfana.
    RETURN QUERY
    WITH propuesta AS (
        SELECT x->>'unidad_organizacional_id' AS id,
               x->>'unidad_padre_id'          AS padre,
               (x->>'plantilla_declarada')::INT AS plantilla
          FROM jsonb_array_elements(p_unidades) AS x)
    SELECT 'PADRE_INEXISTENTE'::VARCHAR,
           'unidad_padre_id'::VARCHAR,
           format('La unidad %s declara el padre %s, que no viene en el '
                  'archivo ni existe en el arbol actual. Aplicarlo dejaria '
                  'una unidad huerfana, y el alcance de los perfiles se '
                  'calcula recorriendo el arbol.', p.id, p.padre)::TEXT
      FROM propuesta p
     WHERE p.padre IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM propuesta q WHERE q.id = p.padre)
       AND NOT EXISTS (SELECT 1 FROM organizacion.unidad_organizacional u
                        WHERE u.unidad_organizacional_id = p.padre);

    -- 2. Una unidad que se declara su propio padre. El caso de un ciclo
    --    más largo lo detecta el recorrido del paso 3.
    RETURN QUERY
    WITH propuesta AS (
        SELECT x->>'unidad_organizacional_id' AS id,
               x->>'unidad_padre_id'          AS padre
          FROM jsonb_array_elements(p_unidades) AS x)
    SELECT 'CICLO'::VARCHAR, 'unidad_padre_id'::VARCHAR,
           format('La unidad %s se declara su propio padre. El alcance se '
                  'calcula con un recorrido recursivo: un ciclo lo deja '
                  'girando.', p.id)::TEXT
      FROM propuesta p WHERE p.padre = p.id;

    -- 3. Ciclo de más de un salto, dentro de lo propuesto.
    RETURN QUERY
    -- El auto-padre se excluye aquí: el paso 2 ya lo reportó, y dejarlo
    -- dentro del recorrido genera una cadena infinita (D→D→D…) que vuelve
    -- a dispararse en el segundo salto. Es lo que pasaba: una sola unidad
    -- con auto-padre producía dos hallazgos de CICLO.
    WITH RECURSIVE propuesta AS (
        SELECT x->>'unidad_organizacional_id' AS id,
               x->>'unidad_padre_id'          AS padre
          FROM jsonb_array_elements(p_unidades) AS x
         WHERE x->>'unidad_padre_id' IS DISTINCT FROM
               x->>'unidad_organizacional_id'),
    subida AS (
        SELECT p.id AS origen, p.padre AS actual, 1 AS saltos
          FROM propuesta p WHERE p.padre IS NOT NULL
        UNION ALL
        SELECT s.origen, p.padre, s.saltos + 1
          FROM subida s
          JOIN propuesta p ON p.id = s.actual
         WHERE s.saltos < 20 AND p.padre IS NOT NULL)
    -- `saltos > 1` deja fuera el caso de un solo salto, que ya reportó el
    -- paso 2. Sin esa condición la misma unidad sale dos veces con el
    -- mismo código, y un informe que repite hallazgos hace dudar de la
    -- cuenta de errores.
    SELECT DISTINCT 'CICLO'::VARCHAR, 'unidad_padre_id'::VARCHAR,
           format('La unidad %s acaba siendo su propia ancestra siguiendo '
                  'los padres declarados.', s.origen)::TEXT
      FROM subida s WHERE s.actual = s.origen;

    -- 4. La plantilla del padre tiene que ser la suma de sus hijas. Esta
    --    es la que protege el control de inferencia.
    RETURN QUERY
    WITH propuesta AS (
        SELECT x->>'unidad_organizacional_id' AS id,
               x->>'unidad_padre_id'          AS padre,
               (x->>'plantilla_declarada')::INT AS plantilla
          FROM jsonb_array_elements(p_unidades) AS x),
    con_hijas AS (
        SELECT p.id, p.plantilla,
               (SELECT sum(h.plantilla) FROM propuesta h WHERE h.padre = p.id)
                   AS suma_hijas
          FROM propuesta p)
    SELECT 'JERARQUIA_NO_CUADRA'::VARCHAR,
           'plantilla_declarada'::VARCHAR,
           format('La unidad %s declara plantilla %s y sus hijas suman %s. '
                  'El control de inferencia resta la plantilla del padre '
                  'menos la de las hijas conocidas para ver si alguien esta '
                  'aislando un grupo por debajo del umbral k; con un arbol '
                  'que no cuadra, ese resto da cualquier cosa y el control '
                  'deja de servir.',
                  c.id, c.plantilla, c.suma_hijas)::TEXT
      FROM con_hijas c
     WHERE c.suma_hijas IS NOT NULL AND c.suma_hijas <> c.plantilla;
END $$;

COMMENT ON FUNCTION integracion.fn_validar_arbol_propuesto(JSONB) IS
  'Valida un arbol organizacional propuesto SIN escribir nada. Vive en '
  'la base y no en el servicio porque la invariante es de los datos: si '
  'viviera solo en Python, otra via de escritura podria dejar el arbol '
  'sin cuadrar y apagar el control de inferencia en silencio.';

-- ---------------------------------------------------------------------
-- Permisos del rol de la aplicación
-- ---------------------------------------------------------------------
-- Sin DELETE en ninguna: una ingesta registrada no se borra, porque el
-- registro de lo que entró —y de lo que se rechazó— es la mitad del
-- valor de tener una puerta.
GRANT USAGE ON SCHEMA integracion TO bienestar_app;
GRANT SELECT ON integracion.fuente TO bienestar_app;
GRANT SELECT, INSERT, UPDATE ON integracion.ingesta TO bienestar_app;
GRANT SELECT, INSERT ON integracion.hallazgo TO bienestar_app;
GRANT SELECT, INSERT, UPDATE ON integracion.identificador_externo
      TO bienestar_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA integracion TO bienestar_app;
GRANT EXECUTE ON FUNCTION integracion.fn_validar_arbol_propuesto(JSONB)
      TO bienestar_app;
-- La integración de estructura escribe en el árbol organizacional. El
-- rol ya tiene lo necesario sobre esa tabla desde la migración 004.

-- ---------------------------------------------------------------------
-- Una fuente de ejemplo, para que la demostración tenga contra qué correr
-- ---------------------------------------------------------------------
INSERT INTO integracion.fuente
  (fuente_id, nombre, descripcion, admite_estructura,
   admite_identificadores, motivo)
VALUES
  ('FC-RH-CORPORATIVO',
   'Sistema corporativo de recursos humanos',
   'Entrega la estructura de unidades con su plantilla declarada y la '
   'correspondencia de identificadores seudonimizados. No entrega, y no '
   'tiene permitido entregar, ningun dato de persona.',
   TRUE, TRUE,
   'Es el sistema que tiene el dato de estructura. Se le autoriza la '
   'estructura y los identificadores seudonimizados, y nada mas: los '
   'campos de persona se rechazan con error, no se ignoran.'),
  ('FC-NOMINA',
   'Sistema de nomina',
   'Registrada y NO autorizada a proposito, para que quede escrito por '
   'que: tiene sueldos y datos fiscales, y no hay ninguna funcionalidad '
   'de esta plataforma que los necesite.',
   FALSE, FALSE,
   'Sin finalidad. Una integracion sin finalidad declarada es la via por '
   'la que entran datos que nadie pidio.')
ON CONFLICT (fuente_id) DO NOTHING;

-- ---------------------------------------------------------------------
-- Acciones y resultados nuevos en la bitácora
-- ---------------------------------------------------------------------
INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('INTEGRACION_VALIDADA',
   'Se valido un archivo de integracion sin aplicarlo.', FALSE),
  ('INTEGRACION_APLICADA',
   'Se aplico una integracion. Modifica el arbol organizacional, del que '
   'depende el alcance de todos los perfiles.', TRUE),
  ('INTEGRACION_RECHAZADA',
   'Se nego una integracion. El motivo queda en integracion.hallazgo, '
   'renglon por renglon.', TRUE),
  ('CAMPO_DE_PERSONA_RECHAZADO',
   'Un archivo de integracion traia campos de persona. Se rechaza con '
   'error y no se ignora: ignorarlos dejaria al sistema de origen '
   'mandandolos sin que nadie se entere.', TRUE)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO auditoria.resultado (codigo, descripcion) VALUES
  ('SOLO_VALIDADA',
   'La corrida paso la validacion y no escribio nada, porque iba en modo '
   'VALIDAR.')
ON CONFLICT (codigo) DO NOTHING;

COMMIT;

-- Verificación:
--
--   -- La invariante que protege el control de inferencia:
--   SELECT * FROM integracion.fn_validar_arbol_propuesto('[
--     {"unidad_organizacional_id":"A","unidad_padre_id":null,
--      "plantilla_declarada":10},
--     {"unidad_organizacional_id":"B","unidad_padre_id":"A",
--      "plantilla_declarada":4}]'::jsonb);
--   -- Devuelve JERARQUIA_NO_CUADRA: A dice 10 y su unica hija suma 4.
--
--   -- Y la fuente que esta registrada para quedar NO autorizada:
--   SELECT fuente_id, admite_estructura, motivo FROM integracion.fuente;
