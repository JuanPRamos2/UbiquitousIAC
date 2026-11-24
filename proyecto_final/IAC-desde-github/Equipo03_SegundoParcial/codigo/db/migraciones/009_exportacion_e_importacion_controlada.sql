-- =====================================================================
-- 009 — Egreso e ingreso controlado de agregados
--
-- QUÉ AGREGA, Y POR QUÉ NO ESTABA
-- --------------------------------
-- El sistema sabía calcular agregados protegidos y sabía mostrarlos. Lo
-- que no tenía era un registro de lo que SALE de la organización.
--
-- reports-service ya exporta un reporte en varios formatos, y eso está
-- bien para un reporte: tiene forma fija, su propio sello y queda en
-- bitácora como un reporte. Lo que no cubre es el egreso de una
-- SELECCIÓN LIBRE de agregados —las unidades y las campañas que alguien
-- elija—, y esa diferencia no es de tamaño: es de riesgo.
--
--   Un reporte tiene una forma que alguien revisó una vez.
--   Una selección libre la arma quien exporta, cada vez.
--
-- El archivo, una vez fuera, ya no tiene control alguno: quien lo recibe
-- puede sumar y restar sin pedirle nada al sistema. Un archivo con una
-- unidad padre y tres de sus cuatro hijas contiene la cuarta por resta,
-- aunque esa cuarta nunca se haya publicado. Por eso el control del
-- conjunto va ANTES de escribir el archivo, y por eso la decisión queda
-- registrada: tanto la exportación que se permitió como la que se negó.
--
-- LAS TRES DECISIONES DEL MODELO
-- -------------------------------
-- 1. GENERAR Y DESCARGAR SON DOS ACTOS, CON DOS REGISTROS.
--    Un archivo generado y nunca descargado deja rastro igual. Si solo se
--    registrara la descarga, un intento de llevarse datos que acabó
--    abandonado no habría existido nunca, y es justo el intento lo que
--    interesa ver. Y al revés: una descarga repetida de un archivo viejo
--    es una salida de datos que no se ve en el acto de generarlo.
--
-- 2. LO IMPORTADO NO SE MEZCLA CON LO CALCULADO, NUNCA.
--    Un agregado importado no pasó por la tubería de privacidad: nadie
--    le aplicó umbral k ni ruido, y su número puede venir de donde sea.
--    Si se guardara junto a los calculados, en la misma tabla, dejaría de
--    poder distinguirse un agregado protegido de uno que alguien escribió
--    a mano. La separación es física —otra tabla, con su procedencia— y no
--    una columna de bandera que una consulta puede olvidar filtrar.
--
-- 3. EL SELLO SE GUARDA, Y SE CALCULA SOBRE EL CONTENIDO.
--    Sin sello, dos archivos del mismo dato no se pueden comparar y nadie
--    puede demostrar que el que recibió es el que se generó.
-- =====================================================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS exportacion;
COMMENT ON SCHEMA exportacion IS
  'Egreso e ingreso controlado de agregados. Separado de agregado porque '
  'lo que entra por aqui NO paso por la tuberia de privacidad y no debe '
  'poder confundirse con lo calculado.';

