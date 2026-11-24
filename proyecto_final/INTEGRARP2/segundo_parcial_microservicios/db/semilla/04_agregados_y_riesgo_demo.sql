-- =====================================================================
-- Precalculo de agregados protegidos y evaluacion de riesgo
--
-- En operacion normal esto ocurre al CERRAR una campania: se calculan una
-- sola vez los agregados de todas las unidades y las consultas posteriores
-- se sirven desde la tabla de resultados protegidos. Es la recomendacion
-- del documento de rendimiento, y tiene una consecuencia favorable en
-- privacidad: reduce el numero de consultas que consumen presupuesto.
--
-- Aqui se ejecuta sobre las campanias ya cerradas para que la demostracion
-- tenga tendencias, detecciones de riesgo y material de evaluacion desde
-- el primer arranque.
--
-- Nota sobre presupuesto: cada combinacion campania/unidad tiene 8.0 de
-- epsilon y cada consulta consume 1.0. Se calcula el indice global mas las
-- dimensiones, lo que cabe dentro del presupuesto sin agotarlo.
-- =====================================================================

DO $$
DECLARE
    c RECORD; u RECORD; d RECORD;
    v_actor VARCHAR := 'USR-00003';   -- especialista de bienestar
BEGIN
    FOR c IN SELECT campania_id FROM catalogo.campania
              WHERE estado = 'CERRADA' ORDER BY secuencia
    LOOP
        FOR u IN SELECT cu.unidad_organizacional_id
                   FROM catalogo.campania_unidad cu
                   JOIN organizacion.unidad_organizacional o
                     ON o.unidad_organizacional_id = cu.unidad_organizacional_id
                  WHERE cu.campania_id = c.campania_id AND o.activa
        LOOP
            -- Indice global de la unidad.
            PERFORM agregado.fn_calcular_agregado_protegido(
                c.campania_id, u.unidad_organizacional_id, NULL, v_actor);

            -- Y cada dimension, que es lo que alimenta el motor de reglas.
            FOR d IN SELECT dimension_id FROM catalogo.dimension ORDER BY orden
            LOOP
                PERFORM agregado.fn_calcular_agregado_protegido(
                    c.campania_id, u.unidad_organizacional_id, d.dimension_id, v_actor);
            END LOOP;

            -- Con los agregados publicados ya se puede evaluar el riesgo.
            PERFORM riesgo.fn_evaluar_unidad(u.unidad_organizacional_id, c.campania_id);
        END LOOP;
    END LOOP;
END $$;
