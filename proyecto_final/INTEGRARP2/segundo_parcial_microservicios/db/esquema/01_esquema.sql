-- =============================================================================
-- PLATAFORMA DE BIENESTAR LABORAL Y PREVENCION DE BURNOUT
-- Equipo 03 · Base de datos PostgreSQL · v2.0
-- =============================================================================
-- CAMBIOS RESPECTO A LA VERSION ANTERIOR (retroalimentacion del profesor):
--   1. PRIVACIDAD DIFERENCIAL REAL: epsilon, presupuesto, sensibilidad,
--      clipping y mecanismo de Laplace. El umbral k por si solo NO es
--      privacidad diferencial.
--   2. Las respuestas del autoreporte viven en PostgreSQL en esta etapa.
--      MongoDB queda como analisis, no como implementacion.
--   3. Cinco perfiles (los recomendados), no siete.
--   4. Ciclo de negocio completo: CONSENTIMIENTO -> AUTOREPORTE -> PROTECCION
--      -> AGREGACION -> TENDENCIA -> RIESGO -> INTERVENCION -> SEGUIMIENTO
--      -> EVALUACION.
--   5. Modulo de intervenciones ORGANIZACIONALES (nunca sobre una persona).
--   6. Matriz de minimizacion de datos formalizada como catalogo.
--   7. Transparencia funcional almacenada en base de datos.
-- =============================================================================
-- Ejecutar sobre una base vacia:
--   CREATE DATABASE bienestar_nexum WITH ENCODING 'UTF8' TEMPLATE template0;
--   \c bienestar_nexum
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE SCHEMA IF NOT EXISTS organizacion;
CREATE SCHEMA IF NOT EXISTS usuarios;
CREATE SCHEMA IF NOT EXISTS catalogo;
CREATE SCHEMA IF NOT EXISTS consentimiento;
CREATE SCHEMA IF NOT EXISTS autoreporte;
CREATE SCHEMA IF NOT EXISTS gobernanza;
CREATE SCHEMA IF NOT EXISTS agregado;
CREATE SCHEMA IF NOT EXISTS riesgo;
CREATE SCHEMA IF NOT EXISTS intervencion;
CREATE SCHEMA IF NOT EXISTS transparencia;
CREATE SCHEMA IF NOT EXISTS auditoria;

COMMENT ON SCHEMA autoreporte IS
  'Respuestas seudonimizadas. Ninguna tabla de este esquema contiene empleado_id.';
COMMENT ON SCHEMA agregado IS
  'Agregacion protegida: umbral k + privacidad diferencial con presupuesto epsilon.';
COMMENT ON SCHEMA intervencion IS
  'Intervenciones ORGANIZACIONALES. Ninguna tabla admite un empleado objetivo.';

-- =============================================================================
-- 1. ORGANIZACION
-- =============================================================================
CREATE TABLE organizacion.unidad_organizacional (
    unidad_organizacional_id VARCHAR(40)  PRIMARY KEY,
    nombre                   VARCHAR(180) NOT NULL,
    tipo                     VARCHAR(30)  NOT NULL DEFAULT 'AREA'
                             CHECK (tipo IN ('DIRECCION','AREA','DEPARTAMENTO','TURNO','EQUIPO')),
    unidad_padre_id          VARCHAR(40)
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id)
                             ON DELETE SET NULL,
    nivel_jerarquico         SMALLINT     NOT NULL DEFAULT 0,
    plantilla_declarada      INTEGER      NOT NULL DEFAULT 0
                             CHECK (plantilla_declarada >= 0),
    activa                   BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_actualizacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_unidad_padre  ON organizacion.unidad_organizacional(unidad_padre_id);
CREATE INDEX idx_unidad_activa ON organizacion.unidad_organizacional(activa);

COMMENT ON COLUMN organizacion.unidad_organizacional.plantilla_declarada IS
  'Tamano de plantilla. Se usa para advertir cuando una unidad es demasiado pequena para publicar agregados.';

-- =============================================================================
-- 2. USUARIOS, PERFILES Y PERMISOS (RBAC dirigido por datos)
-- =============================================================================
CREATE TABLE usuarios.perfil (
    perfil_id      SERIAL       PRIMARY KEY,
    codigo         VARCHAR(30)  NOT NULL UNIQUE,
    nombre         VARCHAR(120) NOT NULL,
    descripcion    TEXT,
    activo         BOOLEAN      NOT NULL DEFAULT TRUE
);

INSERT INTO usuarios.perfil (codigo, nombre, descripcion) VALUES
 ('COLABORADOR',  'Colaborador',
  'Consulta el aviso, consiente, revoca, responde y consulta su estado de participacion.'),
 ('LIDER',        'Lider de unidad',
  'Consulta agregados protegidos, tendencias y recomendaciones de su unidad. Nunca respuestas individuales ni seudonimos.'),
 ('ESPECIALISTA', 'Especialista de bienestar',
  'Administra instrumentos, revisa agregados, gestiona el catalogo de intervenciones y propone planes. No puede identificar quien respondio que.'),
 ('AUDITOR',      'Auditor de cumplimiento',
  'Revisa bitacora y evidencia de consentimiento. No accede a respuestas crudas.'),
 ('ADMINISTRADOR','Administrador del sistema',
  'Usuarios, configuracion, parametros, roles e infraestructura. No tiene acceso funcional a respuestas individuales.');

CREATE TABLE usuarios.permiso (
    permiso_id   SERIAL      PRIMARY KEY,
    codigo       VARCHAR(60) NOT NULL UNIQUE,
    descripcion  TEXT        NOT NULL,
    sensible     BOOLEAN     NOT NULL DEFAULT FALSE
);

INSERT INTO usuarios.permiso (codigo, descripcion, sensible) VALUES
 ('AVISO_CONSULTAR',        'Consultar el aviso de privacidad vigente', FALSE),
 ('CONSENT_OTORGAR',        'Otorgar el propio consentimiento', FALSE),
 ('CONSENT_REVOCAR',        'Revocar el propio consentimiento', FALSE),
 ('CONSENT_HISTORIAL_PROPIO','Consultar el historial propio de consentimiento', FALSE),
 ('CONSENT_EVIDENCIA_AUDIT','Verificar evidencia de consentimiento sin ver respuestas', TRUE),
 ('AUTOREPORTE_RESPONDER',  'Responder el autoreporte de una campania', FALSE),
 ('PARTICIPACION_PROPIA',   'Consultar el estado propio de participacion', FALSE),
 ('AGREGADO_UNIDAD',        'Consultar agregados protegidos de su unidad', TRUE),
 ('AGREGADO_GLOBAL',        'Consultar agregados protegidos de toda la organizacion', TRUE),
 ('TENDENCIA_CONSULTAR',    'Consultar tendencias protegidas', TRUE),
 ('RECOMENDACION_CONSULTAR','Consultar recomendaciones organizacionales', FALSE),
 ('INSTRUMENTO_ADMIN',      'Administrar instrumentos, versiones y reactivos', FALSE),
 ('CAMPANIA_ADMIN',         'Crear, abrir y cerrar campanias', FALSE),
 ('INTERVENCION_PROPONER',  'Proponer planes de intervencion organizacional', FALSE),
 ('INTERVENCION_APROBAR',   'Aprobar planes de intervencion organizacional', FALSE),
 ('INTERVENCION_SEGUIMIENTO','Registrar seguimiento y evaluacion de intervenciones', FALSE),
 ('BITACORA_CONSULTAR',     'Consultar la bitacora de auditoria', TRUE),
 ('USUARIO_ADMIN',          'Administrar usuarios y asignar perfiles', TRUE),
 ('PARAMETRO_ADMIN',        'Administrar parametros del sistema (k, epsilon, presupuesto)', TRUE);

CREATE TABLE usuarios.perfil_permiso (
    perfil_id  INTEGER NOT NULL REFERENCES usuarios.perfil(perfil_id)   ON DELETE CASCADE,
    permiso_id INTEGER NOT NULL REFERENCES usuarios.permiso(permiso_id) ON DELETE CASCADE,
    PRIMARY KEY (perfil_id, permiso_id)
);

INSERT INTO usuarios.perfil_permiso (perfil_id, permiso_id)
SELECT pf.perfil_id, pm.permiso_id
FROM (VALUES
 ('COLABORADOR','AVISO_CONSULTAR'), ('COLABORADOR','CONSENT_OTORGAR'),
 ('COLABORADOR','CONSENT_REVOCAR'), ('COLABORADOR','CONSENT_HISTORIAL_PROPIO'),
 ('COLABORADOR','AUTOREPORTE_RESPONDER'), ('COLABORADOR','PARTICIPACION_PROPIA'),
 ('LIDER','AVISO_CONSULTAR'), ('LIDER','AGREGADO_UNIDAD'),
 ('LIDER','TENDENCIA_CONSULTAR'), ('LIDER','RECOMENDACION_CONSULTAR'),
 ('ESPECIALISTA','AVISO_CONSULTAR'), ('ESPECIALISTA','AGREGADO_UNIDAD'),
 ('ESPECIALISTA','AGREGADO_GLOBAL'), ('ESPECIALISTA','TENDENCIA_CONSULTAR'),
 ('ESPECIALISTA','RECOMENDACION_CONSULTAR'), ('ESPECIALISTA','INSTRUMENTO_ADMIN'),
 ('ESPECIALISTA','CAMPANIA_ADMIN'), ('ESPECIALISTA','INTERVENCION_PROPONER'),
 ('ESPECIALISTA','INTERVENCION_APROBAR'), ('ESPECIALISTA','INTERVENCION_SEGUIMIENTO'),
 ('AUDITOR','AVISO_CONSULTAR'), ('AUDITOR','BITACORA_CONSULTAR'),
 ('AUDITOR','CONSENT_EVIDENCIA_AUDIT'),
 ('ADMINISTRADOR','AVISO_CONSULTAR'), ('ADMINISTRADOR','USUARIO_ADMIN'),
 ('ADMINISTRADOR','PARAMETRO_ADMIN'), ('ADMINISTRADOR','BITACORA_CONSULTAR')
) AS v(perfil_codigo, permiso_codigo)
JOIN usuarios.perfil  pf ON pf.codigo = v.perfil_codigo
JOIN usuarios.permiso pm ON pm.codigo = v.permiso_codigo;

COMMENT ON TABLE usuarios.perfil_permiso IS
  'Matriz de perfiles y permisos. Ningun perfil recibe permiso de lectura de respuestas individuales: ese permiso no existe en el catalogo.';

CREATE TABLE usuarios.usuario (
    usuario_id          VARCHAR(20)  PRIMARY KEY,
    nombre              VARCHAR(120) NOT NULL,
    apellido_paterno    VARCHAR(120) NOT NULL,
    apellido_materno    VARCHAR(120),
    correo              VARCHAR(180) NOT NULL UNIQUE,
    contrasena_hash     TEXT         NOT NULL,
    activo              BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_actualizacion TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_ultimo_acceso TIMESTAMPTZ
);
CREATE INDEX idx_usuario_correo ON usuarios.usuario(correo);

CREATE TABLE usuarios.usuario_perfil (
    usuario_id       VARCHAR(20) NOT NULL REFERENCES usuarios.usuario(usuario_id) ON DELETE CASCADE,
    perfil_id        INTEGER     NOT NULL REFERENCES usuarios.perfil(perfil_id),
    unidad_alcance_id VARCHAR(40)
                     REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    fecha_asignacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (usuario_id, perfil_id)
);
COMMENT ON COLUMN usuarios.usuario_perfil.unidad_alcance_id IS
  'Limita el alcance del perfil a una unidad. Un lider solo consulta agregados de esta unidad y sus descendientes.';

