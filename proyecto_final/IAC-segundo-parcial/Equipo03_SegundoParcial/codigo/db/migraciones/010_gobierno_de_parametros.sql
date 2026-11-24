-- =====================================================================
-- 010 — Gobierno de los parámetros de privacidad
--
-- QUÉ FALTABA
-- -----------
-- `agregado.parametro_privacidad` existe desde el esquema base y guarda el
-- umbral k, los presupuestos de épsilon y la tolerancia de error. Tiene
-- columnas `actualizado_por` y `fecha_actualizacion`, y ahí estaba el
-- hueco: esas dos columnas guardan QUIÉN tocó el valor la última vez y
-- NADA más. Un UPDATE pisa el valor anterior y lo borra.
--
-- El efecto es el que importa: el umbral k es la afirmación central del
-- proyecto —«ningún resultado permite llegar a una persona»— y hasta ahora
-- se podía bajar de 5 a 2 con un UPDATE, sin justificación, sin que
-- quedara constancia del valor anterior y sin que nadie pudiera
-- reconstruir después con qué umbral se publicó cada campaña.
--
-- Esta migración agrega tres cosas:
--
--   1. UN HISTORIAL. Una fila por cambio, con el valor viejo, el nuevo,
--      quién y por qué. Sin el valor viejo, el historial no sirve para
--      reconstruir con qué umbral se publicó una campaña, que es para lo
--      único que existiría.
--
--   2. UN PISO QUE LA API NO PUEDE MOVER. El umbral k tiene un mínimo
--      absoluto declarado en la base y comprobado por una restricción.
--      Que sea una restricción y no una validación en el servicio importa:
--      una validación en Python la salta cualquiera que escriba un UPDATE
--      directo, y la afirmación del proyecto no puede depender de que
--      nadie lo haga.
--
--   3. LÍMITES POR PERFIL. Hoy los topes de consulta son constantes
--      dentro de cada servicio (`limite_consumo(maximo=120)`). Con eso, un
--      auditor que necesita revisar mil registros y un colaborador que
--      mira su propia participación tienen el mismo tope, y el único modo
--      de cambiarlo es volver a desplegar.
-- =====================================================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS configuracion;
COMMENT ON SCHEMA configuracion IS
  'Gobierno de los parametros del sistema: historial de cambios, pisos '
  'que la API no puede mover y limites por perfil.';

-- -------------------------------------------------------------------
-- 1. EL HISTORIAL DE CAMBIOS
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS configuracion.cambio_parametro (
  cambio_id        bigserial    PRIMARY KEY,
  clave            varchar(60)  NOT NULL,
  valor_anterior   numeric,
  valor_nuevo      numeric      NOT NULL,
  -- Obligatoria y con longitud mínima. Un cambio al umbral k sin motivo
  -- escrito es exactamente el cambio que nadie quiere tener que explicar
  -- seis meses después.
  justificacion    text         NOT NULL,
  actor_usuario_id varchar(20)  NOT NULL
                     REFERENCES usuarios.usuario(usuario_id),
  -- Qué campañas estaban abiertas cuando se hizo el cambio. Es el dato
  -- que permite saber si el cambio afectó a una medición en curso, y no
  -- se puede reconstruir después porque los estados de campaña cambian.
  campanias_abiertas text[]     NOT NULL DEFAULT '{}',
  fecha_cambio     timestamptz  NOT NULL DEFAULT now(),
  correlacion_id   varchar(40),
  CONSTRAINT cambio_justificacion_minima
    CHECK (length(btrim(justificacion)) >= 30)
);

CREATE INDEX IF NOT EXISTS idx_cambio_parametro_clave
  ON configuracion.cambio_parametro (clave, fecha_cambio DESC);

COMMENT ON TABLE configuracion.cambio_parametro IS
  'Una fila por cambio, con el valor ANTERIOR. Sin el valor anterior el '
  'historial no sirve para reconstruir con que umbral se publico cada '
  'campania, que es para lo unico que existiria.';

