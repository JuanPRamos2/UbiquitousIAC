-- =====================================================================
-- Migración 003 — Registro de autorreporte sin abrir el esquema
--
-- PROBLEMA
-- --------
-- El sistema web necesita guardar una respuesta de encuesta. La
-- tentación es otorgarle al rol de la aplicación permiso de uso sobre el
-- esquema autoreporte. Eso sería un retroceso: aunque solo tuviera
-- INSERT, la cláusula RETURNING de un INSERT exige permiso de lectura
-- sobre la columna devuelta, y a partir de ahí la frontera se empieza a
-- erosionar concesión por concesión.
--
-- SOLUCIÓN
-- --------
-- Una función propiedad del rol motor que recibe las respuestas y hace
-- la escritura completa por dentro. La aplicación llama a la función y
-- recibe un estado; nunca toca el esquema.
--
-- Beneficio adicional: las reglas de negocio quedan del lado del motor.
-- RN-01 (una respuesta por campaña) y el rango válido de la escala se
-- hacen cumplir aquí, de modo que sigan valiendo aunque mañana escriba
-- otro cliente distinto del sistema web.
-- =====================================================================

BEGIN;

-- El rol motor podia leer autoreporte (migracion 001) pero no escribir.
-- Para registrar una respuesta necesita INSERT sobre las dos tablas y uso
-- de sus secuencias. Sigue sin poder borrar ni actualizar: una respuesta
-- enviada no se modifica.
GRANT INSERT ON autoreporte.respuesta, autoreporte.respuesta_detalle
    TO bienestar_motor;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA autoreporte TO bienestar_motor;

