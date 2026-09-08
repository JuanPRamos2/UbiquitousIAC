-- =============================================================================
-- Plataforma de Bienestar Laboral y Prevención de Burnout
-- Equipo 03 · Proyecto 4 · Primer Parcial
-- Motor: PostgreSQL 15+
-- Base de datos: bienestar_nexum
-- =============================================================================
-- Este script crea la parte RELACIONAL del sistema. Las dos colecciones MongoDB
-- (respuestas_encuesta, bitacora_auditoria) referencian estas tablas por
-- identificador, NO por join directo. La única referencia cruzada permitida
-- entre identidad real y seudonimización es la tabla consentimiento.seudonimo.
-- =============================================================================

-- 0. CREACIÓN DE LA BASE DE DATOS
-- =============================================================================
-- Ejecutar como superusuario (postgres) antes de continuar:
--
--   DROP DATABASE IF EXISTS bienestar_nexum;
--   CREATE DATABASE bienestar_nexum
--       WITH OWNER = postgres
--            ENCODING = 'UTF8'
--            LC_COLLATE = 'es_ES.UTF-8'
--            LC_CTYPE  = 'es_ES.UTF-8'
--            TEMPLATE  = template0;
--   \c bienestar_nexum

-- 1. EXTENSIONES
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. ESQUEMAS
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS organizacion    AUTHORIZATION postgres;
CREATE SCHEMA IF NOT EXISTS usuarios       AUTHORIZATION postgres;
CREATE SCHEMA IF NOT EXISTS catalogo       AUTHORIZATION postgres;
CREATE SCHEMA IF NOT EXISTS consentimiento AUTHORIZATION postgres;
CREATE SCHEMA IF NOT EXISTS agregado       AUTHORIZATION postgres;
CREATE SCHEMA IF NOT EXISTS auditoria      AUTHORIZATION postgres;

-- =============================================================================
-- 3. ESQUEMA: ORGANIZACIÓN
-- =============================================================================

-- 3.1 Unidad organizacional
CREATE TABLE organizacion.unidad_organizacional (
    unidad_organizacional_id VARCHAR(40)  PRIMARY KEY,   -- UO-CALLCENTER-TURNO-B
    nombre                  VARCHAR(180) NOT NULL,
    descripcion             TEXT,
    unidad_padre_id         VARCHAR(40)
                            REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id)
                            ON DELETE SET NULL,
    nivel_jerarquico        SMALLINT     NOT NULL DEFAULT 0,
    activa                  BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_actualizacion     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_unidad_padre ON organizacion.unidad_organizacional(unidad_padre_id);
CREATE INDEX idx_unidad_activa ON organizacion.unidad_organizacional(activa);

COMMENT ON TABLE organizacion.unidad_organizacional IS
    'Catálogo de unidades organizacionales. Referenciada por MongoDB '
    'respuestas_encuesta.unidad_organizacional_id y bitacora_auditoria.recurso. '
    'Alimenta la agregación por umbral k (RN-04).';

-- =============================================================================
-- 4. ESQUEMA: USUARIOS
-- =============================================================================

