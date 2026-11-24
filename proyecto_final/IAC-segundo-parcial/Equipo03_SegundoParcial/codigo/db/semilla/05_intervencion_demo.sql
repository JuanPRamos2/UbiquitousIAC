-- =====================================================================
-- Un plan de intervencion de ejemplo, con seguimiento y evaluacion.
--
-- Sirve para que al abrir el sistema por primera vez el modulo de
-- intervenciones no este vacio y se pueda ver el ciclo completo cerrado.
-- La demostracion en vivo crea uno nuevo desde la interfaz.
--
-- Se elige la unidad con mas campanias publicadas, para que la evaluacion
-- antes/despues tenga material real que comparar.
-- =====================================================================

DO $$
DECLARE
    v_unidad     VARCHAR;
    v_det        BIGINT;
    v_plan       BIGINT;
    v_antes      VARCHAR;
    v_despues    VARCHAR;
    v_va         NUMERIC;
    v_vd         NUMERIC;
    v_concl      VARCHAR;
BEGIN
    -- Unidad con al menos dos indices globales publicados.
    SELECT unidad_organizacional_id INTO v_unidad
      FROM agregado.resultado_protegido
     WHERE dimension_id IS NULL AND estado_publicacion = 'PUBLICADO'
     GROUP BY unidad_organizacional_id
    HAVING count(*) >= 2
     ORDER BY count(*) DESC, unidad_organizacional_id
     LIMIT 1;

    IF v_unidad IS NULL THEN
        RAISE NOTICE 'Sin unidades con dos campanias publicadas; no se crea el ejemplo.';
        RETURN;
    END IF;

    SELECT deteccion_id INTO v_det
      FROM riesgo.deteccion
     WHERE unidad_organizacional_id = v_unidad
     ORDER BY deteccion_id LIMIT 1;

    INSERT INTO intervencion.plan
        (unidad_organizacional_id, tipo_intervencion, deteccion_id, justificacion,
         resultado_esperado, fecha_inicio, fecha_fin, responsable_usuario_id,
         estado, campania_linea_base)
    SELECT v_unidad, 'REDISTRIBUCION_CARGA', v_det,
           'La carga percibida agregada de esta unidad se mantuvo por debajo del '
           'umbral durante campanias consecutivas, con participacion suficiente '
           'en todas ellas.',
           'Recuperar el indice de carga percibida al menos al nivel de la primera campania.',
           CURRENT_DATE - 21, CURRENT_DATE + 7, 'USR-00003', 'EN_EJECUCION',
           (SELECT campania_id FROM agregado.resultado_protegido
             WHERE unidad_organizacional_id = v_unidad AND dimension_id IS NULL
               AND estado_publicacion = 'PUBLICADO'
             ORDER BY campania_id LIMIT 1)
    RETURNING intervencion_id INTO v_plan;

    INSERT INTO intervencion.seguimiento
        (intervencion_id, estado_reportado, avance_nota, registrado_por)
    VALUES
        (v_plan, 'EN_EJECUCION',
         'Se redistribuyeron 40 horas semanales entre dos turnos y se suspendieron '
         'las horas extra voluntarias durante el periodo.', 'USR-00003'),
        (v_plan, 'EN_EJECUCION',
         'Se incorporaron dos pausas estructuradas de 15 minutos por turno.',
         'USR-00003');

    -- Evaluacion comparando la primera y la ultima campania publicadas.
    -- Se ordena por la secuencia de la campania, no por la fecha de calculo:
    -- los agregados se precalculan en lote y comparten marca de tiempo, asi
    -- que ordenar por fecha podria tomar dos veces la misma campania.
    SELECT rp.campania_id, rp.valor_protegido INTO v_antes, v_va
      FROM agregado.resultado_protegido rp
      JOIN catalogo.campania c ON c.campania_id = rp.campania_id
     WHERE rp.unidad_organizacional_id = v_unidad AND rp.dimension_id IS NULL
       AND rp.estado_publicacion = 'PUBLICADO'
     ORDER BY c.secuencia LIMIT 1;

    SELECT rp.campania_id, rp.valor_protegido INTO v_despues, v_vd
      FROM agregado.resultado_protegido rp
      JOIN catalogo.campania c ON c.campania_id = rp.campania_id
     WHERE rp.unidad_organizacional_id = v_unidad AND rp.dimension_id IS NULL
       AND rp.estado_publicacion = 'PUBLICADO'
     ORDER BY c.secuencia DESC LIMIT 1;

    -- Mismo criterio que usa el sistema web: una diferencia menor que el
    -- ruido combinado no se reporta como efecto.
    v_concl := CASE
        WHEN abs(v_vd - v_va) <= 0.5 THEN 'NO_CONCLUYENTE'
        WHEN v_vd > v_va THEN 'MEJORA'
        ELSE 'DETERIORO' END;

    INSERT INTO intervencion.evaluacion
        (intervencion_id, campania_antes, campania_despues,
         valor_antes, valor_despues, conclusion, nota_metodologica)
    VALUES (v_plan, v_antes, v_despues, v_va, v_vd, v_concl,
            'Comparacion de valores protegidos ya publicados; no se recalculo sobre '
            'respuestas ni se consumio presupuesto adicional. Una diferencia menor '
            'que el ruido combinado de ambas mediciones no se reporta como efecto.');

    RAISE NOTICE 'Plan de ejemplo % creado para la unidad %', v_plan, v_unidad;
END $$;