CREATE OR REPLACE FUNCTION autoreporte.fn_registrar_autoreporte(
    p_seudonimo_id VARCHAR,
    p_campania_id  VARCHAR,
    p_valores      JSONB          -- {"R-01": 4, "R-02": 3, ...}
) RETURNS TABLE (estado VARCHAR, mensaje TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = autoreporte, catalogo, consentimiento, usuarios,
                  organizacion, pg_temp
AS $$
DECLARE
    v_unidad     VARCHAR;
    v_aviso      VARCHAR;
    v_respuesta  BIGINT;
    v_reactivo   RECORD;
    v_valor      INT;
    v_esperados  INT;
    v_recibidos  INT;
BEGIN
    -- 1. La campaña debe estar abierta.
    IF NOT EXISTS (SELECT 1 FROM catalogo.campania ca
                    WHERE ca.campania_id = p_campania_id
                      AND ca.estado = 'ABIERTA') THEN
        RETURN QUERY SELECT 'CAMPANIA_NO_ABIERTA'::VARCHAR,
               'La campania no admite respuestas en este momento.'::TEXT;
        RETURN;
    END IF;

    -- 2. RN-02: sin consentimiento vigente no se acepta la respuesta.
    IF NOT EXISTS (SELECT 1 FROM consentimiento.v_estado_vigente ev
                    WHERE ev.seudonimo_id = p_seudonimo_id
                      AND ev.estado = 'ACEPTADO') THEN
        RETURN QUERY SELECT 'SIN_CONSENTIMIENTO'::VARCHAR,
               'No hay consentimiento vigente para esta finalidad.'::TEXT;
        RETURN;
    END IF;

    -- 3. RN-01: una sola respuesta por campaña.
    IF EXISTS (SELECT 1 FROM autoreporte.respuesta re
                WHERE re.seudonimo_id = p_seudonimo_id
                  AND re.campania_id = p_campania_id) THEN
        RETURN QUERY SELECT 'YA_RESPONDIDA'::VARCHAR,
               'Esta campania ya fue respondida.'::TEXT;
        RETURN;
    END IF;

    -- 4. La unidad se toma del padron, no de lo que mande el cliente:
    --    dejar que el cliente declare su unidad permitiria contaminar
    --    los agregados de otra area.
    SELECT e.unidad_organizacional_id INTO v_unidad
      FROM consentimiento.seudonimo s
      JOIN usuarios.empleado e ON e.empleado_id = s.empleado_id
     WHERE s.seudonimo_id = p_seudonimo_id;

    IF v_unidad IS NULL THEN
        RETURN QUERY SELECT 'SEUDONIMO_INVALIDO'::VARCHAR,
               'El seudonimo no corresponde a un colaborador activo.'::TEXT;
        RETURN;
    END IF;

    SELECT ap.aviso_id INTO v_aviso FROM consentimiento.aviso_privacidad ap
     WHERE ap.vigente ORDER BY ap.version DESC LIMIT 1;

    -- 5. Todos los reactivos de la version del instrumento, completos.
    SELECT count(*) INTO v_esperados
      FROM catalogo.campania c
      JOIN catalogo.reactivo_version rv
        ON rv.instrumento_id = c.instrumento_id AND rv.version = c.version_instrumento
      JOIN catalogo.reactivo r ON r.reactivo_id = rv.reactivo_id AND r.activo
     WHERE c.campania_id = p_campania_id;

    SELECT count(*) INTO v_recibidos FROM jsonb_object_keys(p_valores);

    IF v_recibidos <> v_esperados THEN
        RETURN QUERY SELECT 'RESPUESTA_INCOMPLETA'::VARCHAR,
               format('Se esperaban %s reactivos y se recibieron %s.',
                      v_esperados, v_recibidos)::TEXT;
        RETURN;
    END IF;

    -- 6. Escritura. Encabezado y detalle en la misma transaccion.
    INSERT INTO autoreporte.respuesta
        (seudonimo_id, campania_id, unidad_organizacional_id, aviso_id)
    VALUES (p_seudonimo_id, p_campania_id, v_unidad, v_aviso)
    RETURNING respuesta_id INTO v_respuesta;

    FOR v_reactivo IN
        SELECT r.reactivo_id, vi.escala_min, vi.escala_max
          FROM catalogo.campania c
          JOIN catalogo.version_instrumento vi
            ON vi.instrumento_id = c.instrumento_id AND vi.version = c.version_instrumento
          JOIN catalogo.reactivo_version rv
            ON rv.instrumento_id = vi.instrumento_id AND rv.version = vi.version
          JOIN catalogo.reactivo r ON r.reactivo_id = rv.reactivo_id AND r.activo
         WHERE c.campania_id = p_campania_id
    LOOP
        v_valor := (p_valores ->> v_reactivo.reactivo_id)::INT;

        IF v_valor IS NULL
           OR v_valor < v_reactivo.escala_min
           OR v_valor > v_reactivo.escala_max THEN
            RAISE EXCEPTION 'Valor fuera de la escala para el reactivo % (recibido %)',
                  v_reactivo.reactivo_id, v_valor;
        END IF;

        INSERT INTO autoreporte.respuesta_detalle (respuesta_id, reactivo_id, valor)
        VALUES (v_respuesta, v_reactivo.reactivo_id, v_valor::SMALLINT);
    END LOOP;

    RETURN QUERY SELECT 'REGISTRADA'::VARCHAR,
           'Respuesta registrada de forma seudonimizada.'::TEXT;
END;
$$;

ALTER FUNCTION autoreporte.fn_registrar_autoreporte(VARCHAR, VARCHAR, JSONB)
    OWNER TO bienestar_motor;

REVOKE ALL ON FUNCTION autoreporte.fn_registrar_autoreporte(VARCHAR, VARCHAR, JSONB)
    FROM PUBLIC;

-- Para invocar una funcion hace falta USAGE sobre su esquema, incluso si
-- la funcion es SECURITY DEFINER. USAGE por si solo no concede nada sobre
-- las tablas: la aplicacion podra llamar a esta funcion y seguira sin
-- poder leer ni escribir directamente en autoreporte.
GRANT USAGE ON SCHEMA autoreporte TO bienestar_app;
GRANT EXECUTE ON FUNCTION autoreporte.fn_registrar_autoreporte(VARCHAR, VARCHAR, JSONB)
    TO bienestar_app;

-- Los permisos directos sobre las tablas dejan de hacer falta y se
-- retiran: la unica via es la funcion.
REVOKE INSERT ON autoreporte.respuesta, autoreporte.respuesta_detalle
    FROM bienestar_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA autoreporte FROM bienestar_app;

COMMENT ON FUNCTION autoreporte.fn_registrar_autoreporte(VARCHAR, VARCHAR, JSONB) IS
    'Unica via por la que la aplicacion puede escribir una respuesta. La aplicacion no tiene permiso de uso sobre el esquema autoreporte.';

COMMIT;