-- -------------------------------------------------------------------
-- 2. LOS LÍMITES DE CADA PARÁMETRO
-- -------------------------------------------------------------------
-- El piso del umbral k vive aquí y no en el código del servicio. Una
-- validación en Python la salta cualquiera que escriba un UPDATE directo
-- contra la base, y la afirmación central del proyecto no puede depender
-- de que nadie lo haga.
CREATE TABLE IF NOT EXISTS configuracion.limite_parametro (
  clave          varchar(60) PRIMARY KEY
                   REFERENCES agregado.parametro_privacidad(clave)
                   ON DELETE CASCADE,
  minimo         numeric,
  maximo         numeric,
  -- Si es TRUE, el valor no se puede cambiar mientras haya una campaña
  -- abierta. Ver la justificación de cada fila más abajo.
  congelar_en_campania_abierta boolean NOT NULL DEFAULT false,
  motivo         text NOT NULL,
  CONSTRAINT limite_coherente CHECK (minimo IS NULL OR maximo IS NULL
                                     OR minimo <= maximo)
);

INSERT INTO configuracion.limite_parametro
  (clave, minimo, maximo, congelar_en_campania_abierta, motivo) VALUES
  ('k_umbral_minimo', 5, 100, TRUE,
   'El piso de 5 es la afirmacion central del proyecto: por debajo, un '
   'agregado de 2 o 3 personas se publica y cualquiera que conozca el '
   'equipo sabe de quien es. El tope de 100 no es por seguridad sino por '
   'utilidad: con un umbral tan alto no se publicaria casi nada y el '
   'sistema dejaria de servir, que es otra forma de fallar. Congelado '
   'durante una campania abierta porque cambiarlo a mitad de la medicion '
   'produce un tablero donde unas unidades se publicaron con un criterio '
   'y otras con otro, sin que nada en la pantalla lo diga.'),
  ('epsilon_por_consulta', 0.01, 2.0, TRUE,
   'Subirlo agrega menos ruido y da valores mas exactos, que es lo que '
   'todo el mundo quiere y justo lo que no se puede dar: el ruido ES la '
   'proteccion. Bajarlo demasiado hace el valor inservible. Congelado en '
   'campania abierta: cambiarlo a mitad deja dos mitades del tablero con '
   'distinta proteccion.'),
  ('presupuesto_campania', 1.0, 20.0, TRUE,
   'Es cuantas publicaciones caben en una campania antes de que el '
   'presupuesto se agote. Subirlo a mitad de una campania abierta da mas '
   'consultas de las que se prometieron al autorizar la medicion; bajarlo '
   'puede dejar la campania agotada de golpe y sin poder publicar lo que '
   'falta. Entre campanias se ajusta sin problema.'),
  ('n_minimo_utilidad', 5, 500, FALSE,
   'Es un aviso de precision, no una proteccion: por debajo de este '
   'numero el valor publicado se marca como poco preciso. Cambiarlo no '
   'afecta a lo que se publica ni a quien queda protegido, asi que no '
   'hace falta congelarlo.'),
  ('error_tolerado', 0.05, 1.0, FALSE,
   'Tolerancia de error declarada para el analisis de utilidad. No '
   'participa en la decision de publicar.'),
  ('delta_objetivo', 0.0000001, 0.001, TRUE,
   'El delta de la privacidad diferencial aproximada. Subirlo relaja la '
   'garantia de forma que no se ve en ninguna pantalla.'),
  ('exportacion_vigencia_horas', 1, 720, FALSE,
   'Cuantas horas queda descargable un archivo de agregados. No afecta a '
   'la proteccion de lo ya publicado, solo a cuanto tiempo sigue '
   'sirviendo un enlace.')
ON CONFLICT (clave) DO NOTHING;

-- -------------------------------------------------------------------
-- 3. LA FUNCIÓN QUE HACE EL CAMBIO
-- -------------------------------------------------------------------
-- El cambio y su registro van en la MISMA transacción, dentro de una
-- función, y no en dos sentencias del servicio. Si fueran dos sentencias,
-- un error entre ellas dejaría el valor cambiado sin fila de historial
-- —el caso exacto que vuelve inútil un historial—, y nadie se enteraría
-- hasta que alguien preguntara por qué el umbral es otro.
CREATE OR REPLACE FUNCTION configuracion.fn_cambiar_parametro(
    p_clave          VARCHAR,
    p_valor          NUMERIC,
    p_justificacion  TEXT,
    p_actor          VARCHAR,
    p_correlacion    VARCHAR DEFAULT NULL)
