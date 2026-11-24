-- =============================================================================
-- 04_catalogos_crud.sql  (Integrante 2 - Fase 1)
-- Soporte CRUD real de catÃ¡logos. NO destructivo e IDEMPOTENTE:
--   * solo ADD COLUMN IF NOT EXISTS / CREATE ... IF NOT EXISTS
--   * constraints envueltos en bloques que verifican pg_constraint
--   * no cambia tipos, no borra ni renombra nada de 01-03
-- ConvenciÃ³n: se usa `fecha_actualizacion` (misma que 01) para reutilizar
-- fn_actualizar_fecha_modificacion(). `activo` = baja lÃ³gica (soft delete).
-- =============================================================================
BEGIN;

-- 1. Columnas de baja lÃ³gica / auditorÃ­a de cambio -----------------------------
ALTER TABLE catalogo.instrumento         ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.version_instrumento ADD COLUMN IF NOT EXISTS fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.version_instrumento ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.reactivo            ADD COLUMN IF NOT EXISTS fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.reactivo            ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE catalogo.campania            ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE consentimiento.version_consentimiento
                                         ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE auditoria.tipo_accion        ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE auditoria.tipo_accion        ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE auditoria.tipo_recurso       ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE auditoria.resultado_auditoria ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Triggers de fecha_actualizacion para las tablas nuevas (idempotente) -------
DO $$
DECLARE t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY[
        'catalogo.instrumento','catalogo.version_instrumento','catalogo.reactivo',
        'catalogo.campania','consentimiento.version_consentimiento','auditoria.tipo_accion'
    ]) LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_actualizacion ON %s', replace(t,'.','_'), t);
        EXECUTE format(
            'CREATE TRIGGER trg_%I_actualizacion BEFORE UPDATE ON %s
             FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion()',
            replace(t,'.','_'), t);
    END LOOP;
END $$;

-- 3. Unicidad (case-insensitive) para evitar duplicados al hacer CRUD ----------
CREATE UNIQUE INDEX IF NOT EXISTS ux_instrumento_nombre
    ON catalogo.instrumento (lower(nombre));
CREATE UNIQUE INDEX IF NOT EXISTS ux_campania_nombre
    ON catalogo.campania (lower(nombre));
CREATE UNIQUE INDEX IF NOT EXISTS ux_unidad_padre_nombre
    ON organizacion.unidad_organizacional (COALESCE(unidad_padre_id,''), lower(nombre));
CREATE UNIQUE INDEX IF NOT EXISTS ux_riv_orden
    ON catalogo.reactivo_instrumento_version (instrumento_id, version, orden);

-- 4. CHECK constraints (solo si no existen) -----------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_version_instrumento_positiva') THEN
        ALTER TABLE catalogo.version_instrumento
            ADD CONSTRAINT ck_version_instrumento_positiva CHECK (version > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_reactivo_escala_orden') THEN
        ALTER TABLE catalogo.reactivo
            ADD CONSTRAINT ck_reactivo_escala_orden CHECK (escala_min < escala_max);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_riv_orden_positivo') THEN
        ALTER TABLE catalogo.reactivo_instrumento_version
            ADD CONSTRAINT ck_riv_orden_positivo CHECK (orden > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_campania_unidad_fechas') THEN
        ALTER TABLE catalogo.campania_unidad
            ADD CONSTRAINT ck_campania_unidad_fechas
            CHECK (fecha_cierre IS NULL OR fecha_apertura IS NULL OR fecha_cierre >= fecha_apertura);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_version_consent_fechas') THEN
        ALTER TABLE consentimiento.version_consentimiento
            ADD CONSTRAINT ck_version_consent_fechas
            CHECK (fecha_fin_vigencia IS NULL OR fecha_fin_vigencia >= fecha_vigencia);
    END IF;
END $$;

-- 5. Ãndices de consulta para listados/filtros ---------------------------------
CREATE INDEX IF NOT EXISTS idx_instrumento_activo        ON catalogo.instrumento (activo);
CREATE INDEX IF NOT EXISTS idx_version_instrumento_activo ON catalogo.version_instrumento (instrumento_id, activo);
CREATE INDEX IF NOT EXISTS idx_reactivo_activo           ON catalogo.reactivo (activo);
CREATE INDEX IF NOT EXISTS idx_riv_reactivo              ON catalogo.reactivo_instrumento_version (reactivo_id);
CREATE INDEX IF NOT EXISTS idx_campania_activa_fechas    ON catalogo.campania (activa, fecha_inicio, fecha_fin);
CREATE INDEX IF NOT EXISTS idx_campania_instrumento      ON catalogo.campania (instrumento_id, version_instrumento);
CREATE INDEX IF NOT EXISTS idx_campania_unidad_unidad    ON catalogo.campania_unidad (unidad_organizacional_id);
CREATE INDEX IF NOT EXISTS idx_tipo_accion_activo        ON auditoria.tipo_accion (activo);

COMMIT;