-- -------------------------------------------------------------------
-- 1. LA SOLICITUD DE EXPORTACIÓN
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exportacion.solicitud (
  exportacion_id      varchar(40)  PRIMARY KEY,
  actor_usuario_id    varchar(20)  NOT NULL
                        REFERENCES usuarios.usuario(usuario_id),
  formato             varchar(10)  NOT NULL,
  -- La selección se guarda tal como se pidió. Sin esto no se puede
  -- reconstruir después qué contenía el archivo, y un registro de
  -- exportación que no dice qué salió no sirve para nada.
  seleccion           jsonb        NOT NULL,
  filas_publicadas    integer      NOT NULL DEFAULT 0,
  -- Las suprimidas se cuentan aparte a propósito. «Exporté 8 filas» y
  -- «exporté 8 de 12, 4 suprimidas» describen situaciones distintas, y la
  -- segunda es la que permite leer el archivo sin sacar conclusiones de
  -- más.
  filas_suprimidas    integer      NOT NULL DEFAULT 0,
  sello_sha256        char(64),
  bytes               integer,
  -- El archivo generado, en la misma fila que su registro.
  --
  -- POR QUÉ AQUÍ Y NO EN UN VOLUMEN
  -- Guardar el archivo fuera y la fila aquí abre dos huecos. Uno: el
  -- archivo puede existir sin registro —un `docker compose down -v` se
  -- lleva el volumen y deja las filas, o al revés—, y un archivo de
  -- agregados sin registro de quién lo pidió es justo lo que esta tabla
  -- vino a evitar. Dos: la descarga tiene que entregar EXACTAMENTE los
  -- bytes que se sellaron, y si se regenerara desde `seleccion`, una
  -- campaña publicada entre la generación y la descarga daría un archivo
  -- distinto con el sello viejo.
  --
  -- Son archivos de agregados: kilobytes, y vencen en horas. No es un
  -- almacén de documentos —las evidencias sí van a un volumen, porque son
  -- permanentes y pesan— sino un artefacto efímero que no debe poder
  -- separarse de su registro.
  contenido           bytea,
  estado              varchar(20)  NOT NULL DEFAULT 'GENERADA',
  motivo_rechazo      text,
  fecha_generacion    timestamptz  NOT NULL DEFAULT now(),
  -- Un archivo de agregados no debería quedar descargable para siempre.
  -- La ventana la fija el servicio a partir de gobernanza.parametro.
  vence_en            timestamptz  NOT NULL,
  CONSTRAINT solicitud_formato_check
    CHECK (formato IN ('json','xml','csv','pdf')),
  CONSTRAINT solicitud_estado_check
    CHECK (estado IN ('GENERADA','DESCARGADA','VENCIDA','RECHAZADA')),
  -- Una solicitud rechazada tiene que decir por qué. Sin el motivo, el
  -- registro dice que algo se negó y no qué, que es lo único útil.
  CONSTRAINT solicitud_rechazo_con_motivo
    CHECK (estado <> 'RECHAZADA' OR motivo_rechazo IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_solicitud_actor
  ON exportacion.solicitud (actor_usuario_id, fecha_generacion DESC);

-- Para una base que ya tenía la tabla sin la columna.
ALTER TABLE exportacion.solicitud ADD COLUMN IF NOT EXISTS contenido bytea;

-- -------------------------------------------------------------------
-- 2. LAS DESCARGAS — una fila por descarga, no una bandera
-- -------------------------------------------------------------------
-- Una columna `descargada boolean` solo guardaría la primera. La tercera
-- descarga del mismo archivo, una semana después y desde otra cuenta, es
-- una salida de datos distinta y tiene que verse como tal.
CREATE TABLE IF NOT EXISTS exportacion.descarga (
  descarga_id       bigserial    PRIMARY KEY,
  exportacion_id    varchar(40)  NOT NULL
                      REFERENCES exportacion.solicitud(exportacion_id)
                      ON DELETE CASCADE,
  actor_usuario_id  varchar(20)  NOT NULL
                      REFERENCES usuarios.usuario(usuario_id),
  fecha_descarga    timestamptz  NOT NULL DEFAULT now(),
  correlacion_id    varchar(40)
);

CREATE INDEX IF NOT EXISTS idx_descarga_exportacion
  ON exportacion.descarga (exportacion_id, fecha_descarga DESC);

-- -------------------------------------------------------------------
-- 3. LA IMPORTACIÓN — validada, con procedencia, y aparte
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exportacion.importacion (
  importacion_id    varchar(40)  PRIMARY KEY,
  actor_usuario_id  varchar(20)  NOT NULL
                      REFERENCES usuarios.usuario(usuario_id),
  formato           varchar(10)  NOT NULL,
  -- De dónde viene el archivo, en palabras de quien lo sube. Un agregado
  -- sin procedencia es un número sin dueño: dentro de seis meses nadie
  -- puede decir si salió de este sistema, de una hoja de cálculo o de una
  -- estimación.
  procedencia       varchar(180) NOT NULL,
  sello_sha256      char(64)     NOT NULL,
  filas_recibidas   integer      NOT NULL DEFAULT 0,
  filas_validas     integer      NOT NULL DEFAULT 0,
  filas_rechazadas  integer      NOT NULL DEFAULT 0,
  -- Qué falló, fila por fila. Un «no se pudo importar» sin detalle obliga
  -- a adivinar, y quien sube el archivo no tiene cómo arreglarlo.
  detalle_rechazos  jsonb        NOT NULL DEFAULT '[]'::jsonb,
  estado            varchar(20)  NOT NULL DEFAULT 'VALIDADA',
  fecha_importacion timestamptz  NOT NULL DEFAULT now(),
  CONSTRAINT importacion_formato_check CHECK (formato IN ('json','xml','csv')),
  -- VALIDADA es el estado por omisión: se revisó y NO se aplicó nada.
  -- Aplicar es un segundo acto con su propio permiso, por lo mismo que
  -- generar y descargar están separados.
  CONSTRAINT importacion_estado_check
    CHECK (estado IN ('VALIDADA','APLICADA','RECHAZADA'))
);

-- Los agregados importados, en su propia tabla. Ver la decisión 2 del
-- encabezado: la separación es física y no una bandera.
CREATE TABLE IF NOT EXISTS exportacion.agregado_externo (
  agregado_externo_id bigserial   PRIMARY KEY,
  importacion_id      varchar(40) NOT NULL
                        REFERENCES exportacion.importacion(importacion_id)
                        ON DELETE CASCADE,
  unidad_organizacional_id varchar(40) NOT NULL
                        REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
  campania_id         varchar(40) NOT NULL
                        REFERENCES catalogo.campania(campania_id),
  dimension           varchar(60) NOT NULL,
  valor               numeric(6,3),
  -- Se guarda lo que el archivo dijo sobre su propia proteccion, sin
  -- creerselo: es un dato declarado por un tercero.
  epsilon_declarado   numeric(10,4),
  n_declarado         integer,
  UNIQUE (importacion_id, unidad_organizacional_id, campania_id, dimension)
);

COMMENT ON TABLE exportacion.agregado_externo IS
  'Agregados que ENTRARON de fuera. No pasaron por el umbral k ni por el '
  'ruido de Laplace de este sistema: su valor puede venir de cualquier '
  'parte. Nunca se unen con agregado.resultado_protegido en una consulta '
  'que presente las dos cosas como el mismo tipo de dato.';

-- -------------------------------------------------------------------
-- 3bis. PRIVILEGIOS DEL ROL DE LA APLICACIÓN
-- -------------------------------------------------------------------
-- En una base nueva esto lo hace db/esquema/09_permisos.sh, que ya quedó
-- actualizado. Aquí va otra vez porque una base YA CREADA no vuelve a
-- pasar por ese script, y sin estas líneas las tablas existen pero el rol
-- de la aplicación no las ve: `information_schema.tables` filtra por
-- privilegio, así que el servicio no falla con «permiso denegado» sino con
-- «no existe la relación», que manda a buscar el problema al lugar
-- equivocado.
--
-- Sin DELETE, y eso es el punto: un registro de exportación que la propia
-- aplicación puede borrar no sirve como registro. Si alguien se lleva
-- datos y después borra la fila, no queda rastro de nada.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bienestar_app') THEN
    GRANT USAGE ON SCHEMA exportacion TO bienestar_app;
    GRANT SELECT, INSERT, UPDATE
       ON exportacion.solicitud, exportacion.importacion TO bienestar_app;
    GRANT SELECT, INSERT
       ON exportacion.descarga, exportacion.agregado_externo TO bienestar_app;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA exportacion TO bienestar_app;
  END IF;
END $$;

-- -------------------------------------------------------------------
-- 4. LOS PERMISOS
-- -------------------------------------------------------------------
-- Tres permisos y no uno, por la misma razón que proponer y aprobar una
-- intervención son distintos: generar un archivo, llevárselo y meter datos
-- de fuera son tres actos con consecuencias distintas.
INSERT INTO usuarios.permiso (codigo, descripcion) VALUES
  ('EXPORTACION_GENERAR',
   'Armar un archivo de agregados a partir de una seleccion. No incluye '
   'descargarlo.'),
  ('EXPORTACION_DESCARGAR',
   'Llevarse un archivo ya generado. Separado de generarlo porque es el '
   'acto en que los datos salen de la organizacion.'),
  ('IMPORTACION_APLICAR',
   'Dar de alta agregados que vienen de fuera. Validar un archivo no '
   'requiere este permiso; aplicarlo si.')
ON CONFLICT (codigo) DO NOTHING;

-- ESPECIALISTA: genera y descarga. Es su trabajo llevar resultados a un
-- comité. No aplica importaciones: dar de alta datos de fuera cambia lo
-- que el sistema afirma, y eso es administración.
INSERT INTO usuarios.perfil_permiso (perfil_id, permiso_id)
SELECT p.perfil_id, m.permiso_id
  FROM usuarios.perfil p, usuarios.permiso m
 WHERE p.codigo = 'ESPECIALISTA'
   AND m.codigo IN ('EXPORTACION_GENERAR','EXPORTACION_DESCARGAR')
ON CONFLICT DO NOTHING;

INSERT INTO usuarios.perfil_permiso (perfil_id, permiso_id)
SELECT p.perfil_id, m.permiso_id
  FROM usuarios.perfil p, usuarios.permiso m
 WHERE p.codigo = 'ADMINISTRADOR'
   AND m.codigo IN ('EXPORTACION_GENERAR','EXPORTACION_DESCARGAR',
                    'IMPORTACION_APLICAR')
ON CONFLICT DO NOTHING;

-- El AUDITOR no exporta. Lee la bitácora, que es otra cosa: su trabajo es
-- revisar quién se llevó qué, y darle el permiso de llevárselo lo pondría
-- a auditarse a sí mismo.

-- -------------------------------------------------------------------
-- 5. LOS CÓDIGOS DE BITÁCORA
-- -------------------------------------------------------------------
-- auditoria.bitacora tiene llave foránea contra auditoria.tipo_accion. Un
-- código que no esté aquí hace fallar la inserción, y como el registro va
-- envuelto en un try para no tumbar la operación principal, falla en
-- silencio: exactamente el defecto que la migración 007 vino a corregir.
INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('EXPORTACION_GENERADA',
   'Se armo un archivo de agregados a partir de una seleccion.', TRUE),
  ('EXPORTACION_DESCARGADA',
   'Un archivo de agregados salio de la organizacion. Una fila por '
   'descarga, no una por archivo.', TRUE),
  ('EXPORTACION_BLOQUEADA',
   'Se nego una exportacion porque el conjunto pedido permitia aislar un '
   'grupo por debajo del umbral k restando unas filas de otras.', TRUE),
  ('IMPORTACION_VALIDADA',
   'Se reviso un archivo de agregados externos contra el contrato. No se '
   'aplico nada.', TRUE),
  ('IMPORTACION_APLICADA',
   'Se dieron de alta agregados que vienen de fuera, con su procedencia.',
   TRUE)
ON CONFLICT (codigo) DO NOTHING;

-- -------------------------------------------------------------------
-- 6. LA VENTANA DE VIGENCIA, COMO PARÁMETRO
-- -------------------------------------------------------------------
-- En el código sería un número suelto que nadie puede cambiar sin volver a
-- desplegar. Aquí se discute y se ajusta, y va en la MISMA tabla que el
-- umbral k y los presupuestos de épsilon: la vigencia de un archivo de
-- agregados es una decisión de privacidad, no de configuración técnica, y
-- separarla en otra tabla la sacaría de la discusión donde pertenece.
INSERT INTO agregado.parametro_privacidad
  (clave, valor, unidad, descripcion, justificacion) VALUES
  ('exportacion_vigencia_horas', 72, 'horas',
   'Cuantas horas queda descargable un archivo de agregados ya generado.',
   'Pasado el plazo hay que volver a generarlo, y el registro nuevo deja '
   'ver que alguien volvio a pedir los mismos datos. Sin vencimiento, un '
   'enlace de descarga sigue sirviendo meses despues de que la persona '
   'que lo pidio dejo de necesitarlo, o dejo la organizacion.')
ON CONFLICT (clave) DO NOTHING;

COMMIT;

-- Verificación:
--   SELECT count(*) FROM usuarios.permiso
--    WHERE codigo LIKE 'EXPORTACION%' OR codigo = 'IMPORTACION_APLICAR';  -- 3
--   SELECT agregado.fn_parametro('exportacion_vigencia_horas');           -- 72
--   \dt exportacion.*                                                     -- 4