RETURNS TABLE (valor_anterior NUMERIC, valor_nuevo NUMERIC, cambio_id BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = agregado, configuracion, catalogo, public
AS $$
DECLARE
    v_anterior NUMERIC;
    v_minimo   NUMERIC;
    v_maximo   NUMERIC;
    v_congelar BOOLEAN;
    v_motivo   TEXT;
    v_abiertas TEXT[];
    v_cambio   BIGINT;
BEGIN
    SELECT valor INTO v_anterior
      FROM agregado.parametro_privacidad WHERE clave = p_clave;
    IF v_anterior IS NULL THEN
        RAISE EXCEPTION 'PARAMETRO_NO_EXISTE: %', p_clave
              USING ERRCODE = 'no_data_found';
    END IF;

    SELECT minimo, maximo, congelar_en_campania_abierta, motivo
      INTO v_minimo, v_maximo, v_congelar, v_motivo
      FROM configuracion.limite_parametro WHERE clave = p_clave;

    -- Un parámetro sin límites declarados NO se puede cambiar por aquí.
    -- Es deliberado: el camino fácil sería permitirlo «porque nadie
    -- declaró un límite», y entonces agregar un parámetro nuevo lo
    -- dejaría sin protección sin que nadie lo decidiera.
    IF v_minimo IS NULL AND v_maximo IS NULL AND NOT FOUND THEN
        RAISE EXCEPTION 'PARAMETRO_SIN_LIMITES: % no tiene limites declarados '
                        'en configuracion.limite_parametro', p_clave
              USING ERRCODE = 'raise_exception';
    END IF;

    IF v_minimo IS NOT NULL AND p_valor < v_minimo THEN
        RAISE EXCEPTION 'FUERA_DE_LIMITE: % no puede bajar de %. %',
                        p_clave, v_minimo, v_motivo
              USING ERRCODE = 'check_violation';
    END IF;
    IF v_maximo IS NOT NULL AND p_valor > v_maximo THEN
        RAISE EXCEPTION 'FUERA_DE_LIMITE: % no puede pasar de %. %',
                        p_clave, v_maximo, v_motivo
              USING ERRCODE = 'check_violation';
    END IF;

    SELECT coalesce(array_agg(campania_id ORDER BY campania_id), '{}')
      INTO v_abiertas
      FROM catalogo.campania WHERE estado = 'ABIERTA';

    IF v_congelar AND array_length(v_abiertas, 1) > 0 THEN
        RAISE EXCEPTION 'CAMPANIA_ABIERTA: % no se puede cambiar mientras '
                        'haya una campania abierta (%). %',
                        p_clave, array_to_string(v_abiertas, ', '), v_motivo
              USING ERRCODE = 'object_not_in_prerequisite_state';
    END IF;

    IF length(btrim(coalesce(p_justificacion, ''))) < 30 THEN
        RAISE EXCEPTION 'JUSTIFICACION_INSUFICIENTE: hacen falta al menos 30 '
                        'caracteres explicando por que se cambia %', p_clave
              USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO configuracion.cambio_parametro
      (clave, valor_anterior, valor_nuevo, justificacion, actor_usuario_id,
       campanias_abiertas, correlacion_id)
    VALUES (p_clave, v_anterior, p_valor, p_justificacion, p_actor,
            v_abiertas, p_correlacion)
    RETURNING configuracion.cambio_parametro.cambio_id INTO v_cambio;

    UPDATE agregado.parametro_privacidad
       SET valor = p_valor,
           actualizado_por = p_actor,
           fecha_actualizacion = now()
     WHERE clave = p_clave;

    RETURN QUERY SELECT v_anterior, p_valor, v_cambio;
END $$;

COMMENT ON FUNCTION configuracion.fn_cambiar_parametro IS
  'Cambia un parametro y registra el cambio en la MISMA transaccion. Es '
  'SECURITY DEFINER porque el rol de la aplicacion no tiene UPDATE sobre '
  'agregado.parametro_privacidad: el unico camino para cambiar un umbral '
  'pasa por aqui, y por aqui siempre queda historial.';

-- -------------------------------------------------------------------
-- 4. LÍMITES DE CONSULTA POR PERFIL
-- -------------------------------------------------------------------
-- Hoy los topes son constantes dentro de cada servicio. Con eso, un
-- auditor que revisa mil registros y un colaborador que mira su propia
-- participación tienen el mismo tope, y el único modo de cambiarlo es
-- volver a desplegar.
CREATE TABLE IF NOT EXISTS configuracion.limite_perfil (
  perfil_id        integer     NOT NULL
                     REFERENCES usuarios.perfil(perfil_id) ON DELETE CASCADE,
  recurso          varchar(60) NOT NULL,
  maximo_por_hora  integer     NOT NULL,
  motivo           text        NOT NULL,
  PRIMARY KEY (perfil_id, recurso),
  CONSTRAINT limite_perfil_positivo CHECK (maximo_por_hora > 0)
);

INSERT INTO configuracion.limite_perfil (perfil_id, recurso, maximo_por_hora, motivo)
SELECT p.perfil_id, v.recurso, v.maximo, v.motivo
  FROM usuarios.perfil p
  JOIN (VALUES
    ('COLABORADOR',   'consultas',     60,
     'Solo consulta lo propio: su participacion y su historial de '
     'consentimiento. Sesenta por hora cubre de sobra una sesion real.'),
    ('LIDER',         'consultas',    120,
     'Mira el tablero de su unidad y su subarbol. El tope acota el raspado '
     'sin estorbar el trabajo.'),
    ('ESPECIALISTA',  'consultas',    300,
     'Trabajo transversal sobre toda la organizacion: compara unidades y '
     'campanias, y con 120 se queda corto en una sesion de analisis.'),
    ('AUDITOR',       'consultas',    600,
     'Revisar una bitacora es, por definicion, leer muchos registros. Un '
     'tope bajo aqui no protege nada y convierte la auditoria en algo que '
     'no se puede hacer.'),
    ('ADMINISTRADOR', 'consultas',    300,
     'Administra catalogos y usuarios; no es su trabajo raspar agregados.'),
    ('ESPECIALISTA',  'exportaciones', 20,
     'Exportar es el acto por el que los datos salen. Un tope bajo es '
     'deliberado: veinte archivos en una hora ya no es trabajo de '
     'analisis.'),
    ('ADMINISTRADOR', 'exportaciones', 20,
     'Mismo motivo que para el especialista.')
  ) AS v(perfil, recurso, maximo, motivo) ON v.perfil = p.codigo
ON CONFLICT (perfil_id, recurso) DO NOTHING;

-- -------------------------------------------------------------------
-- 5. PRIVILEGIOS
-- -------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bienestar_app') THEN
    GRANT USAGE ON SCHEMA configuracion TO bienestar_app;
    -- Lectura sí; UPDATE sobre parametro_privacidad NO. El único camino
    -- para cambiar un umbral es fn_cambiar_parametro, y por ese camino
    -- siempre queda historial.
    GRANT SELECT ON configuracion.cambio_parametro,
                    configuracion.limite_parametro,
                    configuracion.limite_perfil TO bienestar_app;
    GRANT EXECUTE ON FUNCTION configuracion.fn_cambiar_parametro(
            VARCHAR, NUMERIC, TEXT, VARCHAR, VARCHAR) TO bienestar_app;
  END IF;
END $$;

-- -------------------------------------------------------------------
-- 6. CÓDIGOS DE BITÁCORA
-- -------------------------------------------------------------------
INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('PARAMETRO_CAMBIADO',
   'Se cambio un parametro de privacidad. Sensible: el umbral k y los '
   'presupuestos de epsilon son la proteccion misma.', TRUE),
  ('PARAMETRO_CONSULTADO',
   'Se leyeron los parametros vigentes y sus limites.', FALSE)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;

-- Verificación:
--   SELECT * FROM configuracion.limite_parametro ORDER BY clave;        -- 7
--   SELECT count(*) FROM configuracion.limite_perfil;                   -- 7
--   -- Debe fallar con FUERA_DE_LIMITE:
--   SELECT * FROM configuracion.fn_cambiar_parametro(
--     'k_umbral_minimo', 2, 'bajando el umbral para ver mas detalle en el
--      tablero de operaciones', 'USR-00001');
