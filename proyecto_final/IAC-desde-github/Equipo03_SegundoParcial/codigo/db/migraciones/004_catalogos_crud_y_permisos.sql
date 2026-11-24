-- =====================================================================
-- Migración 004 — CRUD de catálogos, baja lógica y permisos nuevos
--
-- ORIGEN
-- ------
-- Esta migración recoge la intención de db/postgres/04_catalogos_crud.sql
-- que entregó el Integrante 2 y la corrige contra el esquema que está
-- realmente entregado. La versión original no se podía aplicar: nombraba
-- `catalogo.reactivo_instrumento_version` (la tabla es
-- `catalogo.reactivo_version`), ponía la escala en `catalogo.reactivo`
-- (vive en `catalogo.version_instrumento`), filtraba
-- `catalogo.campania.activa` (el estado de una campaña es `estado`),
-- tocaba `consentimiento.version_consentimiento` y
-- `auditoria.tipo_recurso` (no existen; son `aviso_privacidad` y
-- `resultado`) y llamaba a `fn_actualizar_fecha_modificacion()`, que
-- nunca se creó. Se conservan sus decisiones de diseño, que son buenas:
-- baja lógica en lugar de DELETE, unicidad insensible a mayúsculas,
-- fechas de actualización por trigger e índices para los listados.
--
-- POR QUÉ BAJA LÓGICA Y NO DELETE
-- -------------------------------
-- Un DELETE de una unidad o de un reactivo rompería las llaves foráneas
-- de las respuestas ya registradas, o dejaría huérfano el histórico. Una
-- unidad que se cierra se marca inactiva: los agregados de las campañas
-- pasadas siguen pudiendo explicarse.
--
-- PERMISOS NUEVOS
-- ---------------
-- El RBAC del proyecto es dirigido por datos, así que un permiso nuevo es
-- una fila, no una constante en el código. Se agregan tres que el segundo
-- parcial necesita: administrar unidades organizacionales, solicitar
-- apoyo y atender solicitudes de apoyo.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Función de trigger para la fecha de actualización
-- ---------------------------------------------------------------------
-- La migración del Integrante 2 la daba por existente. Se crea aquí, una
-- sola vez, y la reutilizan todas las tablas.
CREATE OR REPLACE FUNCTION public.fn_actualizar_fecha_modificacion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.fecha_actualizacion := NOW();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.fn_actualizar_fecha_modificacion() IS
    'Pone fecha_actualizacion = NOW() en cada UPDATE. La fecha la escribe la base y no el cliente: un cliente con el reloj mal puesto no puede falsear cuando se modifico un catalogo.';

-- ---------------------------------------------------------------------
-- 2. Columnas de baja lógica y de auditoría de cambio (idempotente)
-- ---------------------------------------------------------------------
ALTER TABLE catalogo.instrumento
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.version_instrumento
    ADD COLUMN IF NOT EXISTS fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.version_instrumento
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.version_instrumento
    ADD COLUMN IF NOT EXISTS activa              BOOLEAN     NOT NULL DEFAULT TRUE;
ALTER TABLE catalogo.reactivo
    ADD COLUMN IF NOT EXISTS fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.reactivo
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.campania
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
-- Una campaña NO lleva columna `activa`: su ciclo de vida es
-- `estado` (BORRADOR, ABIERTA, CERRADA, CANCELADA) y tener dos campos que
-- dicen lo mismo abre la puerta a que se contradigan.
ALTER TABLE auditoria.tipo_accion
    ADD COLUMN IF NOT EXISTS activo              BOOLEAN     NOT NULL DEFAULT TRUE;
ALTER TABLE auditoria.tipo_accion
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE auditoria.resultado
    ADD COLUMN IF NOT EXISTS activo              BOOLEAN     NOT NULL DEFAULT TRUE;
ALTER TABLE consentimiento.aviso_privacidad
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- `descripcion` en unidades: la capa de datos del catalog-service la
-- consulta y la tabla original no la tenía.
ALTER TABLE organizacion.unidad_organizacional
    ADD COLUMN IF NOT EXISTS descripcion TEXT;

-- ---------------------------------------------------------------------
-- 3. Triggers de fecha_actualizacion (idempotentes)
-- ---------------------------------------------------------------------
DO $$
DECLARE
    t         TEXT;
    sufijo    TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY[
        'organizacion.unidad_organizacional',
        'catalogo.instrumento',
        'catalogo.version_instrumento',
        'catalogo.reactivo',
        'catalogo.campania',
        'consentimiento.aviso_privacidad',
        'auditoria.tipo_accion'
    ]) LOOP
        sufijo := replace(t, '.', '_');
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_actualizacion ON %s', sufijo, t);
        EXECUTE format(
            'CREATE TRIGGER trg_%s_actualizacion BEFORE UPDATE ON %s
             FOR EACH ROW EXECUTE FUNCTION public.fn_actualizar_fecha_modificacion()',
            sufijo, t);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------
-- 4. Unicidad insensible a mayúsculas, para que el CRUD no duplique
-- ---------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS ux_instrumento_nombre
    ON catalogo.instrumento (lower(nombre));
CREATE UNIQUE INDEX IF NOT EXISTS ux_campania_nombre
    ON catalogo.campania (lower(nombre));
-- Dos unidades hermanas no pueden llamarse igual; dos unidades de padres
-- distintos sí ("Turno A" existe en varias plantas).
CREATE UNIQUE INDEX IF NOT EXISTS ux_unidad_padre_nombre
    ON organizacion.unidad_organizacional (COALESCE(unidad_padre_id, ''), lower(nombre));