CREATE TABLE usuarios.empleado (
    empleado_id              VARCHAR(20)  PRIMARY KEY,
    usuario_id               VARCHAR(20)  UNIQUE
                             REFERENCES usuarios.usuario(usuario_id) ON DELETE SET NULL,
    nombre                   VARCHAR(120) NOT NULL,
    apellido_paterno         VARCHAR(120) NOT NULL,
    apellido_materno         VARCHAR(120),
    fecha_ingreso            DATE         NOT NULL,
    fecha_baja               DATE,
    unidad_organizacional_id VARCHAR(40)  NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    activo                   BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_actualizacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_empleado_unidad ON usuarios.empleado(unidad_organizacional_id);

COMMENT ON TABLE usuarios.empleado IS
  'Identidad laboral. NUNCA se une con autoreporte.respuesta en una consulta que sirva a un perfil distinto del propio colaborador.';
-- =============================================================================
-- 3. CATALOGO: INSTRUMENTOS, REACTIVOS, CAMPANIAS, FUENTES AUTORIZADAS
-- =============================================================================
CREATE TABLE catalogo.dimension (
    dimension_id VARCHAR(40)  PRIMARY KEY,
    nombre       VARCHAR(120) NOT NULL,
    descripcion  TEXT,
    orden        SMALLINT     NOT NULL DEFAULT 0
);

CREATE TABLE catalogo.fuente_autorizada (
    fuente_id   VARCHAR(40)  PRIMARY KEY,
    nombre      VARCHAR(140) NOT NULL,
    descripcion TEXT         NOT NULL,
    autorizada  BOOLEAN      NOT NULL DEFAULT TRUE,
    motivo      TEXT         NOT NULL
);
COMMENT ON TABLE catalogo.fuente_autorizada IS
  'Fuentes de indicadores permitidas y explicitamente prohibidas. Una fuente con autorizada = FALSE no puede alimentar ningun indicador: convertiria la herramienta en vigilancia.';

INSERT INTO catalogo.fuente_autorizada (fuente_id, nombre, descripcion, autorizada, motivo) VALUES
 ('FA-AUTOREPORTE','Autoreporte de la persona','Respuestas voluntarias a instrumentos de bienestar.',TRUE,'Declarado y consentido por la persona.'),
 ('FA-CARGA','Carga percibida','Percepcion de carga declarada por la persona.',TRUE,'Autoreporte, no medicion encubierta.'),
 ('FA-HORAS-EXTRA','Horas extra declaradas','Horas extra registradas de forma agregada por unidad.',TRUE,'Dato organizacional, se usa agregado.'),
 ('FA-RECUPERACION','Recuperacion percibida','Percepcion de descanso y recuperacion.',TRUE,'Autoreporte.'),
 ('FA-APOYO','Apoyo del equipo','Percepcion de apoyo entre pares y liderazgo.',TRUE,'Autoreporte.'),
 ('FA-ORG','Indicador organizacional autorizado','Rotacion, ausentismo y staffing a nivel de unidad.',TRUE,'Dato de la unidad, nunca individual.'),
 ('FA-CORREO','Correo electronico','Contenido o metadatos de correo.',FALSE,'Vigilancia de comunicaciones. Prohibido.'),
 ('FA-CHAT','Mensajeria corporativa','Teams, Slack u otra mensajeria.',FALSE,'Vigilancia de comunicaciones. Prohibido.'),
 ('FA-GPS','Geolocalizacion','Ubicacion continua de la persona.',FALSE,'Vigilancia de ubicacion. Prohibido.'),
 ('FA-TECLADO','Actividad de teclado o pantalla','Pulsaciones, capturas o tiempo de actividad.',FALSE,'Vigilancia de productividad individual. Prohibido.'),
 ('FA-NAVEGACION','Navegacion y productividad individual','Historial de navegacion o metricas individuales.',FALSE,'Vigilancia individual. Prohibido.');

CREATE TABLE catalogo.instrumento (
    instrumento_id VARCHAR(40)  PRIMARY KEY,
    nombre         VARCHAR(180) NOT NULL,
    descripcion    TEXT,
    tipo           VARCHAR(30)  NOT NULL
                   CHECK (tipo IN ('NOM035','CLIMA','BREVE','PERSONALIZADO')),
    fuente_id      VARCHAR(40)  NOT NULL REFERENCES catalogo.fuente_autorizada(fuente_id),
    activo         BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE catalogo.version_instrumento (
    instrumento_id       VARCHAR(40) NOT NULL
                         REFERENCES catalogo.instrumento(instrumento_id) ON DELETE CASCADE,
    version              SMALLINT    NOT NULL,
    fecha_vigencia_desde DATE        NOT NULL,
    fecha_vigencia_hasta DATE,
    escala_min           SMALLINT    NOT NULL DEFAULT 1,
    escala_max           SMALLINT    NOT NULL DEFAULT 5,
    publicada            BOOLEAN     NOT NULL DEFAULT FALSE,
    PRIMARY KEY (instrumento_id, version),
    CHECK (escala_max > escala_min),
    CHECK (fecha_vigencia_hasta IS NULL OR fecha_vigencia_hasta >= fecha_vigencia_desde)
);
COMMENT ON COLUMN catalogo.version_instrumento.escala_min IS
  'Limite inferior de la escala. Define el rango de clipping usado por el mecanismo de privacidad diferencial.';

CREATE TABLE catalogo.reactivo (
    reactivo_id  VARCHAR(20)  PRIMARY KEY,
    texto        TEXT         NOT NULL,
    dimension_id VARCHAR(40)  NOT NULL REFERENCES catalogo.dimension(dimension_id),
    invertido    BOOLEAN      NOT NULL DEFAULT FALSE,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE catalogo.reactivo_version (
    instrumento_id VARCHAR(40) NOT NULL,
    version        SMALLINT    NOT NULL,
    reactivo_id    VARCHAR(20) NOT NULL REFERENCES catalogo.reactivo(reactivo_id) ON DELETE RESTRICT,
    orden          SMALLINT    NOT NULL,
    obligatorio    BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (instrumento_id, version, reactivo_id),
    FOREIGN KEY (instrumento_id, version)
        REFERENCES catalogo.version_instrumento(instrumento_id, version) ON DELETE CASCADE
);

CREATE TABLE catalogo.campania (
    campania_id         VARCHAR(40)  PRIMARY KEY,
    nombre              VARCHAR(180) NOT NULL,
    instrumento_id      VARCHAR(40)  NOT NULL,
    version_instrumento SMALLINT     NOT NULL,
    fecha_inicio        DATE         NOT NULL,
    fecha_fin           DATE         NOT NULL,
    estado              VARCHAR(20)  NOT NULL DEFAULT 'BORRADOR'
                        CHECK (estado IN ('BORRADOR','ABIERTA','CERRADA','CANCELADA')),
    secuencia           INTEGER      NOT NULL,
    fecha_creacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    FOREIGN KEY (instrumento_id, version_instrumento)
        REFERENCES catalogo.version_instrumento(instrumento_id, version),
    CHECK (fecha_fin >= fecha_inicio)
);
COMMENT ON COLUMN catalogo.campania.secuencia IS
  'Orden cronologico de la campania. Permite construir la tendencia longitudinal sin depender de fechas.';

CREATE TABLE catalogo.campania_unidad (
    campania_id              VARCHAR(40) NOT NULL
                             REFERENCES catalogo.campania(campania_id) ON DELETE CASCADE,
    unidad_organizacional_id VARCHAR(40) NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    PRIMARY KEY (campania_id, unidad_organizacional_id)
);

-- =============================================================================
-- 4. CONSENTIMIENTO (aviso completo, seudonimo, historial)
-- =============================================================================
CREATE TABLE consentimiento.aviso_privacidad (
    aviso_id            VARCHAR(40) PRIMARY KEY,
    version             VARCHAR(20) NOT NULL,
    fecha_vigencia      DATE        NOT NULL,
    fecha_fin_vigencia  DATE,
    vigente             BOOLEAN     NOT NULL DEFAULT FALSE,
    datos_capturados      TEXT      NOT NULL,
    finalidad             TEXT      NOT NULL,
    plazo_retencion       TEXT      NOT NULL,
    quien_accede          TEXT      NOT NULL,
    quien_no_accede       TEXT      NOT NULL,
    forma_agregacion      TEXT      NOT NULL,
    explicacion_k         TEXT      NOT NULL,
    explicacion_dp        TEXT      NOT NULL,
    consecuencias_revocar TEXT      NOT NULL,
    politica_retencion    TEXT      NOT NULL,
    canal_contacto        TEXT      NOT NULL,
    hash_documento        TEXT
);
COMMENT ON TABLE consentimiento.aviso_privacidad IS
  'Aviso de privacidad versionado. Cada campo corresponde a un elemento que la pantalla de consentimiento debe explicar de forma comprensible.';

CREATE UNIQUE INDEX uq_aviso_vigente ON consentimiento.aviso_privacidad (vigente) WHERE vigente;

CREATE TABLE consentimiento.seudonimo (
    seudonimo_id     VARCHAR(30)  PRIMARY KEY,
    empleado_id      VARCHAR(20)  NOT NULL UNIQUE
                     REFERENCES usuarios.empleado(empleado_id) ON DELETE RESTRICT,
    algoritmo        VARCHAR(40)  NOT NULL DEFAULT 'HMAC-SHA256',
    fecha_generacion TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    activo           BOOLEAN      NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE consentimiento.seudonimo IS
  'SEUDONIMIZACION, NO ANONIMIZACION. Esta tabla permite reidentificar y por eso su acceso es restringido y auditado. La documentacion y la defensa oral deben usar el termino correcto.';

CREATE TABLE consentimiento.consentimiento (
    consentimiento_id BIGSERIAL   PRIMARY KEY,
    seudonimo_id      VARCHAR(30) NOT NULL REFERENCES consentimiento.seudonimo(seudonimo_id),
    aviso_id          VARCHAR(40) NOT NULL REFERENCES consentimiento.aviso_privacidad(aviso_id),
    estado            VARCHAR(20) NOT NULL
                      CHECK (estado IN ('ACEPTADO','REVOCADO','EXPIRADO')),
    fecha_evento      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidencia_hash    TEXT,
    UNIQUE (seudonimo_id, aviso_id, fecha_evento)
);
CREATE INDEX idx_consent_seud ON consentimiento.consentimiento(seudonimo_id, fecha_evento DESC);
COMMENT ON TABLE consentimiento.consentimiento IS
  'Historial append-only. Revocar NO borra: agrega un evento REVOCADO. El estado vigente es el evento mas reciente.';

CREATE OR REPLACE VIEW consentimiento.v_estado_vigente AS
SELECT DISTINCT ON (c.seudonimo_id)
       c.seudonimo_id, c.aviso_id, c.estado, c.fecha_evento
FROM consentimiento.consentimiento c
ORDER BY c.seudonimo_id, c.fecha_evento DESC, c.consentimiento_id DESC;

-- =============================================================================
-- 5. AUTOREPORTE (respuestas seudonimizadas, en PostgreSQL en esta etapa)
-- =============================================================================
CREATE TABLE autoreporte.respuesta (
    respuesta_id             BIGSERIAL   PRIMARY KEY,
    seudonimo_id             VARCHAR(30) NOT NULL
                             REFERENCES consentimiento.seudonimo(seudonimo_id),
    campania_id              VARCHAR(40) NOT NULL
                             REFERENCES catalogo.campania(campania_id),
    unidad_organizacional_id VARCHAR(40) NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    aviso_id                 VARCHAR(40) NOT NULL
                             REFERENCES consentimiento.aviso_privacidad(aviso_id),
    fecha_respuesta          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (seudonimo_id, campania_id)
);
COMMENT ON TABLE autoreporte.respuesta IS
  'Una respuesta por seudonimo por campania. No contiene empleado_id. La unicidad implementa la regla de una sola participacion por campania.';

CREATE TABLE autoreporte.respuesta_detalle (
    respuesta_id BIGINT      NOT NULL
                 REFERENCES autoreporte.respuesta(respuesta_id) ON DELETE CASCADE,
    reactivo_id  VARCHAR(20) NOT NULL REFERENCES catalogo.reactivo(reactivo_id),
    valor        SMALLINT    NOT NULL,
    PRIMARY KEY (respuesta_id, reactivo_id)
);
CREATE INDEX idx_detalle_reactivo ON autoreporte.respuesta_detalle(reactivo_id);

-- =============================================================================
-- 6. GOBERNANZA: MATRIZ DE MINIMIZACION DE DATOS
-- =============================================================================
CREATE TABLE gobernanza.minimizacion_dato (
    dato               VARCHAR(80)  PRIMARY KEY,
    se_captura         BOOLEAN      NOT NULL,
    justificacion      TEXT         NOT NULL,
    almacenamiento     VARCHAR(60),
    retencion          VARCHAR(60),
    riesgo_asociado    TEXT
);
COMMENT ON TABLE gobernanza.minimizacion_dato IS
  'Matriz de minimizacion. Cada campo del sistema justifica su necesidad. Un dato con se_captura = FALSE esta documentado como excluido a proposito.';

INSERT INTO gobernanza.minimizacion_dato VALUES
 ('Nombre completo',       FALSE,'No es necesario para el analisis agregado.',NULL,NULL,'Identificacion directa.'),
 ('Numero de empleado',    TRUE, 'Necesario para la relacion laboral, nunca viaja al autoreporte.','PostgreSQL (usuarios.empleado)','Vigencia laboral + 12 meses','Reidentificacion si se cruza con respuestas.'),
 ('Seudonimo',             TRUE, 'Permite operar sin exponer la identidad.','PostgreSQL (consentimiento.seudonimo)','Vigencia de la campania + 24 meses','Reidentificable por diseno: acceso restringido.'),
 ('Unidad organizacional', TRUE, 'Indispensable para agregar por area y turno.','PostgreSQL','24 meses','Unidades pequenas permiten inferencia: se mitiga con k y ruido.'),
 ('Respuestas del autoreporte', TRUE,'Objeto del analisis de bienestar.','PostgreSQL (autoreporte)','24 meses','Sensible: solo se publica agregado y con ruido.'),
 ('Consentimiento y version',   TRUE,'Obligacion legal de acreditar el tratamiento.','PostgreSQL (consentimiento)','5 anos','Bajo.'),
 ('Edad exacta',           FALSE,'No aporta al analisis y eleva el riesgo de reidentificacion.',NULL,NULL,'Cuasi-identificador.'),
 ('Puesto exacto',         FALSE,'En unidades pequenas identifica a la persona.',NULL,NULL,'Cuasi-identificador.'),
 ('Antiguedad exacta',     FALSE,'Cuasi-identificador combinado con area y turno.',NULL,NULL,'Cuasi-identificador.'),
 ('Contenido de comunicaciones', FALSE,'Fuera de toda finalidad declarada.',NULL,NULL,'Vigilancia. Prohibido.'),
 ('Ubicacion geografica',  FALSE,'Fuera de toda finalidad declarada.',NULL,NULL,'Vigilancia. Prohibido.'),
 ('Actividad en equipo de computo', FALSE,'Fuera de toda finalidad declarada.',NULL,NULL,'Vigilancia. Prohibido.'),
 ('Diagnostico clinico',   FALSE,'La plataforma no es un sistema de diagnostico.',NULL,NULL,'Dato de salud. Prohibido.');
-- =============================================================================
-- 7. AGREGACION PROTEGIDA: UMBRAL k + PRIVACIDAD DIFERENCIAL
-- =============================================================================
-- Un umbral k NO es privacidad diferencial. Aqui conviven ambos controles:
--   (a) supresion por tamano de grupo  -> evita publicar grupos pequenos
--   (b) privacidad diferencial (Laplace) -> acota lo que se aprende de cualquier
--       individuo aunque el atacante repita consultas
-- =============================================================================

CREATE TABLE agregado.parametro_privacidad (
    clave          VARCHAR(60)  PRIMARY KEY,
    valor          NUMERIC      NOT NULL,
    unidad         VARCHAR(30),
    descripcion    TEXT         NOT NULL,
    justificacion  TEXT         NOT NULL,
    actualizado_por VARCHAR(20) REFERENCES usuarios.usuario(usuario_id),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO agregado.parametro_privacidad (clave, valor, unidad, descripcion, justificacion) VALUES
 ('k_umbral_minimo', 5, 'respuestas',
  'Numero minimo de respuestas para considerar publicable un agregado.',
  'Valor academico inicial. Evita publicar grupos donde la sola pertenencia identifica. No sustituye a la privacidad diferencial.'),
 ('epsilon_por_consulta', 0.2, 'epsilon',
  'Presupuesto de privacidad que consume cada consulta protegida.',
  'Valor academico inicial. A menor epsilon, mas ruido y mas privacidad. Debe justificarse en el reporte tecnico y no trasladarse a produccion sin analisis.'),
 ('presupuesto_campania', 2.0, 'epsilon',
  'Presupuesto total de privacidad por combinacion de campania y unidad.',
  'Permite aproximadamente diez consultas protegidas antes de agotarse. Al agotarse el sistema deja de publicar resultados nuevos.'),
 ('delta_objetivo', 0.000001, 'delta',
  'Parametro delta de referencia para comparacion con mecanismos gaussianos.',
  'No se usa en el mecanismo de Laplace (delta = 0). Se documenta para el analisis comparativo del reporte.');

COMMENT ON TABLE agregado.parametro_privacidad IS
  'Parametros de privacidad con su justificacion escrita. Cambiarlos exige perfil ADMINISTRADOR y queda auditado.';

-- ---------------------------------------------------------------------------
-- 7.1 Presupuesto de privacidad (composicion secuencial)
-- ---------------------------------------------------------------------------
CREATE TABLE agregado.presupuesto_privacidad (
    presupuesto_id           BIGSERIAL   PRIMARY KEY,
    campania_id              VARCHAR(40) NOT NULL REFERENCES catalogo.campania(campania_id),
    unidad_organizacional_id VARCHAR(40) NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    epsilon_total            NUMERIC(10,4) NOT NULL CHECK (epsilon_total > 0),
    epsilon_consumido        NUMERIC(10,4) NOT NULL DEFAULT 0 CHECK (epsilon_consumido >= 0),
    agotado                  BOOLEAN     NOT NULL DEFAULT FALSE,
    fecha_apertura           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (campania_id, unidad_organizacional_id),
    CHECK (epsilon_consumido <= epsilon_total)
);
COMMENT ON TABLE agregado.presupuesto_privacidad IS
  'Presupuesto acumulado por campania y unidad. Implementa composicion secuencial: los epsilon de cada consulta se suman. Agotado el presupuesto no se publican resultados nuevos.';

CREATE TABLE agregado.consulta_privada (
    consulta_id       BIGSERIAL     PRIMARY KEY,
    presupuesto_id    BIGINT        NOT NULL REFERENCES agregado.presupuesto_privacidad(presupuesto_id),
    actor_id          VARCHAR(20)   REFERENCES usuarios.usuario(usuario_id),
    epsilon_consumido NUMERIC(10,4) NOT NULL CHECK (epsilon_consumido > 0),
    sensibilidad      NUMERIC(12,6) NOT NULL,
    escala_ruido      NUMERIC(12,6) NOT NULL,
    mecanismo         VARCHAR(30)   NOT NULL DEFAULT 'LAPLACE',
    n_observaciones   INTEGER       NOT NULL,
    fecha_consulta    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE agregado.consulta_privada IS
  'Bitacora del presupuesto: cada consulta protegida registra su epsilon, sensibilidad y escala de ruido. Permite auditar el gasto de privacidad.';

-- ---------------------------------------------------------------------------
-- 7.2 Resultados protegidos publicados
-- ---------------------------------------------------------------------------
CREATE TABLE agregado.resultado_protegido (
    resultado_id             BIGSERIAL   PRIMARY KEY,
    campania_id              VARCHAR(40) NOT NULL REFERENCES catalogo.campania(campania_id),
    unidad_organizacional_id VARCHAR(40) NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    dimension_id             VARCHAR(40) REFERENCES catalogo.dimension(dimension_id),
    estado_publicacion       VARCHAR(30) NOT NULL
                             CHECK (estado_publicacion IN
                                    ('PUBLICADO','GRUPO_INSUFICIENTE','PRESUPUESTO_PRIVACIDAD_AGOTADO')),
    n_observaciones          INTEGER     NOT NULL,
    k_aplicado               INTEGER     NOT NULL,
    valor_protegido          NUMERIC(6,3),
    epsilon_aplicado         NUMERIC(10,4),
    mecanismo                VARCHAR(30),
    escala_ruido             NUMERIC(12,6),
    rango_clipping_min       SMALLINT,
    rango_clipping_max       SMALLINT,
    consulta_id              BIGINT      REFERENCES agregado.consulta_privada(consulta_id),
    fecha_calculo            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (estado_publicacion <> 'PUBLICADO' OR valor_protegido IS NOT NULL),
    CHECK (estado_publicacion <> 'PUBLICADO' OR epsilon_aplicado IS NOT NULL)
);
CREATE INDEX idx_resultado_unidad ON agregado.resultado_protegido(unidad_organizacional_id, campania_id);

COMMENT ON TABLE agregado.resultado_protegido IS
  'Unico lugar del sistema desde donde la capa organizacional lee metricas. El valor siempre trae ruido calibrado. No existe tabla de puntaje individual.';
COMMENT ON COLUMN agregado.resultado_protegido.valor_protegido IS
  'Media acotada con ruido de Laplace. NO es la media real. Nunca se almacena ni se publica la media sin ruido.';

ALTER TABLE agregado.resultado_protegido
    ADD COLUMN precision_advertencia VARCHAR(30);
COMMENT ON COLUMN agregado.resultado_protegido.precision_advertencia IS
  'PRECISION_SUFICIENTE, PRECISION_LIMITADA o RUIDO_DOMINANTE. Obliga a que quien lee el tablero sepa cuanta confianza merece el valor.';

CREATE OR REPLACE FUNCTION agregado.fn_clasificar_precision(p_escala NUMERIC)
RETURNS VARCHAR AS $$
BEGIN
    IF p_escala <= 0.30 THEN RETURN 'PRECISION_SUFICIENTE';
    ELSIF p_escala <= 0.60 THEN RETURN 'PRECISION_LIMITADA';
    ELSE RETURN 'RUIDO_DOMINANTE';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ---------------------------------------------------------------------------
-- 7.3 Mecanismo de Laplace
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION agregado.fn_ruido_laplace(p_escala NUMERIC)
RETURNS NUMERIC AS $$
DECLARE
    u NUMERIC;
BEGIN
    IF p_escala IS NULL OR p_escala <= 0 THEN
        RETURN 0;
    END IF;
    -- u uniforme en (-1/2, 1/2), evitando los extremos donde ln(0) diverge
    u := random() - 0.5;
    IF u >  0.4999999 THEN u :=  0.4999999; END IF;
    IF u < -0.4999999 THEN u := -0.4999999; END IF;
    -- inversa de la CDF de Laplace(0, escala)
    RETURN -p_escala * sign(u) * ln(1 - 2 * abs(u));
END;
$$ LANGUAGE plpgsql VOLATILE;

COMMENT ON FUNCTION agregado.fn_ruido_laplace IS
  'Muestrea Laplace(0, b) por transformada inversa. b = sensibilidad / epsilon.';

CREATE OR REPLACE FUNCTION agregado.fn_parametro(p_clave VARCHAR)
RETURNS NUMERIC AS $$
    SELECT valor FROM agregado.parametro_privacidad WHERE clave = p_clave;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- 7.4 Calculo del agregado protegido: supresion + clipping + ruido + presupuesto
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION agregado.fn_calcular_agregado_protegido(
    p_campania_id   VARCHAR,
    p_unidad_id     VARCHAR,
    p_dimension_id  VARCHAR DEFAULT NULL,
    p_actor_id      VARCHAR DEFAULT NULL
) RETURNS TABLE (
    estado          VARCHAR,
    n               INTEGER,
    valor_protegido NUMERIC,
    epsilon         NUMERIC,
    escala_ruido    NUMERIC,
    mensaje         TEXT
) AS $$
DECLARE
    v_k              INTEGER;
    v_eps_consulta   NUMERIC;
    v_eps_total      NUMERIC;
    v_n              INTEGER;
    v_lo             SMALLINT;
    v_hi             SMALLINT;
    v_media          NUMERIC;
    v_sensibilidad   NUMERIC;
    v_escala         NUMERIC;
    v_ruidosa        NUMERIC;
    v_presupuesto_id BIGINT;
    v_consumido      NUMERIC;
    v_consulta_id    BIGINT;
BEGIN
    v_k            := agregado.fn_parametro('k_umbral_minimo')::INTEGER;
    v_eps_consulta := agregado.fn_parametro('epsilon_por_consulta');
    v_eps_total    := agregado.fn_parametro('presupuesto_campania');

    -- rango de la escala del instrumento de esta campania (limites de clipping)
    SELECT vi.escala_min, vi.escala_max INTO v_lo, v_hi
    FROM catalogo.campania c
    JOIN catalogo.version_instrumento vi
      ON vi.instrumento_id = c.instrumento_id AND vi.version = c.version_instrumento
    WHERE c.campania_id = p_campania_id;

    IF v_lo IS NULL THEN
        RETURN QUERY SELECT 'CAMPANIA_INVALIDA'::VARCHAR, 0, NULL::NUMERIC, NULL::NUMERIC,
                            NULL::NUMERIC, 'La campania no existe o no tiene instrumento vigente.'::TEXT;
        RETURN;
    END IF;

    -- (a) tamano del grupo: respuestas con consentimiento vigente
    SELECT COUNT(DISTINCT r.respuesta_id) INTO v_n
    FROM autoreporte.respuesta r
    JOIN autoreporte.respuesta_detalle d ON d.respuesta_id = r.respuesta_id
    JOIN catalogo.reactivo rx            ON rx.reactivo_id = d.reactivo_id
    JOIN consentimiento.v_estado_vigente ev ON ev.seudonimo_id = r.seudonimo_id
    WHERE r.campania_id = p_campania_id
      AND r.unidad_organizacional_id = p_unidad_id
      AND ev.estado = 'ACEPTADO'
      AND (p_dimension_id IS NULL OR rx.dimension_id = p_dimension_id);

    IF v_n < v_k THEN
        INSERT INTO agregado.resultado_protegido
            (campania_id, unidad_organizacional_id, dimension_id, estado_publicacion,
             n_observaciones, k_aplicado)
        VALUES (p_campania_id, p_unidad_id, p_dimension_id, 'GRUPO_INSUFICIENTE', v_n, v_k);

        RETURN QUERY SELECT 'GRUPO_INSUFICIENTE'::VARCHAR, v_n, NULL::NUMERIC, NULL::NUMERIC,
                            NULL::NUMERIC,
                            format('El grupo tiene %s respuestas y el umbral minimo es %s. No se publica ningun valor.', v_n, v_k)::TEXT;
        RETURN;
    END IF;

    -- (b) presupuesto de privacidad para esta campania y unidad
    SELECT presupuesto_id, epsilon_consumido INTO v_presupuesto_id, v_consumido
    FROM agregado.presupuesto_privacidad
    WHERE campania_id = p_campania_id AND unidad_organizacional_id = p_unidad_id;

    -- Creacion idempotente: si dos consultas concurrentes llegan a la vez, una inserta
    -- y la otra recupera la fila existente en lugar de fallar por llave duplicada.
    IF v_presupuesto_id IS NULL THEN
        INSERT INTO agregado.presupuesto_privacidad (campania_id, unidad_organizacional_id, epsilon_total)
        VALUES (p_campania_id, p_unidad_id, v_eps_total)
        ON CONFLICT (campania_id, unidad_organizacional_id) DO UPDATE
            SET epsilon_total = agregado.presupuesto_privacidad.epsilon_total
        RETURNING presupuesto_id, epsilon_consumido INTO v_presupuesto_id, v_consumido;
    END IF;

    -- (c) media con CLIPPING al rango declarado del instrumento
    SELECT AVG(LEAST(GREATEST(d.valor, v_lo), v_hi)) INTO v_media
    FROM autoreporte.respuesta r
    JOIN autoreporte.respuesta_detalle d ON d.respuesta_id = r.respuesta_id
    JOIN catalogo.reactivo rx            ON rx.reactivo_id = d.reactivo_id
    JOIN consentimiento.v_estado_vigente ev ON ev.seudonimo_id = r.seudonimo_id
    WHERE r.campania_id = p_campania_id
      AND r.unidad_organizacional_id = p_unidad_id
      AND ev.estado = 'ACEPTADO'
      AND (p_dimension_id IS NULL OR rx.dimension_id = p_dimension_id);

    -- (d) sensibilidad de una media acotada: (hi - lo) / n
    v_sensibilidad := (v_hi - v_lo)::NUMERIC / v_n;
    v_escala       := v_sensibilidad / v_eps_consulta;

    -- (e) mecanismo de Laplace y recorte al rango valido
    v_ruidosa := v_media + agregado.fn_ruido_laplace(v_escala);
    v_ruidosa := LEAST(GREATEST(v_ruidosa, v_lo), v_hi);

    -- (f) consumo ATOMICO del presupuesto.
    -- La condicion viaja dentro del WHERE: PostgreSQL la reevalua bajo el bloqueo de fila,
    -- de modo que dos consultas concurrentes no pueden sobregirar el presupuesto.
    UPDATE agregado.presupuesto_privacidad
       SET epsilon_consumido = epsilon_consumido + v_eps_consulta,
           agotado = (epsilon_consumido + v_eps_consulta >= epsilon_total)
     WHERE presupuesto_id = v_presupuesto_id
       AND epsilon_consumido + v_eps_consulta <= epsilon_total
    RETURNING epsilon_consumido INTO v_consumido;

    IF NOT FOUND THEN
        UPDATE agregado.presupuesto_privacidad SET agotado = TRUE WHERE presupuesto_id = v_presupuesto_id;
        INSERT INTO agregado.resultado_protegido
            (campania_id, unidad_organizacional_id, dimension_id, estado_publicacion,
             n_observaciones, k_aplicado)
        VALUES (p_campania_id, p_unidad_id, p_dimension_id, 'PRESUPUESTO_PRIVACIDAD_AGOTADO', v_n, v_k);
        RETURN QUERY SELECT 'PRESUPUESTO_PRIVACIDAD_AGOTADO'::VARCHAR, v_n, NULL::NUMERIC,
                            NULL::NUMERIC, NULL::NUMERIC,
                            format('El presupuesto de privacidad de esta unidad se agoto (limite %s epsilon). No se generan resultados nuevos.', v_eps_total)::TEXT;
        RETURN;
    END IF;

    INSERT INTO agregado.consulta_privada
        (presupuesto_id, actor_id, epsilon_consumido, sensibilidad, escala_ruido, n_observaciones)
    VALUES (v_presupuesto_id, p_actor_id, v_eps_consulta, v_sensibilidad, v_escala, v_n)
    RETURNING consulta_id INTO v_consulta_id;

    INSERT INTO agregado.resultado_protegido
        (campania_id, unidad_organizacional_id, dimension_id, estado_publicacion,
         n_observaciones, k_aplicado, valor_protegido, epsilon_aplicado, mecanismo,
         escala_ruido, rango_clipping_min, rango_clipping_max, consulta_id,
         precision_advertencia)
    VALUES (p_campania_id, p_unidad_id, p_dimension_id, 'PUBLICADO', v_n, v_k,
            ROUND(v_ruidosa, 3), v_eps_consulta, 'LAPLACE', v_escala, v_lo, v_hi, v_consulta_id,
            agregado.fn_clasificar_precision(v_escala));

    RETURN QUERY SELECT 'PUBLICADO'::VARCHAR, v_n, ROUND(v_ruidosa,3), v_eps_consulta, ROUND(v_escala,6),
                        format('Valor protegido con ruido de Laplace. Precision: %s (error esperado %s puntos).',
                               agregado.fn_clasificar_precision(v_escala), ROUND(v_escala,2))::TEXT;
END;
$$ LANGUAGE plpgsql VOLATILE;

COMMENT ON FUNCTION agregado.fn_calcular_agregado_protegido IS
  'Flujo completo: validacion -> clipping -> verificacion n >= k -> calculo -> sensibilidad -> mecanismo de privacidad diferencial -> publicacion protegida. Nunca devuelve la media real.';
-- =============================================================================
-- 8. TENDENCIAS (evolucion longitudinal protegida)
-- =============================================================================
CREATE OR REPLACE VIEW agregado.v_tendencia AS
SELECT rp.unidad_organizacional_id,
       uo.nombre                AS unidad_nombre,
       rp.dimension_id,
       c.secuencia,
       c.campania_id,
       c.nombre                 AS campania_nombre,
       rp.valor_protegido,
       rp.n_observaciones,
       rp.escala_ruido,
       rp.valor_protegido - LAG(rp.valor_protegido) OVER (
            PARTITION BY rp.unidad_organizacional_id, COALESCE(rp.dimension_id,'__global__')
            ORDER BY c.secuencia) AS variacion_absoluta,
       CASE WHEN ABS(COALESCE(rp.valor_protegido - LAG(rp.valor_protegido) OVER (
                 PARTITION BY rp.unidad_organizacional_id, COALESCE(rp.dimension_id,'__global__')
                 ORDER BY c.secuencia),0)) > rp.escala_ruido
            THEN 'VARIACION_INTERPRETABLE'
            ELSE 'DENTRO_DEL_RUIDO' END AS lectura
FROM agregado.resultado_protegido rp
JOIN catalogo.campania c  ON c.campania_id = rp.campania_id
JOIN organizacion.unidad_organizacional uo
                          ON uo.unidad_organizacional_id = rp.unidad_organizacional_id
WHERE rp.estado_publicacion = 'PUBLICADO';

COMMENT ON VIEW agregado.v_tendencia IS
  'Serie longitudinal de resultados publicados. La columna lectura advierte si la variacion entre dos campanias supera la escala del ruido: si no la supera, la diferencia NO debe interpretarse como una mejora o un deterioro real.';

-- =============================================================================
-- 9. REGLAS DE RIESGO ORGANIZACIONAL (motor transparente y auditable)
-- =============================================================================
CREATE TABLE riesgo.regla (
    regla_id          VARCHAR(30)  PRIMARY KEY,
    nombre            VARCHAR(160) NOT NULL,
    condicion_legible TEXT         NOT NULL,
    dimension_id      VARCHAR(40)  REFERENCES catalogo.dimension(dimension_id),
    umbral_valor      NUMERIC(6,3),
    comparador        VARCHAR(10)  CHECK (comparador IN ('<','<=','>','>=')),
    campanias_consecutivas SMALLINT NOT NULL DEFAULT 1,
    nivel             VARCHAR(20)  NOT NULL CHECK (nivel IN ('INFORMATIVO','ATENCION','PRIORITARIO')),
    activa            BOOLEAN      NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE riesgo.regla IS
  'Motor de reglas explicito. Se prefiere sobre un modelo opaco porque cada deteccion debe poder explicarse y auditarse.';

CREATE TABLE riesgo.deteccion (
    deteccion_id             BIGSERIAL   PRIMARY KEY,
    regla_id                 VARCHAR(30) NOT NULL REFERENCES riesgo.regla(regla_id),
    unidad_organizacional_id VARCHAR(40) NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    campania_id              VARCHAR(40) NOT NULL REFERENCES catalogo.campania(campania_id),
    valor_observado          NUMERIC(6,3) NOT NULL,
    explicacion              TEXT        NOT NULL,
    fecha_deteccion          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (regla_id, unidad_organizacional_id, campania_id)
);
COMMENT ON COLUMN riesgo.deteccion.explicacion IS
  'Texto legible que indica por que se disparo la regla. La trazabilidad es obligatoria: ninguna recomendacion aparece sin explicacion.';

CREATE TABLE riesgo.regla_recomendacion (
    regla_id       VARCHAR(30) NOT NULL REFERENCES riesgo.regla(regla_id) ON DELETE CASCADE,
    tipo_intervencion VARCHAR(40) NOT NULL,
    orden          SMALLINT    NOT NULL DEFAULT 1,
    PRIMARY KEY (regla_id, tipo_intervencion)
);

-- =============================================================================
-- 10. INTERVENCIONES ORGANIZACIONALES
-- =============================================================================
CREATE TABLE intervencion.tipo_intervencion (
    tipo_intervencion VARCHAR(40)  PRIMARY KEY,
    nombre            VARCHAR(160) NOT NULL,
    descripcion       TEXT         NOT NULL,
    ambito            VARCHAR(20)  NOT NULL DEFAULT 'ORGANIZACIONAL'
                      CHECK (ambito = 'ORGANIZACIONAL')
);
COMMENT ON TABLE intervencion.tipo_intervencion IS
  'Catalogo de intervenciones. El CHECK de ambito impide por construccion registrar una intervencion dirigida a una persona.';

INSERT INTO intervencion.tipo_intervencion (tipo_intervencion, nombre, descripcion) VALUES
 ('REDISTRIBUCION_CARGA','Redistribucion temporal de carga','Reasignar volumen de trabajo entre equipos durante un periodo definido.'),
 ('REVISION_TURNOS','Revision de turnos','Analizar rotacion, duracion y secuencia de turnos de la unidad.'),
 ('PAUSAS_ESTRUCTURADAS','Pausas estructuradas','Instaurar pausas programadas dentro de la jornada.'),
 ('REDUCCION_HORAS_EXTRA','Reduccion de horas extra','Acotar las horas extra de la unidad en el periodo.'),
 ('REVISION_STAFFING','Revision de staffing','Evaluar si la plantilla de la unidad es suficiente para la demanda.'),
 ('CAPACITACION_LIDERAZGO','Capacitacion de liderazgo','Formacion para mandos de la unidad en apoyo y comunicacion.'),
 ('MEJORA_AUTONOMIA','Mejora de autonomia','Ampliar el margen de decision del equipo sobre su propio trabajo.'),
 ('REVISION_CARGA_ADMIN','Revision de cargas administrativas','Eliminar o simplificar tareas administrativas de bajo valor.'),
 ('ACCIONES_RECUPERACION','Acciones de recuperacion','Medidas orientadas al descanso efectivo del equipo.'),
 ('RECURSOS_COLECTIVOS','Recursos colectivos de bienestar','Recursos de apoyo disponibles para toda la unidad.');

CREATE TABLE intervencion.plan (
    intervencion_id          BIGSERIAL    PRIMARY KEY,
    unidad_organizacional_id VARCHAR(40)  NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    tipo_intervencion        VARCHAR(40)  NOT NULL
                             REFERENCES intervencion.tipo_intervencion(tipo_intervencion),
    deteccion_id             BIGINT       REFERENCES riesgo.deteccion(deteccion_id),
    justificacion            TEXT         NOT NULL,
    resultado_esperado       TEXT         NOT NULL,
    fecha_inicio             DATE,
    fecha_fin                DATE,
    responsable_usuario_id   VARCHAR(20)  REFERENCES usuarios.usuario(usuario_id),
    estado                   VARCHAR(20)  NOT NULL DEFAULT 'PROPUESTA'
                             CHECK (estado IN ('PROPUESTA','APROBADA','EN_EJECUCION','FINALIZADA','CANCELADA')),
    campania_linea_base      VARCHAR(40)  REFERENCES catalogo.campania(campania_id),
    fecha_creacion           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
);
COMMENT ON TABLE intervencion.plan IS
  'Plan de intervencion ORGANIZACIONAL. No existe columna de empleado objetivo: la intervencion actua sobre el entorno de trabajo, nunca sobre una persona senalada.';

CREATE TABLE intervencion.seguimiento (
    seguimiento_id   BIGSERIAL   PRIMARY KEY,
    intervencion_id  BIGINT      NOT NULL REFERENCES intervencion.plan(intervencion_id) ON DELETE CASCADE,
    fecha_registro   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    estado_reportado VARCHAR(20) NOT NULL,
    avance_nota      TEXT        NOT NULL,
    registrado_por   VARCHAR(20) REFERENCES usuarios.usuario(usuario_id)
);

CREATE TABLE intervencion.evaluacion (
    evaluacion_id        BIGSERIAL    PRIMARY KEY,
    intervencion_id      BIGINT       NOT NULL UNIQUE
                         REFERENCES intervencion.plan(intervencion_id) ON DELETE CASCADE,
    campania_antes       VARCHAR(40)  NOT NULL REFERENCES catalogo.campania(campania_id),
    campania_despues     VARCHAR(40)  NOT NULL REFERENCES catalogo.campania(campania_id),
    valor_antes          NUMERIC(6,3) NOT NULL,
    valor_despues        NUMERIC(6,3) NOT NULL,
    variacion            NUMERIC(6,3) GENERATED ALWAYS AS (valor_despues - valor_antes) STORED,
    conclusion           VARCHAR(20)  NOT NULL
                         CHECK (conclusion IN ('MEJORA','SIN_CAMBIO','DETERIORO','NO_CONCLUYENTE')),
    nota_metodologica    TEXT         NOT NULL,
    fecha_evaluacion     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON COLUMN intervencion.evaluacion.nota_metodologica IS
  'Los valores comparados llevan ruido de privacidad diferencial. Una variacion menor que la escala del ruido no es concluyente y asi debe reportarse.';

-- =============================================================================
-- 11. TRANSPARENCIA FUNCIONAL
-- =============================================================================
CREATE TABLE transparencia.seccion (
    seccion_id  VARCHAR(40)  PRIMARY KEY,
    orden       SMALLINT     NOT NULL,
    titulo      VARCHAR(160) NOT NULL,
    contenido   TEXT         NOT NULL,
    publicada   BOOLEAN      NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE transparencia.seccion IS
  'Contenido de la seccion Como protegemos tus datos. Vive en base de datos para que la transparencia sea funcional dentro del sistema y no solo un anexo del documento tecnico.';

INSERT INTO transparencia.seccion (seccion_id, orden, titulo, contenido) VALUES
 ('TR-01',1,'Participacion voluntaria','Responder es voluntario. No participar no tiene ninguna consecuencia laboral y ningun mando puede saber quien participo y quien no.'),
 ('TR-02',2,'Datos que recolectamos','Tus respuestas al instrumento, la unidad a la que perteneces, la fecha y la version del aviso que aceptaste.'),
 ('TR-03',3,'Datos que NO recolectamos','No recolectamos el contenido de tus comunicaciones, tu ubicacion, tu actividad en la computadora, tu edad exacta, tu puesto exacto ni ningun diagnostico clinico.'),
 ('TR-04',4,'Seudonimizacion','Tus respuestas se guardan con un seudonimo, no con tu nombre ni con tu numero de empleado.'),
 ('TR-05',5,'Separacion de identidad','La correspondencia entre tu identidad y tu seudonimo vive en una tabla aparte, de acceso restringido y auditado. Esto es seudonimizacion, no anonimizacion: te lo decimos con precision.'),
 ('TR-06',6,'Umbral minimo de grupo','Ningun resultado se muestra si el grupo tiene menos de cinco respuestas. Si tu equipo es pequeno, el sistema responde que el grupo es insuficiente y no publica nada.'),
 ('TR-07',7,'Privacidad diferencial','A cada resultado publicado se le suma ruido matematico calibrado. Esto acota lo que alguien podria deducir sobre ti aunque repita muchas consultas. Cada consulta consume un presupuesto de privacidad y, cuando se agota, el sistema deja de publicar resultados nuevos.'),
 ('TR-08',8,'Quien puede consultar resultados','Tu lider, el especialista de bienestar y la direccion pueden consultar resultados de grupo, siempre protegidos.'),
 ('TR-09',9,'Quien NO puede consultar','Nadie puede consultar tus respuestas individuales. No existe un puntaje individual de burnout visible para la organizacion.'),
 ('TR-10',10,'Revocacion','Puedes revocar tu consentimiento cuando quieras. Dejaras de recibir encuestas. Tus respuestas anteriores no se borran, pero no se recolectan nuevas.'),
 ('TR-11',11,'Retencion','Las respuestas se conservan veinticuatro meses. La evidencia de consentimiento se conserva cinco anos por obligacion legal.'),
 ('TR-12',12,'Auditoria','Cada acceso a informacion queda registrado. Puedes consultar quien ha accedido a informacion relacionada contigo.');

-- =============================================================================
-- 12. AUDITORIA
-- =============================================================================
CREATE TABLE auditoria.tipo_accion (
    codigo      VARCHAR(60) PRIMARY KEY,
    descripcion TEXT        NOT NULL,
    sensible    BOOLEAN     NOT NULL DEFAULT TRUE
);
INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
 ('LOGIN_EXITOSO','Inicio de sesion correcto',FALSE),
 ('LOGIN_FALLIDO','Intento de inicio de sesion fallido',TRUE),
 ('LOGOUT','Cierre de sesion',FALSE),
 ('AVISO_CONSULTADO','Consulta del aviso de privacidad',FALSE),
 ('CONSENT_OTORGADO','Otorgamiento de consentimiento',TRUE),
 ('CONSENT_REVOCADO','Revocacion de consentimiento',TRUE),
 ('CONSENT_VERIFICADO','Verificacion de evidencia de consentimiento por auditoria',TRUE),
 ('AUTOREPORTE_ENVIADO','Envio de respuestas de autoreporte',TRUE),
 ('AGREGADO_CONSULTADO','Consulta de agregado protegido',TRUE),
 ('PRESUPUESTO_AGOTADO','Consulta rechazada por presupuesto de privacidad agotado',TRUE),
 ('GRUPO_INSUFICIENTE','Consulta suprimida por no alcanzar el umbral k',TRUE),
 ('TENDENCIA_CONSULTADA','Consulta de tendencia protegida',TRUE),
 ('INTERVENCION_PROPUESTA','Propuesta de intervencion organizacional',FALSE),
 ('INTERVENCION_APROBADA','Aprobacion de intervencion organizacional',FALSE),
 ('INTERVENCION_EVALUADA','Evaluacion de resultados de una intervencion',FALSE),
 ('PARAMETRO_MODIFICADO','Modificacion de un parametro de privacidad',TRUE),
 ('PERFIL_MODIFICADO','Cambio de perfil de un usuario',TRUE),
 ('BITACORA_CONSULTADA','Consulta de la bitacora de auditoria',TRUE);

CREATE TABLE auditoria.resultado (
    codigo      VARCHAR(40) PRIMARY KEY,
    descripcion TEXT
);
INSERT INTO auditoria.resultado VALUES
 ('EXITO','Operacion completada'),
 ('RECHAZADO','Operacion rechazada por falta de permisos'),
 ('GRUPO_INSUFICIENTE','Operacion suprimida por no alcanzar el umbral minimo'),
 ('PRESUPUESTO_AGOTADO','Operacion rechazada por presupuesto de privacidad agotado'),
 ('ERROR_TECNICO','Error tecnico durante la operacion');

CREATE TABLE auditoria.bitacora (
    bitacora_id      BIGSERIAL   PRIMARY KEY,
    actor_usuario_id VARCHAR(20) REFERENCES usuarios.usuario(usuario_id),
    actor_perfil     VARCHAR(30) NOT NULL,
    accion           VARCHAR(60) NOT NULL REFERENCES auditoria.tipo_accion(codigo),
    tipo_recurso     VARCHAR(40),
    recurso_id       VARCHAR(80),
    resultado        VARCHAR(40) NOT NULL REFERENCES auditoria.resultado(codigo),
    correlacion_id   VARCHAR(60) NOT NULL,
    direccion_origen INET,
    fecha_hora       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_bitacora_fecha ON auditoria.bitacora(fecha_hora DESC);
CREATE INDEX idx_bitacora_actor ON auditoria.bitacora(actor_usuario_id, accion);

COMMENT ON TABLE auditoria.bitacora IS
  'Registro de accesos. Nunca almacena el contenido de una respuesta. El campo recurso_id guarda un seudonimo solo cuando la accion es de consentimiento y el consultante tiene permiso de verificacion.';
-- =============================================================================
-- 15. ANALISIS DE UTILIDAD: justificacion de epsilon (no elegido arbitrariamente)
-- =============================================================================
-- El error absoluto esperado del mecanismo de Laplace es igual a su escala:
--     E[|ruido|] = b = sensibilidad / epsilon = (hi - lo) / (n * epsilon)
-- De aqui se desprende la condicion de utilidad:
--     n * epsilon >= (hi - lo) / error_tolerado
-- Con escala 1..5 y un error tolerado de 0.30 puntos:  n * epsilon >= 13.3
-- =============================================================================

CREATE OR REPLACE FUNCTION agregado.fn_analisis_utilidad(
    p_n INTEGER, p_epsilon NUMERIC, p_lo SMALLINT DEFAULT 1, p_hi SMALLINT DEFAULT 5
) RETURNS TABLE (
    n INTEGER, epsilon NUMERIC, sensibilidad NUMERIC, escala_ruido NUMERIC,
    error_esperado NUMERIC, utilizable BOOLEAN, comentario TEXT
) AS $$
DECLARE
    v_sens NUMERIC; v_b NUMERIC;
BEGIN
    v_sens := (p_hi - p_lo)::NUMERIC / GREATEST(p_n,1);
    v_b    := v_sens / p_epsilon;
    RETURN QUERY SELECT
        p_n, p_epsilon, ROUND(v_sens,4), ROUND(v_b,4), ROUND(v_b,4),
        (v_b <= 0.30),
        CASE WHEN v_b <= 0.30
             THEN 'El ruido es menor que el error tolerado: el resultado conserva utilidad.'
             WHEN v_b <= 0.60
             THEN 'Ruido moderado. La tendencia sigue siendo legible pero un valor puntual no es confiable.'
             ELSE 'El ruido supera al dato. Publicar este valor seria enganoso: conviene agregar mas personas o subir epsilon.'
        END::TEXT;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION agregado.fn_analisis_utilidad IS
  'Sustenta la eleccion de epsilon con un criterio explicito en lugar de un valor arbitrario. Se usa en el reporte tecnico para justificar la parametrizacion.';

-- ---------------------------------------------------------------------------
-- Reparametrizacion justificada
-- ---------------------------------------------------------------------------
-- epsilon = 0.2 por consulta exige n * 0.2 >= 13.3, es decir n >= 67 personas.
-- Ninguna unidad del caso de estudio alcanza ese tamano, de modo que ese valor
-- publicaria ruido puro. Se adopta epsilon = 1.0 por consulta, que exige n >= 14,
-- y se documenta 0.2 como alternativa mas estricta para unidades grandes.
UPDATE agregado.parametro_privacidad
   SET valor = 1.0,
       justificacion = 'Elegido con el criterio n*epsilon >= (hi-lo)/error_tolerado. Con escala 1..5 y error tolerado 0.30, epsilon = 1.0 exige n >= 14. Un epsilon de 0.2 seria mas protector pero exigiria n >= 67, tamano que ninguna unidad del caso alcanza, por lo que publicaria ruido puro. La eleccion prioriza que el dato publicado sea interpretable sin dejar de acotar la fuga de informacion.'
 WHERE clave = 'epsilon_por_consulta';

UPDATE agregado.parametro_privacidad
   SET valor = 8.0,
       justificacion = 'La composicion secuencial suma el epsilon de cada consulta. Un tablero completo requiere seis consultas por campania y unidad: el indice global mas cinco dimensiones. Se asignan 8.0 para cubrir esas seis y dejar margen a dos reconsultas. Agotado el presupuesto, el sistema deja de publicar resultados nuevos de esa campania y unidad.'
 WHERE clave = 'presupuesto_campania';

INSERT INTO agregado.parametro_privacidad (clave, valor, unidad, descripcion, justificacion) VALUES
 ('error_tolerado', 0.30, 'puntos',
  'Error absoluto maximo aceptable en una media publicada dentro de la escala del instrumento.',
  'Media escala de respuesta. Por debajo de este valor la diferencia entre dos campanias sigue siendo interpretable como tendencia.'),
 ('n_minimo_utilidad', 14, 'respuestas',
  'Tamano de grupo a partir del cual el resultado conserva utilidad con el epsilon vigente.',
  'Resultado de despejar n en n*epsilon >= (hi-lo)/error_tolerado con epsilon = 1.0. Por debajo de este valor el sistema publica pero advierte baja precision.');

-- ---------------------------------------------------------------------------
-- La publicacion ahora declara su precision
-- ---------------------------------------------------------------------------
-- =============================================================================
-- 16. MOTOR DE DETECCION DE RIESGO ORGANIZACIONAL
-- =============================================================================
CREATE OR REPLACE FUNCTION riesgo.fn_evaluar_unidad(
    p_unidad_id   VARCHAR,
    p_campania_id VARCHAR
) RETURNS TABLE (
    regla_id VARCHAR, nivel VARCHAR, valor_observado NUMERIC, explicacion TEXT
) AS $$
DECLARE
    r            RECORD;
    v_valor      NUMERIC;
    v_consec     INTEGER;
    v_explica    TEXT;
BEGIN
    FOR r IN SELECT * FROM riesgo.regla WHERE activa ORDER BY regla_id LOOP

        -- valor protegido mas reciente de la dimension evaluada
        SELECT rp.valor_protegido INTO v_valor
        FROM agregado.resultado_protegido rp
        WHERE rp.unidad_organizacional_id = p_unidad_id
          AND rp.campania_id = p_campania_id
          AND rp.estado_publicacion = 'PUBLICADO'
          AND (r.dimension_id IS NULL OR rp.dimension_id = r.dimension_id)
          AND (r.dimension_id IS NOT NULL OR rp.dimension_id IS NULL)
        ORDER BY rp.fecha_calculo DESC LIMIT 1;

        IF v_valor IS NULL THEN CONTINUE; END IF;

        -- regla de deterioro sostenido: compara la serie protegida
        IF r.umbral_valor IS NULL THEN
            SELECT COUNT(*) INTO v_consec
            FROM (SELECT variacion_absoluta
                  FROM agregado.v_tendencia
                  WHERE unidad_organizacional_id = p_unidad_id
                    AND dimension_id IS NULL
                  ORDER BY secuencia DESC LIMIT r.campanias_consecutivas) t
            WHERE t.variacion_absoluta < 0;

            IF v_consec >= r.campanias_consecutivas THEN
                v_explica := format('El indice global protegido descendio en las ultimas %s campanias consecutivas. Ultimo valor protegido: %s.',
                                    r.campanias_consecutivas, v_valor);
                INSERT INTO riesgo.deteccion (regla_id, unidad_organizacional_id, campania_id, valor_observado, explicacion)
                VALUES (r.regla_id, p_unidad_id, p_campania_id, v_valor, v_explica)
                ON CONFLICT DO NOTHING;
                RETURN QUERY SELECT r.regla_id, r.nivel, v_valor, v_explica;
            END IF;
            CONTINUE;
        END IF;

        -- reglas de umbral sobre una dimension
        IF (r.comparador = '<=' AND v_valor <= r.umbral_valor)
        OR (r.comparador = '<'  AND v_valor <  r.umbral_valor)
        OR (r.comparador = '>=' AND v_valor >= r.umbral_valor)
        OR (r.comparador = '>'  AND v_valor >  r.umbral_valor) THEN
            v_explica := format('%s: valor protegido %s %s umbral %s en la campania %s.',
                                r.nombre, v_valor, r.comparador, r.umbral_valor, p_campania_id);
            INSERT INTO riesgo.deteccion (regla_id, unidad_organizacional_id, campania_id, valor_observado, explicacion)
            VALUES (r.regla_id, p_unidad_id, p_campania_id, v_valor, v_explica)
            ON CONFLICT DO NOTHING;
            RETURN QUERY SELECT r.regla_id, r.nivel, v_valor, v_explica;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql VOLATILE;

COMMENT ON FUNCTION riesgo.fn_evaluar_unidad IS
  'Motor de reglas transparente. Solo lee resultados PUBLICADOS, es decir valores que ya pasaron el umbral k y el mecanismo de privacidad diferencial. Nunca lee respuestas crudas.';

-- Recomendaciones derivadas de las detecciones (nunca dirigidas a una persona)
CREATE OR REPLACE VIEW riesgo.v_recomendaciones AS
SELECT d.deteccion_id,
       d.unidad_organizacional_id,
       uo.nombre                AS unidad,
       d.campania_id,
       d.regla_id,
       rg.nivel,
       d.explicacion,
       rr.orden,
       ti.tipo_intervencion,
       ti.nombre                AS intervencion_sugerida,
       ti.descripcion
FROM riesgo.deteccion d
JOIN riesgo.regla rg               ON rg.regla_id = d.regla_id
JOIN riesgo.regla_recomendacion rr ON rr.regla_id = d.regla_id
JOIN intervencion.tipo_intervencion ti ON ti.tipo_intervencion = rr.tipo_intervencion
JOIN organizacion.unidad_organizacional uo ON uo.unidad_organizacional_id = d.unidad_organizacional_id
ORDER BY d.deteccion_id, rr.orden;

COMMENT ON VIEW riesgo.v_recomendaciones IS
  'Recomendaciones organizacionales con su explicacion. Toda recomendacion actua sobre el entorno de trabajo, nunca sobre una persona identificada.';

-- =============================================================================
-- 17. GARANTIAS ESTRUCTURALES (lo que el modelo hace imposible)
-- =============================================================================
-- G1: no existe ninguna columna que asocie una intervencion a una persona
CREATE OR REPLACE FUNCTION gobernanza.fn_verificar_garantias()
RETURNS TABLE (garantia TEXT, cumple BOOLEAN, detalle TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT 'G1 Intervenciones sin persona objetivo'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='intervencion'
                         AND (column_name ILIKE '%empleado%' OR column_name ILIKE '%seudonimo%')),
           'Ninguna tabla del esquema intervencion admite un empleado o seudonimo objetivo.'::TEXT;

    RETURN QUERY
    SELECT 'G2 Autoreporte sin identidad'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='autoreporte' AND column_name ILIKE '%empleado%'),
           'Ninguna tabla de autoreporte contiene empleado_id: solo seudonimo.'::TEXT;

    RETURN QUERY
    SELECT 'G3 Sin puntaje individual publicable'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema IN ('riesgo','agregado')
                         AND (column_name ILIKE '%seudonimo%' OR column_name ILIKE '%empleado%')),
           'Los esquemas de riesgo y agregacion no pueden referirse a una persona: operan solo sobre unidades.'::TEXT;

    RETURN QUERY
    SELECT 'G4 Toda publicacion lleva epsilon'::TEXT,
           NOT EXISTS (SELECT 1 FROM agregado.resultado_protegido
                       WHERE estado_publicacion='PUBLICADO' AND epsilon_aplicado IS NULL),
           'Ningun resultado publicado carece de mecanismo de privacidad diferencial aplicado.'::TEXT;

    RETURN QUERY
    SELECT 'G5 Toda publicacion respeta el umbral k'::TEXT,
           NOT EXISTS (SELECT 1 FROM agregado.resultado_protegido
                       WHERE estado_publicacion='PUBLICADO' AND n_observaciones < k_aplicado),
           'Ningun resultado publicado proviene de un grupo menor que k.'::TEXT;

    RETURN QUERY
    SELECT 'G6 Fuentes de vigilancia bloqueadas'::TEXT,
           NOT EXISTS (SELECT 1 FROM catalogo.instrumento i
                       JOIN catalogo.fuente_autorizada f ON f.fuente_id=i.fuente_id
                       WHERE NOT f.autorizada),
           'Ningun instrumento se alimenta de una fuente marcada como no autorizada.'::TEXT;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION gobernanza.fn_verificar_garantias IS
  'Verifica contra el catalogo del sistema que las garantias de privacidad se sostienen a nivel de modelo y no solo de interfaz. Se ejecuta durante la demostracion.';
-- =============================================================================
-- 13. DATOS DE PRUEBA (sinteticos, caso Nexum Servicios Corporativos)
-- =============================================================================
INSERT INTO organizacion.unidad_organizacional
   (unidad_organizacional_id, nombre, tipo, nivel_jerarquico, plantilla_declarada) VALUES
 ('UO-OPERACIONES','Operaciones','DIRECCION',0,120),
 ('UO-CC-TURNO-A','Call Center - Turno A','TURNO',1,24),
 ('UO-CC-TURNO-B','Call Center - Turno B','TURNO',1,9),
 ('UO-LOG-TURNO-A','Logistica - Turno A','TURNO',1,3);
UPDATE organizacion.unidad_organizacional SET unidad_padre_id='UO-OPERACIONES'
 WHERE unidad_organizacional_id LIKE 'UO-CC-%' OR unidad_organizacional_id LIKE 'UO-LOG-%';

INSERT INTO catalogo.dimension (dimension_id, nombre, descripcion, orden) VALUES
 ('DIM-CARGA','Carga percibida','Percepcion de volumen y ritmo de trabajo.',1),
 ('DIM-RECUP','Recuperacion','Posibilidad de descanso y desconexion.',2),
 ('DIM-APOYO','Apoyo del equipo','Soporte percibido de pares y liderazgo.',3),
 ('DIM-AUTON','Autonomia','Margen de decision sobre el propio trabajo.',4),
 ('DIM-CLARID','Claridad de rol','Claridad sobre responsabilidades y expectativas.',5);

INSERT INTO catalogo.instrumento (instrumento_id, nombre, tipo, fuente_id) VALUES
 ('INST-BIENESTAR','Instrumento breve de bienestar laboral','NOM035','FA-AUTOREPORTE');

INSERT INTO catalogo.version_instrumento
   (instrumento_id, version, fecha_vigencia_desde, escala_min, escala_max, publicada) VALUES
 ('INST-BIENESTAR',1,'2026-01-01',1,5,TRUE);

INSERT INTO catalogo.reactivo (reactivo_id, texto, dimension_id, invertido) VALUES
 ('R-01','Mi carga de trabajo es manejable en mi jornada habitual.','DIM-CARGA',FALSE),
 ('R-02','Puedo desconectarme del trabajo al terminar mi turno.','DIM-RECUP',FALSE),
 ('R-03','Recibo apoyo de mi equipo cuando lo necesito.','DIM-APOYO',FALSE),
 ('R-04','Tengo margen para decidir como organizo mi trabajo.','DIM-AUTON',FALSE),
 ('R-05','Tengo claridad sobre lo que se espera de mi.','DIM-CLARID',FALSE);

INSERT INTO catalogo.reactivo_version (instrumento_id, version, reactivo_id, orden)
SELECT 'INST-BIENESTAR',1,reactivo_id,ROW_NUMBER() OVER (ORDER BY reactivo_id)
FROM catalogo.reactivo;

-- cuatro campanias consecutivas: permiten construir tendencia
INSERT INTO catalogo.campania
   (campania_id, nombre, instrumento_id, version_instrumento, fecha_inicio, fecha_fin, estado, secuencia) VALUES
 ('CAMP-2026-S1','Medicion semana 1','INST-BIENESTAR',1,'2026-08-03','2026-08-07','CERRADA',1),
 ('CAMP-2026-S2','Medicion semana 2','INST-BIENESTAR',1,'2026-08-10','2026-08-14','CERRADA',2),
 ('CAMP-2026-S3','Medicion semana 3','INST-BIENESTAR',1,'2026-08-17','2026-08-21','CERRADA',3),
 ('CAMP-2026-S4','Medicion semana 4','INST-BIENESTAR',1,'2026-08-24','2026-08-28','ABIERTA',4);

INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id)
SELECT c.campania_id, u.unidad_organizacional_id
FROM catalogo.campania c
CROSS JOIN (VALUES ('UO-CC-TURNO-B'),('UO-LOG-TURNO-A')) AS u(unidad_organizacional_id);

INSERT INTO consentimiento.aviso_privacidad
 (aviso_id, version, fecha_vigencia, vigente, datos_capturados, finalidad, plazo_retencion,
  quien_accede, quien_no_accede, forma_agregacion, explicacion_k, explicacion_dp,
  consecuencias_revocar, politica_retencion, canal_contacto)
VALUES
 ('AVISO-v1','1.0','2026-07-01',TRUE,
  'Tus respuestas al instrumento de bienestar, tu unidad organizacional, la fecha y la version de este aviso.',
  'Identificar condiciones de trabajo que generan desgaste, a nivel de area y turno, para poder corregirlas.',
  'Veinticuatro meses para las respuestas; cinco anos para la evidencia de consentimiento.',
  'Tu lider, el especialista de bienestar y la direccion, siempre en forma de resultados de grupo protegidos.',
  'Nadie accede a tus respuestas individuales. No existe un puntaje individual visible para la organizacion.',
  'Las respuestas se promedian por unidad y campania. El promedio se publica con ruido matematico.',
  'Si tu grupo tiene menos de cinco respuestas no se publica ningun resultado, porque con pocas personas seria posible deducir quien dijo que.',
  'A cada resultado se le suma ruido calibrado. Esto limita lo que alguien puede deducir sobre ti aunque repita muchas consultas. Cada consulta gasta un presupuesto de privacidad que, al agotarse, detiene la publicacion de resultados nuevos.',
  'Dejaras de recibir encuestas. Tus respuestas anteriores no se eliminan pero no se recolectaran nuevas.',
  'Las respuestas se eliminan a los veinticuatro meses. La evidencia de consentimiento se conserva cinco anos.',
  'bienestar@nexum.com.mx');

-- usuarios: uno por perfil + colaboradores
INSERT INTO usuarios.usuario (usuario_id, nombre, apellido_paterno, apellido_materno, correo, contrasena_hash) VALUES
 ('USR-00001','Ana','Perez','Gomez','ana.perez@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00002','Carlos','Ramirez','Lopez','carlos.ramirez@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00003','Mariana','Solis','Cantu','mariana.solis@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00004','Roberto','Garcia','Vazquez','roberto.garcia@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00005','Lucia','Hernandez','Martinez','lucia.hernandez@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00101','Diego','Morales','Rangel','diego.morales@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00102','Sofia','Aguilar','Nunez','sofia.aguilar@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00103','Javier','Ortiz','Guerrero','javier.ortiz@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00104','Valeria','Cazares','Montoya','valeria.cazares@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00105','Andres','Lozano','Ibarra','andres.lozano@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00106','Paulina','Rivera','Esquivel','paulina.rivera@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00107','Hector','Delgado','Pena','hector.delgado@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00201','Karla','Sandoval','Ruiz','karla.sandoval@nexum.com.mx',crypt('demo123',gen_salt('bf'))),
 ('USR-00202','Emilio','Zapata','Fuentes','emilio.zapata@nexum.com.mx',crypt('demo123',gen_salt('bf')));

INSERT INTO usuarios.usuario_perfil (usuario_id, perfil_id, unidad_alcance_id)
SELECT v.usuario_id, p.perfil_id, v.unidad
FROM (VALUES
 ('USR-00001','COLABORADOR',NULL),        ('USR-00002','ADMINISTRADOR',NULL),
 ('USR-00003','ESPECIALISTA',NULL),       ('USR-00004','AUDITOR',NULL),
 ('USR-00005','LIDER','UO-CC-TURNO-B'),
 ('USR-00101','COLABORADOR',NULL),('USR-00102','COLABORADOR',NULL),
 ('USR-00103','COLABORADOR',NULL),('USR-00104','COLABORADOR',NULL),
 ('USR-00105','COLABORADOR',NULL),('USR-00106','COLABORADOR',NULL),
 ('USR-00107','COLABORADOR',NULL),('USR-00201','COLABORADOR',NULL),
 ('USR-00202','COLABORADOR',NULL)
) AS v(usuario_id, perfil_codigo, unidad)
JOIN usuarios.perfil p ON p.codigo = v.perfil_codigo;

-- 8 colaboradores en Turno B (supera k=5) y 3 en Logistica (no supera)
INSERT INTO usuarios.empleado
 (empleado_id, usuario_id, nombre, apellido_paterno, fecha_ingreso, unidad_organizacional_id) VALUES
 ('EMP-001','USR-00001','Ana','Perez','2022-03-15','UO-CC-TURNO-B'),
 ('EMP-002','USR-00101','Diego','Morales','2023-07-10','UO-CC-TURNO-B'),
 ('EMP-003','USR-00102','Sofia','Aguilar','2023-09-01','UO-CC-TURNO-B'),
 ('EMP-004','USR-00103','Javier','Ortiz','2024-02-19','UO-CC-TURNO-B'),
 ('EMP-005','USR-00104','Valeria','Cazares','2024-06-03','UO-CC-TURNO-B'),
 ('EMP-006','USR-00105','Andres','Lozano','2025-01-13','UO-CC-TURNO-B'),
 ('EMP-007','USR-00106','Paulina','Rivera','2025-04-22','UO-CC-TURNO-B'),
 ('EMP-008','USR-00107','Hector','Delgado','2025-08-11','UO-CC-TURNO-B'),
 ('EMP-101',NULL,       'Roberto','Garcia','2024-01-05','UO-LOG-TURNO-A'),
 ('EMP-102','USR-00201','Karla','Sandoval','2024-08-20','UO-LOG-TURNO-A'),
 ('EMP-103','USR-00202','Emilio','Zapata','2025-03-11','UO-LOG-TURNO-A');

INSERT INTO consentimiento.seudonimo (seudonimo_id, empleado_id)
SELECT 'SEUD-' || SUBSTRING(empleado_id FROM 5), empleado_id FROM usuarios.empleado;

-- consentimiento: todos aceptan; uno de Logistica revoca despues (historial completo)
INSERT INTO consentimiento.consentimiento (seudonimo_id, aviso_id, estado, fecha_evento)
SELECT s.seudonimo_id,'AVISO-v1','ACEPTADO','2026-08-01 09:00:00-06'::TIMESTAMPTZ
FROM consentimiento.seudonimo s;

INSERT INTO consentimiento.consentimiento (seudonimo_id, aviso_id, estado, fecha_evento)
VALUES ('SEUD-103','AVISO-v1','REVOCADO','2026-08-20 11:30:00-06');
-- ---------------------------------------------------------------------------
-- Respuestas de autoreporte: 4 campanias con tendencia descendente en Turno B
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_camp     RECORD;
    v_seud     RECORD;
    v_resp_id  BIGINT;
    v_react    RECORD;
    v_base     NUMERIC;
    v_valor    SMALLINT;
    v_ajuste   NUMERIC;
BEGIN
    FOR v_camp IN SELECT campania_id, secuencia FROM catalogo.campania ORDER BY secuencia LOOP
        FOR v_seud IN
            SELECT s.seudonimo_id, e.unidad_organizacional_id
            FROM consentimiento.seudonimo s
            JOIN usuarios.empleado e ON e.empleado_id = s.empleado_id
            JOIN consentimiento.v_estado_vigente ev ON ev.seudonimo_id = s.seudonimo_id
            WHERE ev.estado = 'ACEPTADO'
        LOOP
            -- Turno B se deteriora con el tiempo; Logistica se mantiene estable
            IF v_seud.unidad_organizacional_id = 'UO-CC-TURNO-B' THEN
                v_base := 4.0 - (v_camp.secuencia - 1) * 0.35;
            ELSE
                v_base := 3.6;
            END IF;

            INSERT INTO autoreporte.respuesta
                (seudonimo_id, campania_id, unidad_organizacional_id, aviso_id, fecha_respuesta)
            VALUES (v_seud.seudonimo_id, v_camp.campania_id, v_seud.unidad_organizacional_id,
                    'AVISO-v1', NOW() - (4 - v_camp.secuencia) * INTERVAL '7 days')
            RETURNING respuesta_id INTO v_resp_id;

            FOR v_react IN SELECT reactivo_id, dimension_id FROM catalogo.reactivo ORDER BY reactivo_id LOOP
                -- carga y recuperacion caen mas rapido que las demas dimensiones
                v_ajuste := CASE WHEN v_react.dimension_id IN ('DIM-CARGA','DIM-RECUP') THEN -0.4 ELSE 0.2 END;
                v_valor  := GREATEST(1, LEAST(5, ROUND(v_base + v_ajuste + (random() - 0.5))))::SMALLINT;
                INSERT INTO autoreporte.respuesta_detalle (respuesta_id, reactivo_id, valor)
                VALUES (v_resp_id, v_react.reactivo_id, v_valor);
            END LOOP;
        END LOOP;
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Reglas de riesgo organizacional
-- ---------------------------------------------------------------------------
INSERT INTO riesgo.regla
 (regla_id, nombre, condicion_legible, dimension_id, umbral_valor, comparador,
  campanias_consecutivas, nivel) VALUES
 ('RG-01','Carga percibida elevada de forma sostenida',
  'Si la carga percibida agregada es menor o igual a 2.8 durante 3 campanias consecutivas y n >= k, entonces sugerir revision de carga del equipo.',
  'DIM-CARGA',2.8,'<=',3,'PRIORITARIO'),
 ('RG-02','Recuperacion insuficiente',
  'Si la recuperacion agregada es menor o igual a 3.0 y n >= k, entonces sugerir pausas estructuradas y revision de turnos.',
  'DIM-RECUP',3.0,'<=',1,'ATENCION'),
 ('RG-03','Apoyo y autonomia bajos',
  'Si el apoyo percibido y la autonomia agregados son menores o iguales a 3.0, entonces recomendar intervencion de liderazgo.',
  'DIM-APOYO',3.0,'<=',1,'ATENCION'),
 ('RG-04','Deterioro sostenido del indice global',
  'Si el indice agregado global empeora durante 3 campanias consecutivas y n >= k, entonces sugerir revision integral de la unidad.',
  NULL,NULL,NULL,3,'PRIORITARIO');

INSERT INTO riesgo.regla_recomendacion (regla_id, tipo_intervencion, orden) VALUES
 ('RG-01','REDISTRIBUCION_CARGA',1), ('RG-01','REVISION_STAFFING',2), ('RG-01','REDUCCION_HORAS_EXTRA',3),
 ('RG-02','PAUSAS_ESTRUCTURADAS',1), ('RG-02','REVISION_TURNOS',2), ('RG-02','ACCIONES_RECUPERACION',3),
 ('RG-03','CAPACITACION_LIDERAZGO',1), ('RG-03','MEJORA_AUTONOMIA',2),
 ('RG-04','REVISION_STAFFING',1), ('RG-04','REVISION_CARGA_ADMIN',2);

-- =============================================================================
-- 14. VISTAS DE TABLERO (lo que cada perfil puede ver)
-- =============================================================================

-- Colaborador: solo su propio estado. Sin resultados, sin diagnosticos.
-- Vive en el esquema portal, no en autoreporte: asi el esquema de respuestas
-- permanece libre de cualquier referencia a la identidad (garantia G2).
CREATE SCHEMA IF NOT EXISTS portal;
COMMENT ON SCHEMA portal IS
  'Vistas que una persona consulta sobre SI MISMA. La aplicacion debe filtrar siempre por el usuario de la sesion.';

CREATE OR REPLACE VIEW portal.v_participacion_propia AS
SELECT e.usuario_id,
       s.seudonimo_id,
       ev.estado                          AS estado_consentimiento,
       ev.fecha_evento                    AS fecha_consentimiento,
       (SELECT COUNT(*) FROM autoreporte.respuesta r WHERE r.seudonimo_id = s.seudonimo_id) AS campanias_respondidas,
       (SELECT MAX(r.fecha_respuesta) FROM autoreporte.respuesta r WHERE r.seudonimo_id = s.seudonimo_id) AS ultima_participacion
FROM consentimiento.seudonimo s
JOIN usuarios.empleado e ON e.empleado_id = s.empleado_id
LEFT JOIN consentimiento.v_estado_vigente ev ON ev.seudonimo_id = s.seudonimo_id
WHERE e.usuario_id IS NOT NULL;

COMMENT ON VIEW portal.v_participacion_propia IS
  'Tablero del colaborador. Se consulta SIEMPRE con WHERE usuario_id = <usuario de la sesion>. No expone puntajes ni interpretaciones clinicas.';

-- Campanias abiertas que la persona aun no responde
CREATE OR REPLACE VIEW portal.v_campanias_pendientes AS
SELECT e.usuario_id, s.seudonimo_id, c.campania_id, c.nombre AS campania,
       c.fecha_inicio, c.fecha_fin
FROM consentimiento.seudonimo s
JOIN usuarios.empleado e  ON e.empleado_id = s.empleado_id
JOIN catalogo.campania_unidad cu ON cu.unidad_organizacional_id = e.unidad_organizacional_id
JOIN catalogo.campania c  ON c.campania_id = cu.campania_id AND c.estado = 'ABIERTA'
JOIN consentimiento.v_estado_vigente ev ON ev.seudonimo_id = s.seudonimo_id AND ev.estado = 'ACEPTADO'
WHERE e.usuario_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM autoreporte.respuesta r
                  WHERE r.seudonimo_id = s.seudonimo_id AND r.campania_id = c.campania_id);

-- Lider y especialista: solo agregados protegidos ya publicados
CREATE OR REPLACE VIEW agregado.v_tablero_unidad AS
SELECT rp.unidad_organizacional_id,
       uo.nombre                AS unidad,
       c.campania_id,
       c.secuencia,
       COALESCE(d.nombre,'Indice global') AS dimension,
       rp.estado_publicacion,
       CASE rp.estado_publicacion
            WHEN 'PUBLICADO'                      THEN 'suficiente'
            WHEN 'GRUPO_INSUFICIENTE'             THEN 'insuficiente'
            WHEN 'PRESUPUESTO_PRIVACIDAD_AGOTADO' THEN 'no disponible: presupuesto de privacidad agotado'
       END AS participacion_protegida,
       rp.precision_advertencia,
       rp.valor_protegido,
       rp.epsilon_aplicado,
       rp.mecanismo
FROM agregado.resultado_protegido rp
JOIN organizacion.unidad_organizacional uo ON uo.unidad_organizacional_id = rp.unidad_organizacional_id
JOIN catalogo.campania c ON c.campania_id = rp.campania_id
LEFT JOIN catalogo.dimension d ON d.dimension_id = rp.dimension_id;

COMMENT ON VIEW agregado.v_tablero_unidad IS
  'Tablero del lider. No expone n exacto para evitar inferencia por diferencia: solo indica si la participacion fue suficiente.';

-- Auditor: quien accedio, a que, cuando, con que resultado. Sin contenido sensible.
CREATE OR REPLACE VIEW auditoria.v_tablero_auditoria AS
SELECT b.fecha_hora,
       b.actor_usuario_id,
       u.nombre || ' ' || u.apellido_paterno AS actor_nombre,
       b.actor_perfil,
       b.accion,
       ta.descripcion        AS accion_descripcion,
       b.tipo_recurso,
       b.recurso_id,
       b.resultado,
       b.correlacion_id
FROM auditoria.bitacora b
LEFT JOIN usuarios.usuario u ON u.usuario_id = b.actor_usuario_id
JOIN auditoria.tipo_accion ta ON ta.codigo = b.accion;

COMMENT ON VIEW auditoria.v_tablero_auditoria IS
  'Tablero de auditoria. Responde quien, que, cuando, sobre que recurso y si fue autorizada, sin mostrar el contenido de ninguna respuesta.';

-- Estado del presupuesto de privacidad
CREATE OR REPLACE VIEW agregado.v_estado_presupuesto AS
SELECT p.campania_id,
       p.unidad_organizacional_id,
       uo.nombre                AS unidad,
       p.epsilon_total,
       p.epsilon_consumido,
       p.epsilon_total - p.epsilon_consumido AS epsilon_restante,
       p.agotado,
       (SELECT COUNT(*) FROM agregado.consulta_privada cp WHERE cp.presupuesto_id = p.presupuesto_id) AS consultas_realizadas
FROM agregado.presupuesto_privacidad p
JOIN organizacion.unidad_organizacional uo ON uo.unidad_organizacional_id = p.unidad_organizacional_id;
-- =============================================================================
-- 18. BITACORA: eventos de ejemplo que cubren el ciclo completo
-- =============================================================================
INSERT INTO auditoria.bitacora
 (actor_usuario_id, actor_perfil, accion, tipo_recurso, recurso_id, resultado, correlacion_id, direccion_origen, fecha_hora) VALUES
 ('USR-00001','COLABORADOR','LOGIN_EXITOSO',      NULL,NULL,'EXITO','corr-a1b2c3d4','10.20.4.18','2026-08-24 07:58:00-06'),
 ('USR-00001','COLABORADOR','AVISO_CONSULTADO',   'AVISO','AVISO-v1','EXITO','corr-a1b2c3d4','10.20.4.18','2026-08-24 07:58:40-06'),
 ('USR-00001','COLABORADOR','CONSENT_OTORGADO',   'CONSENTIMIENTO','AVISO-v1','EXITO','corr-a1b2c3d4','10.20.4.18','2026-08-24 07:59:10-06'),
 ('USR-00001','COLABORADOR','AUTOREPORTE_ENVIADO','CAMPANIA','CAMP-2026-S4','EXITO','corr-a1b2c3d4','10.20.4.18','2026-08-24 08:03:22-06'),
 ('USR-00005','LIDER','AGREGADO_CONSULTADO','UNIDAD','UO-CC-TURNO-B','EXITO','corr-e5f6a7b8','10.20.7.44','2026-08-25 10:41:00-06'),
 ('USR-00005','LIDER','AGREGADO_CONSULTADO','UNIDAD','UO-LOG-TURNO-A','GRUPO_INSUFICIENTE','corr-e5f6a7b9','10.20.7.44','2026-08-25 10:44:00-06'),
 ('USR-00005','LIDER','TENDENCIA_CONSULTADA','UNIDAD','UO-CC-TURNO-B','EXITO','corr-e5f6a7c0','10.20.7.44','2026-08-25 10:46:00-06'),
 ('USR-00003','ESPECIALISTA','AGREGADO_CONSULTADO','UNIDAD','UO-CC-TURNO-B','EXITO','corr-11aa22bb','10.20.2.9','2026-08-26 09:15:00-06'),
 ('USR-00003','ESPECIALISTA','AGREGADO_CONSULTADO','UNIDAD','UO-CC-TURNO-B','PRESUPUESTO_AGOTADO','corr-11aa22bc','10.20.2.9','2026-08-26 09:31:00-06'),
 ('USR-00003','ESPECIALISTA','INTERVENCION_PROPUESTA','UNIDAD','UO-CC-TURNO-B','EXITO','corr-33cc44dd','10.20.2.9','2026-08-26 11:02:00-06'),
 ('USR-00004','AUDITOR','CONSENT_VERIFICADO','CONSENTIMIENTO','SEUD-001','EXITO','corr-55ee66ff','10.20.1.77','2026-08-27 16:20:00-06'),
 ('USR-00004','AUDITOR','BITACORA_CONSULTADA','BITACORA',NULL,'EXITO','corr-55ee6700','10.20.1.77','2026-08-27 16:22:00-06'),
 ('USR-00002','ADMINISTRADOR','PARAMETRO_MODIFICADO','PARAMETRO','epsilon_por_consulta','EXITO','corr-77aa88bb','10.20.1.5','2026-08-28 08:22:00-06'),
 (NULL,'DESCONOCIDO','LOGIN_FALLIDO',NULL,NULL,'RECHAZADO','corr-99cc00dd','10.20.9.201','2026-08-28 23:14:00-06');

-- =============================================================================
-- 19. VISTA DE ACCESOS PROPIOS (transparencia verificable para el colaborador)
-- =============================================================================
CREATE OR REPLACE VIEW portal.v_accesos_a_mis_datos AS
SELECT e.usuario_id,
       b.fecha_hora,
       b.actor_perfil,
       ta.descripcion AS que_hizo,
       b.resultado
FROM auditoria.bitacora b
JOIN auditoria.tipo_accion ta ON ta.codigo = b.accion
JOIN consentimiento.seudonimo s ON s.seudonimo_id = b.recurso_id
JOIN usuarios.empleado e        ON e.empleado_id = s.empleado_id
WHERE b.tipo_recurso = 'CONSENTIMIENTO'
  AND e.usuario_id IS NOT NULL;

COMMENT ON VIEW portal.v_accesos_a_mis_datos IS
  'Permite a la persona ver quien consulto informacion relacionada con ella. La transparencia es verificable, no una promesa del aviso.';