-- 4.1 Perfil
CREATE TABLE usuarios.perfil (
    perfil_id           SERIAL       PRIMARY KEY,
    codigo              VARCHAR(40)  NOT NULL UNIQUE,   -- COLAB, AUDITOR, LIDER_TURNO, ADMIN_SISTEMA
    nombre              VARCHAR(120) NOT NULL,
    descripcion         TEXT,
    nivel_acceso        SMALLINT     NOT NULL DEFAULT 1
                        CHECK (nivel_acceso BETWEEN 0 AND 10),
    activo              BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_actualizacion TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE usuarios.perfil IS
    'Perfiles del sistema (Colaborador, Líder de Turno, Auditor de Cumplimiento, '
    'Administrador del Sistema). Se copian a bitacora_auditoria.actor_perfil en el '
    'momento de la acción para preservar el valor histórico.';

INSERT INTO usuarios.perfil (codigo, nombre, nivel_acceso) VALUES
    ('COLAB',         'Colaborador',               1),
    ('LIDER_TURNO',   'Líder de Turno',            3),
    ('AUDITOR',       'Auditor de Cumplimiento',   4),
    ('ADMIN_SISTEMA', 'Administrador del Sistema', 9);

-- 4.2 Usuario
CREATE TABLE usuarios.usuario (
    usuario_id          VARCHAR(20)  PRIMARY KEY,   -- USR-00027
    nombre              VARCHAR(120) NOT NULL,
    apellido_paterno    VARCHAR(120) NOT NULL,
    apellido_materno    VARCHAR(120),
    correo              VARCHAR(180) NOT NULL UNIQUE,
    contrasena_hash     TEXT,                       -- hash bcrypt/argon2
    activo              BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_actualizacion TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_ultimo_acceso TIMESTAMPTZ
);

CREATE INDEX idx_usuario_correo ON usuarios.usuario(correo);
CREATE INDEX idx_usuario_activo ON usuarios.usuario(activo);

COMMENT ON TABLE usuarios.usuario IS
    'Cuentas de acceso. Referenciada por MongoDB bitacora_auditoria.actor_id '
    '(sin join real, solo por identificador).';

-- 4.3 Relación usuario-perfil (un usuario puede tener varios perfiles)
CREATE TABLE usuarios.usuario_perfil (
    usuario_id        VARCHAR(20) NOT NULL
                      REFERENCES usuarios.usuario(usuario_id) ON DELETE CASCADE,
    perfil_id         INTEGER     NOT NULL
                      REFERENCES usuarios.perfil(perfil_id),
    fecha_asignacion  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    perfil_principal  BOOLEAN     NOT NULL DEFAULT FALSE,
    PRIMARY KEY (usuario_id, perfil_id)
);

-- 4.4 Empleado
CREATE TABLE usuarios.empleado (
    empleado_id             VARCHAR(20)  PRIMARY KEY,  -- EMP-00142
    usuario_id              VARCHAR(20)  UNIQUE
                            REFERENCES usuarios.usuario(usuario_id) ON DELETE SET NULL,
    nombre                  VARCHAR(120) NOT NULL,
    apellido_paterno        VARCHAR(120) NOT NULL,
    apellido_materno        VARCHAR(120),
    fecha_ingreso           DATE         NOT NULL,
    fecha_baja              DATE,
    unidad_organizacional_id VARCHAR(40) NOT NULL
                            REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    activo                  BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_actualizacion     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_empleado_unidad ON usuarios.empleado(unidad_organizacional_id);
CREATE INDEX idx_empleado_activo ON usuarios.empleado(activo);

-- =============================================================================
-- 5. ESQUEMA: CATÁLOGO
-- =============================================================================

-- 5.1 Instrumento
CREATE TABLE catalogo.instrumento (
    instrumento_id  VARCHAR(40)  PRIMARY KEY,   -- INST-NOM035-GUIA3
    nombre          VARCHAR(180) NOT NULL,
    descripcion     TEXT,
    tipo            VARCHAR(40)  NOT NULL
                    CHECK (tipo IN ('NOM035','CLIMA','BREVE','PERSONALIZADO')),
    activo          BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 5.2 Versión de instrumento
CREATE TABLE catalogo.version_instrumento (
    instrumento_id        VARCHAR(40) NOT NULL
                          REFERENCES catalogo.instrumento(instrumento_id) ON DELETE CASCADE,
    version               SMALLINT    NOT NULL,
    fecha_vigencia_desde  DATE        NOT NULL,
    fecha_vigencia_hasta  DATE,
    archivo_plantilla     TEXT,
    activo                BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (instrumento_id, version),
    CHECK (fecha_vigencia_hasta IS NULL OR fecha_vigencia_hasta >= fecha_vigencia_desde)
);

COMMENT ON TABLE catalogo.version_instrumento IS
    'Versión del instrumento. La combinación (instrumento_id, version) es '
    'referenciada por MongoDB respuestas_encuesta.{instrumento_id, version_instrumento}.';

-- 5.3 Reactivo
CREATE TABLE catalogo.reactivo (
    reactivo_id   VARCHAR(20)  PRIMARY KEY,   -- R-01
    texto         TEXT         NOT NULL,
    dimension     VARCHAR(80),
    escala_min    SMALLINT     NOT NULL DEFAULT 1
                  CHECK (escala_min BETWEEN 0 AND 10),
    escala_max    SMALLINT     NOT NULL DEFAULT 5
                  CHECK (escala_max BETWEEN 1 AND 10),
    invertido     BOOLEAN      NOT NULL DEFAULT FALSE,
    activo        BOOLEAN      NOT NULL DEFAULT TRUE
);

-- 5.4 Reactivos por versión de instrumento (define la estructura del array embebido)
CREATE TABLE catalogo.reactivo_instrumento_version (
    instrumento_id  VARCHAR(40) NOT NULL,
    version         SMALLINT    NOT NULL,
    reactivo_id     VARCHAR(20) NOT NULL
                    REFERENCES catalogo.reactivo(reactivo_id) ON DELETE RESTRICT,
    orden           SMALLINT    NOT NULL,
    obligatorio     BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (instrumento_id, version, reactivo_id),
    FOREIGN KEY (instrumento_id, version)
        REFERENCES catalogo.version_instrumento(instrumento_id, version)
        ON DELETE CASCADE
);

-- 5.5 Campaña
CREATE TABLE catalogo.campania (
    campania_id          VARCHAR(40)  PRIMARY KEY,   -- CAMP-2026-Q3-CALLCENTER
    nombre               VARCHAR(180) NOT NULL,
    descripcion          TEXT,
    fecha_inicio         DATE         NOT NULL,
    fecha_fin            DATE         NOT NULL,
    instrumento_id       VARCHAR(40)  NOT NULL
                         REFERENCES catalogo.instrumento(instrumento_id),
    version_instrumento  SMALLINT     NOT NULL,
    activa               BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    FOREIGN KEY (instrumento_id, version_instrumento)
        REFERENCES catalogo.version_instrumento(instrumento_id, version),
    CHECK (fecha_fin >= fecha_inicio)
);

COMMENT ON TABLE catalogo.campania IS
    'Campañas de aplicación. Referenciada por MongoDB respuestas_encuesta.campania_id.';

-- 5.6 Campaña-Unidad (asignación)
CREATE TABLE catalogo.campania_unidad (
    campania_id              VARCHAR(40) NOT NULL
                             REFERENCES catalogo.campania(campania_id) ON DELETE CASCADE,
    unidad_organizacional_id VARCHAR(40) NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    fecha_apertura           DATE,
    fecha_cierre             DATE,
    PRIMARY KEY (campania_id, unidad_organizacional_id)
);

-- =============================================================================
-- 6. ESQUEMA: CONSENTIMIENTO
-- =============================================================================

-- 6.1 Versión del documento de consentimiento
CREATE TABLE consentimiento.version_consentimiento (
    version_consentimiento_id VARCHAR(40) PRIMARY KEY,   -- CONSENT-v3-2026-07-01
    documento_url             TEXT,
    resumen_cambios           TEXT,
    fecha_vigencia            DATE        NOT NULL,
    fecha_fin_vigencia        DATE,
    activo                    BOOLEAN     NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE consentimiento.version_consentimiento IS
    'Versión del documento de consentimiento. Permite trazabilidad histórica '
    'de qué versión firmó el colaborador (decisión D-02).';

-- 6.2 Seudónimo (tabla pivote de identidad)
CREATE TABLE consentimiento.seudonimo (
    seudonimo_id     VARCHAR(20)  PRIMARY KEY,   -- SEUD-2026-014892
    empleado_id      VARCHAR(20)  NOT NULL UNIQUE
                     REFERENCES usuarios.empleado(empleado_id) ON DELETE RESTRICT,
    fecha_generacion TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    algoritmo        VARCHAR(40)  NOT NULL DEFAULT 'HMAC-SHA256',
    sal              TEXT,                       -- sal/noise usado
    activo           BOOLEAN      NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE consentimiento.seudonimo IS
    'Pivote crítico de seudonimización (decisión D-01). Vincula empleado_id '
    '(identidad real) con seudonimo_id (identidad operativa). Esta es la ÚNICA '
    'tabla que contiene la correspondencia; su acceso debe estar restringido y '
    'auditado. MongoDB respuestas_encuesta SOLO debe usar seudonimo_id.';

-- 6.3 Consentimiento (registro de otorgamiento)
CREATE TABLE consentimiento.consentimiento (
    consentimiento_id          BIGSERIAL    PRIMARY KEY,
    seudonimo_id               VARCHAR(20)  NOT NULL
                               REFERENCES consentimiento.seudonimo(seudonimo_id),
    version_consentimiento_id  VARCHAR(40)  NOT NULL
                               REFERENCES consentimiento.version_consentimiento(version_consentimiento_id),
    fecha_aceptacion           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_revocacion           TIMESTAMPTZ,
    ip_origen                  INET,
    estado                     VARCHAR(20)  NOT NULL DEFAULT 'ACEPTADO'
                               CHECK (estado IN ('ACEPTADO','REVOCADO','EXPIRADO')),
    hash_documento             TEXT,
    UNIQUE (seudonimo_id, version_consentimiento_id)
);

CREATE INDEX idx_consentimiento_seudonimo ON consentimiento.consentimiento(seudonimo_id);
CREATE INDEX idx_consentimiento_estado ON consentimiento.consentimiento(estado);

-- =============================================================================
-- 7. ESQUEMA: AGREGADO
-- =============================================================================

-- 7.1 Parámetro global
CREATE TABLE agregado.parametro_global (
    parametro_id        SERIAL       PRIMARY KEY,
    clave               VARCHAR(80)  NOT NULL UNIQUE,   -- 'k', 'version_activa_consentimiento'
    valor               TEXT         NOT NULL,
    descripcion         TEXT,
    fecha_actualizacion TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    actualizado_por     VARCHAR(20)
                        REFERENCES usuarios.usuario(usuario_id)
);

COMMENT ON TABLE agregado.parametro_global IS
    'Parámetros globales del sistema. Ejemplo: el umbral k (RN-04) o la versión '
    'activa del consentimiento. Cualquier cambio aquí debe generar una entrada '
    'en bitacora_auditoria con accion=CAMBIO_UMBRAL_K (RNF-04, RNF-07).';

INSERT INTO agregado.parametro_global (clave, valor, descripcion) VALUES
    ('k',                             '5',                       'Umbral mínimo de respuestas por unidad para mostrar agregados (RN-04)'),
    ('version_activa_consentimiento', 'CONSENT-v3-2026-07-01',   'Versión activa del documento de consentimiento');

-- 7.2 Agregado calculado
CREATE TABLE agregado.agregado_calculado (
    agregado_id              BIGSERIAL    PRIMARY KEY,
    campania_id              VARCHAR(40)  NOT NULL
                             REFERENCES catalogo.campania(campania_id),
    unidad_organizacional_id VARCHAR(40)  NOT NULL
                             REFERENCES organizacion.unidad_organizacional(unidad_organizacional_id),
    instrumento_id           VARCHAR(40)  NOT NULL,
    version_instrumento      SMALLINT     NOT NULL,
    total_respuestas         INTEGER      NOT NULL CHECK (total_respuestas >= 0),
    supera_umbral_k          BOOLEAN      NOT NULL,
    k_umbral                 INTEGER      NOT NULL,
    promedio_global          NUMERIC(5,2),
    detalle_json             JSONB        NOT NULL,
    fecha_calculo            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    valido_hasta             TIMESTAMPTZ,
    UNIQUE (campania_id, unidad_organizacional_id, instrumento_id, version_instrumento),
    FOREIGN KEY (instrumento_id, version_instrumento)
        REFERENCES catalogo.version_instrumento(instrumento_id, version)
);

CREATE INDEX idx_agregado_unidad_camp ON agregado.agregado_calculado(unidad_organizacional_id, campania_id);

COMMENT ON TABLE agregado.agregado_calculado IS
    'Resultados precalculados. La clave Redis cache:agregado:{unidad}:{campania} '
    'apunta conceptualmente a esta fila. El campo supera_umbral_k determina '
    'si se muestra o no al usuario (RN-04).';

-- =============================================================================
-- 8. ESQUEMA: AUDITORÍA (solo catálogos de soporte, los LOGS viven en MongoDB)
-- =============================================================================

CREATE TABLE auditoria.tipo_accion (
    tipo_accion_id SERIAL       PRIMARY KEY,
    codigo         VARCHAR(60)  NOT NULL UNIQUE,
    descripcion    TEXT         NOT NULL,
    es_sensible    BOOLEAN      NOT NULL DEFAULT TRUE
);

INSERT INTO auditoria.tipo_accion (codigo, descripcion) VALUES
    ('CONSULTA_HISTORIAL_CONSENTIMIENTO', 'Consulta del historial de consentimientos de un seudónimo'),
    ('CONSULTA_AGREGADO',                 'Consulta de resultados agregados por unidad/campaña'),
    ('CAMBIO_UMBRAL_K',                   'Cambio del umbral k de agregación'),
    ('CAMBIO_CONSENTIMIENTO',             'Cambio/alta de versión del documento de consentimiento'),
    ('LOGIN_FALLIDO',                     'Intento de inicio de sesión fallido'),
    ('LOGIN_EXITOSO',                     'Inicio de sesión exitoso'),
    ('LOGOUT',                            'Cierre de sesión'),
    ('CREACION_RESPUESTA',                'Registro de nueva respuesta de encuesta');

CREATE TABLE auditoria.resultado_auditoria (
    resultado_id SERIAL       PRIMARY KEY,
    codigo       VARCHAR(40)  NOT NULL UNIQUE,
    descripcion  TEXT
);

INSERT INTO auditoria.resultado_auditoria (codigo, descripcion) VALUES
    ('EXITO',              'Operación completada con éxito'),
    ('RECHAZADO',          'Operación rechazada por falta de permisos'),
    ('GRUPO_INSUFICIENTE', 'Operación rechazada por no alcanzar el umbral k'),
    ('ERROR_TECNICO',      'Error técnico durante la operación');

CREATE TABLE auditoria.tipo_recurso (
    tipo_recurso_id SERIAL       PRIMARY KEY,
    codigo          VARCHAR(60)  NOT NULL UNIQUE,
    descripcion     TEXT
);

INSERT INTO auditoria.tipo_recurso (codigo, descripcion) VALUES
    ('SEUDONIMO',              'Registro de seudonimización'),
    ('UNIDAD_ORGANIZACIONAL',  'Unidad organizacional'),
    ('PARAMETRO_GLOBAL',       'Parámetro global del sistema'),
    ('VERSION_CONSENTIMIENTO', 'Versión del documento de consentimiento'),
    ('RESPUESTA_ENCUESTA',     'Respuesta de encuesta');

-- =============================================================================
-- 9. VISTAS DE APOYO
-- =============================================================================

-- 9.1 Consentimiento vigente por seudónimo
CREATE OR REPLACE VIEW consentimiento.v_consentimiento_vigente AS
SELECT
    s.seudonimo_id,
    s.empleado_id,
    vc.version_consentimiento_id,
    vc.fecha_vigencia,
    c.fecha_aceptacion
FROM consentimiento.seudonimo s
JOIN consentimiento.consentimiento c
     ON c.seudonimo_id = s.seudonimo_id
    AND c.estado = 'ACEPTADO'
    AND c.fecha_revocacion IS NULL
JOIN consentimiento.version_consentimiento vc
     ON vc.version_consentimiento_id = c.version_consentimiento_id
    AND vc.activo = TRUE;

-- 9.2 Catálogo de unidades activas
CREATE OR REPLACE VIEW organizacion.v_unidades_activas AS
SELECT
    unidad_organizacional_id,
    nombre,
    unidad_padre_id,
    nivel_jerarquico
FROM organizacion.unidad_organizacional
WHERE activa = TRUE;

-- 9.3 Usuarios con su perfil principal (para mapear actor_id en bitácora)
CREATE OR REPLACE VIEW auditoria.v_actor_perfil AS
SELECT
    u.usuario_id,
    u.nombre || ' ' || u.apellido_paterno AS nombre_completo,
    p.codigo AS perfil_codigo,
    p.nombre AS perfil_nombre,
    p.nivel_acceso
FROM usuarios.usuario u
JOIN usuarios.usuario_perfil up ON up.usuario_id = u.usuario_id
JOIN usuarios.perfil p          ON p.perfil_id = up.perfil_id
WHERE up.perfil_principal = TRUE
  AND u.activo = TRUE
  AND p.activo = TRUE;

-- =============================================================================
-- 10. DATOS DE EJEMPLO (coherentes con los JSON de MongoDB)
-- =============================================================================

-- 10.1 Unidades organizacionales
INSERT INTO organizacion.unidad_organizacional (unidad_organizacional_id, nombre, descripcion) VALUES
    ('UO-CALLCENTER-TURNO-A', 'Call Center - Turno A', 'Operadores turno matutino'),
    ('UO-CALLCENTER-TURNO-B', 'Call Center - Turno B', 'Operadores turno vespertino'),
    ('UO-LOGISTICA-TURNO-A',  'Logística - Turno A',   'Almacén y distribución matutino');

-- 10.2 Instrumentos y versiones
INSERT INTO catalogo.instrumento (instrumento_id, nombre, tipo) VALUES
    ('INST-NOM035-GUIA3', 'NOM-035 Guía III',             'NOM035'),
    ('INST-CLIMA-BREVE',  'Cuestionario Breve de Clima',  'CLIMA');

INSERT INTO catalogo.version_instrumento (instrumento_id, version, fecha_vigencia_desde) VALUES
    ('INST-NOM035-GUIA3', 1, '2025-01-01'),
    ('INST-NOM035-GUIA3', 2, '2026-01-01'),
    ('INST-CLIMA-BREVE',  1, '2026-01-01');

-- 10.3 Reactivos
INSERT INTO catalogo.reactivo (reactivo_id, texto, dimension) VALUES
    ('R-01', 'Siento que mi carga de trabajo es manejable', 'Carga'),
    ('R-02', 'Tengo claridad sobre mis responsabilidades',  'Claridad'),
    ('R-03', 'Recibo retroalimentación constante',          'Retroalimentación'),
    ('R-04', 'Mi jornada me permite descansar',             'Jornada'),
    ('R-05', 'Me siento apoyado por mi equipo',             'Apoyo');

INSERT INTO catalogo.reactivo_instrumento_version
    (instrumento_id, version, reactivo_id, orden) VALUES
    ('INST-NOM035-GUIA3', 2, 'R-01', 1),
    ('INST-NOM035-GUIA3', 2, 'R-02', 2),
    ('INST-NOM035-GUIA3', 2, 'R-03', 3),
    ('INST-NOM035-GUIA3', 2, 'R-04', 4),
    ('INST-NOM035-GUIA3', 2, 'R-05', 5),
    ('INST-CLIMA-BREVE',  1, 'R-01', 1),
    ('INST-CLIMA-BREVE',  1, 'R-02', 2),
    ('INST-CLIMA-BREVE',  1, 'R-03', 3);

-- 10.4 Versiones de consentimiento
INSERT INTO consentimiento.version_consentimiento
    (version_consentimiento_id, resumen_cambios, fecha_vigencia) VALUES
    ('CONSENT-v2-2026-05-10', 'Versión inicial del documento',                    '2026-05-10'),
    ('CONSENT-v3-2026-07-01', 'Se agregan cláusulas de revocación y portabilidad', '2026-07-01');

-- 10.5 Campañas
INSERT INTO catalogo.campania
    (campania_id, nombre, fecha_inicio, fecha_fin, instrumento_id, version_instrumento) VALUES
    ('CAMP-2026-Q3-CALLCENTER', 'Campaña Q3 - Call Center',
     '2026-08-01', '2026-09-30', 'INST-NOM035-GUIA3', 2),
    ('CAMP-2026-Q3-LOGISTICA',  'Campaña Q3 - Logística',
     '2026-08-01', '2026-09-30', 'INST-CLIMA-BREVE',  1);

INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id) VALUES
    ('CAMP-2026-Q3-CALLCENTER', 'UO-CALLCENTER-TURNO-B'),
    ('CAMP-2026-Q3-LOGISTICA',  'UO-LOGISTICA-TURNO-A');

-- 10.6 Usuarios
INSERT INTO usuarios.usuario
    (usuario_id, nombre, apellido_paterno, apellido_materno, correo, contrasena_hash) VALUES
    ('USR-00001', 'Ana',     'Pérez',    'Gómez',      'ana.perez@empresa.com',      crypt('demo123', gen_salt('bf'))),
    ('USR-00002', 'Carlos',  'Ramírez',  'López',      'carlos.ramirez@empresa.com', crypt('demo123', gen_salt('bf'))),
    ('USR-00011', 'Lucía',   'Hernández','Martínez',   'lucia.hernandez@empresa.com',crypt('demo123', gen_salt('bf'))),
    ('USR-00027', 'Roberto', 'García',   'Vázquez',    'roberto.garcia@empresa.com', crypt('demo123', gen_salt('bf')));

INSERT INTO usuarios.usuario_perfil (usuario_id, perfil_id, perfil_principal)
SELECT 'USR-00001', perfil_id, TRUE FROM usuarios.perfil WHERE codigo = 'COLAB'
UNION ALL
SELECT 'USR-00002', perfil_id, TRUE FROM usuarios.perfil WHERE codigo = 'ADMIN_SISTEMA'
UNION ALL
SELECT 'USR-00011', perfil_id, TRUE FROM usuarios.perfil WHERE codigo = 'LIDER_TURNO'
UNION ALL
SELECT 'USR-00027', perfil_id, TRUE FROM usuarios.perfil WHERE codigo = 'AUDITOR';

-- 10.7 Empleados y seudónimos (D-01: el seudónimo se deriva del empleado)
INSERT INTO usuarios.empleado
    (empleado_id, usuario_id, nombre, apellido_paterno, apellido_materno,
     fecha_ingreso, unidad_organizacional_id) VALUES
    ('EMP-00142', 'USR-00001', 'Ana',     'Pérez',    'Gómez',    '2022-03-15', 'UO-CALLCENTER-TURNO-B'),
    ('EMP-00933', NULL,        'Lucía',   'Hernández','Martínez', '2023-07-10', 'UO-CALLCENTER-TURNO-B'),
    ('EMP-00210', NULL,        'Roberto', 'García',   'Vázquez',  '2024-01-05', 'UO-LOGISTICA-TURNO-A');

INSERT INTO consentimiento.seudonimo (seudonimo_id, empleado_id) VALUES
    ('SEUD-2026-014892', 'EMP-00142'),
    ('SEUD-2026-009331', 'EMP-00933'),
    ('SEUD-2026-002104', 'EMP-00210');

-- 10.8 Consentimientos (D-02: se registra la versión firmada)
INSERT INTO consentimiento.consentimiento
    (seudonimo_id, version_consentimiento_id, ip_origen, estado) VALUES
    ('SEUD-2026-014892', 'CONSENT-v3-2026-07-01', '10.20.4.18',  'ACEPTADO'),
    ('SEUD-2026-009331', 'CONSENT-v3-2026-07-01', '10.20.4.18',  'ACEPTADO'),
    ('SEUD-2026-002104', 'CONSENT-v2-2026-05-10', '10.20.7.44',  'ACEPTADO');

-- =============================================================================
-- 11. TRIGGER: actualizar fecha_actualizacion automáticamente
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_actualizar_fecha_modificacion()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN
        SELECT c.table_schema || '.' || c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
              ON t.table_schema = c.table_schema
             AND t.table_name   = c.table_name
             AND t.table_type   = 'BASE TABLE'
        WHERE c.column_name = 'fecha_actualizacion'
          AND c.table_schema IN ('organizacion','usuarios','catalogo','agregado')
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%I_actualizacion
             BEFORE UPDATE ON %s
             FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();',
            replace(t, '.', '_'), t);
    END LOOP;
END $$;

-- =============================================================================
-- 12. MAPEO: TABLAS POSTGRESQL ←→ DOCUMENTOS MONGODB
-- =============================================================================
--
-- ESQUEMA         TABLA                          REFERENCIADA POR MONGO
-- -------------   ----------------------------   --------------------------------
-- organizacion    unidad_organizacional          respuestas_encuesta, bitacora_auditoria
-- usuarios        usuario                        bitacora_auditoria.actor_id
-- usuarios        empleado                       (pivote, NO se referencia desde Mongo)
-- usuarios        perfil                         (se copia a bitacora_auditoria.actor_perfil)
-- catalogo        instrumento + version          respuestas_encuesta.instrumento_id
-- catalogo        campania                       respuestas_encuesta.campania_id
-- catalogo        reactivo                       (valida respuestas_encuesta.respuestas[].reactivo_id)
-- consentimiento  seudonimo                      respuestas_encuesta.seudonimo_id
-- consentimiento  version_consentimiento         respuestas_encuesta.version_consentimiento
-- consentimiento  consentimiento                 (trazabilidad del otorgamiento)
-- agregado        parametro_global               bitacora_auditoria.recurso
-- agregado        agregado_calculado             (cacheada en Redis: cache:agregado:{u}:{c})
-- auditoria       tipo_accion/resultado/recurso  (catálogos de validación, no logs)
--
-- DECISIONES DE DISEÑO CLAVE
-- ---------------------------
-- D-01: Seudonimización — solo seudonimo_id viaja a Mongo, jamás empleado_id.
-- D-02: Trazabilidad de consentimiento — se guarda la versión firmada.
-- RN-01: Un seudónimo responde una vez por campaña (validado en app, índice único en Mongo).
-- RN-04: Umbral k — se valida contra agregado_calculado.total_respuestas vs k_umbral.
-- RNF-04: Cambio de k — auditable (CAMBIO_UMBRAL_K).
-- RNF-07: Bitácora — vive en MongoDB por volumen; aquí solo catálogos.
--
-- FIN DEL SCRIPT
-- =============================================================================