CREATE UNIQUE INDEX IF NOT EXISTS ux_reactivo_version_orden
    ON catalogo.reactivo_version (instrumento_id, version, orden);

-- ---------------------------------------------------------------------
-- 5. Restricciones CHECK (solo si no existen)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_version_instrumento_positiva') THEN
        ALTER TABLE catalogo.version_instrumento
            ADD CONSTRAINT ck_version_instrumento_positiva CHECK (version > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_reactivo_version_orden_positivo') THEN
        ALTER TABLE catalogo.reactivo_version
            ADD CONSTRAINT ck_reactivo_version_orden_positivo CHECK (orden > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_unidad_plantilla_no_negativa') THEN
        ALTER TABLE organizacion.unidad_organizacional
            ADD CONSTRAINT ck_unidad_plantilla_no_negativa CHECK (plantilla_declarada >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_aviso_fechas') THEN
        ALTER TABLE consentimiento.aviso_privacidad
            ADD CONSTRAINT ck_aviso_fechas
            CHECK (fecha_fin_vigencia IS NULL OR fecha_fin_vigencia >= fecha_vigencia);
    END IF;
END $$;

-- ---------------------------------------------------------------------
-- 6. Índices de consulta para los listados y filtros del CRUD
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_instrumento_activo
    ON catalogo.instrumento (activo);
CREATE INDEX IF NOT EXISTS idx_version_instrumento_activa
    ON catalogo.version_instrumento (instrumento_id, activa);
CREATE INDEX IF NOT EXISTS idx_reactivo_activo
    ON catalogo.reactivo (activo);
CREATE INDEX IF NOT EXISTS idx_reactivo_version_reactivo
    ON catalogo.reactivo_version (reactivo_id);
CREATE INDEX IF NOT EXISTS idx_campania_estado_fechas
    ON catalogo.campania (estado, fecha_inicio, fecha_fin);
CREATE INDEX IF NOT EXISTS idx_campania_instrumento
    ON catalogo.campania (instrumento_id, version_instrumento);
CREATE INDEX IF NOT EXISTS idx_campania_unidad_unidad
    ON catalogo.campania_unidad (unidad_organizacional_id);
CREATE INDEX IF NOT EXISTS idx_tipo_accion_activo
    ON auditoria.tipo_accion (activo);

-- ---------------------------------------------------------------------
-- 7. Permisos nuevos (RBAC dirigido por datos: un permiso es una fila)
-- ---------------------------------------------------------------------
INSERT INTO usuarios.permiso (codigo, descripcion, sensible) VALUES
 ('UNIDAD_ADMIN',    'Administrar unidades organizacionales del catalogo', FALSE),
 ('APOYO_SOLICITAR', 'Solicitar apoyo de bienestar de forma seudonimizada', FALSE),
 ('APOYO_ATENDER',   'Atender y cambiar el estado de las solicitudes de apoyo', TRUE)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO usuarios.perfil_permiso (perfil_id, permiso_id)
SELECT pf.perfil_id, pm.permiso_id
  FROM (VALUES
        ('ADMINISTRADOR', 'UNIDAD_ADMIN'),
        ('COLABORADOR',   'APOYO_SOLICITAR'),
        ('ESPECIALISTA',  'APOYO_ATENDER'),
        ('ADMINISTRADOR', 'APOYO_ATENDER')
       ) AS v(perfil_codigo, permiso_codigo)
  JOIN usuarios.perfil  pf ON pf.codigo = v.perfil_codigo
  JOIN usuarios.permiso pm ON pm.codigo = v.permiso_codigo
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- 8. Privilegios del rol de la aplicación para el CRUD de catálogos
-- ---------------------------------------------------------------------
-- Se otorgan INSERT y UPDATE, nunca DELETE: la baja es lógica. Esto NO
-- debilita la garantía central del proyecto, porque administrar catálogos
-- no da ningún acceso al contenido de las respuestas: el esquema
-- autoreporte sigue cerrado para este rol.
DO $$
DECLARE v_rol TEXT := 'bienestar_app';
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_rol) THEN
        EXECUTE format('GRANT INSERT, UPDATE ON organizacion.unidad_organizacional TO %I', v_rol);
        EXECUTE format('GRANT INSERT, UPDATE ON catalogo.instrumento TO %I', v_rol);
        EXECUTE format('GRANT INSERT, UPDATE ON catalogo.version_instrumento TO %I', v_rol);
        EXECUTE format('GRANT INSERT, UPDATE ON catalogo.reactivo TO %I', v_rol);
        EXECUTE format('GRANT INSERT, UPDATE ON catalogo.campania TO %I', v_rol);
        -- reactivo_version y campania_unidad son tablas de relación: aquí
        -- sí se permite DELETE, porque desasociar un reactivo de una
        -- versión no borra el reactivo ni ninguna respuesta.
        EXECUTE format('GRANT INSERT, UPDATE, DELETE ON catalogo.reactivo_version TO %I', v_rol);
        EXECUTE format('GRANT INSERT, UPDATE, DELETE ON catalogo.campania_unidad TO %I', v_rol);
        -- Administración de perfiles y de su matriz de permisos, para la
        -- pantalla de perfiles del sistema web (Integrante 1).
        EXECUTE format('GRANT INSERT, UPDATE ON usuarios.perfil TO %I', v_rol);
        EXECUTE format('GRANT USAGE ON SEQUENCE usuarios.perfil_perfil_id_seq TO %I', v_rol);
        EXECUTE format('GRANT INSERT, DELETE ON usuarios.perfil_permiso TO %I', v_rol);
    END IF;
END $$;

COMMIT;
