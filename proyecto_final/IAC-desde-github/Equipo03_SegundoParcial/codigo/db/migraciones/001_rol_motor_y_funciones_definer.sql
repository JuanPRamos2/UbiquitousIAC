-- =====================================================================
-- Migración 001 — Rol motor y funciones con privilegios propios
--
-- PROBLEMA QUE RESUELVE
-- ---------------------
-- Al aplicar el principio de menor privilegio al rol de la aplicación
-- (09_permisos.sh), la aplicación quedó correctamente sin acceso a
-- autoreporte y sin poder escribir el presupuesto de privacidad. Pero
-- fn_calcular_agregado_protegido corría con los privilegios de quien la
-- llamaba, de modo que también dejó de funcionar:
--
--   ERROR: permission denied for schema autoreporte
--
-- La tentación es devolverle a la aplicación el permiso de lectura sobre
-- autoreporte. Eso destruiría la garantía: cualquier consulta de la
-- aplicación podría leer respuestas individuales y saltarse el
-- mecanismo de privacidad diferencial por completo.
--
-- SOLUCIÓN
-- --------
-- Un rol motor sin inicio de sesión, dueño de las funciones de dominio,
-- que sí puede leer respuestas y escribir el presupuesto. Las funciones
-- se marcan SECURITY DEFINER, de modo que corren con los privilegios del
-- motor y no con los de quien las invoca.
--
-- Resultado: la ÚNICA ruta desde la aplicación hacia los datos
-- individuales pasa por el mecanismo de privacidad diferencial. No es
-- una convención de programación; es una restricción del motor.
--
-- NOTA DE SEGURIDAD: toda función SECURITY DEFINER fija su search_path.
-- Sin eso, quien la invoca podría anteponer un esquema propio y hacer
-- que la función ejecute tablas o funciones suyas con los privilegios
-- del dueño. Es la vía clásica de escalación de privilegios en
-- PostgreSQL, y la razón de los SET search_path de más abajo.
-- =====================================================================

BEGIN;

-- 1. Rol motor: no puede iniciar sesión. Nadie se conecta como él.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bienestar_motor') THEN
        CREATE ROLE bienestar_motor NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END $$;

COMMENT ON ROLE bienestar_motor IS
    'Dueño de las funciones de dominio. Existe solo para prestar sus privilegios a las funciones SECURITY DEFINER. No tiene LOGIN.';

-- 2. Privilegios del motor: justo los que la aplicación NO debe tener.
GRANT USAGE ON SCHEMA autoreporte, agregado, catalogo, organizacion,
                      consentimiento, usuarios, riesgo, auditoria, gobernanza, portal
      TO bienestar_motor;

-- Leer respuestas individuales: esto es lo que la aplicación no puede hacer.
GRANT SELECT ON ALL TABLES IN SCHEMA autoreporte TO bienestar_motor;
GRANT SELECT ON ALL TABLES IN SCHEMA catalogo, organizacion, consentimiento,
                                     usuarios, riesgo, gobernanza, portal
      TO bienestar_motor;

-- Consumir presupuesto y publicar resultados: tampoco la aplicación.
GRANT SELECT, INSERT, UPDATE ON agregado.presupuesto_privacidad,
                                agregado.resultado_protegido,
                                agregado.consulta_privada
      TO bienestar_motor;
GRANT SELECT ON agregado.parametro_privacidad TO bienestar_motor;
-- Las vistas de agregado: el motor de reglas de riesgo lee la tendencia
-- para decidir si una condicion se sostiene durante varias campanias.
GRANT SELECT ON agregado.v_tendencia, agregado.v_tablero_unidad,
                agregado.v_estado_presupuesto
      TO bienestar_motor;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA agregado TO bienestar_motor;

-- Registrar detecciones de riesgo.
GRANT SELECT, INSERT, UPDATE ON riesgo.deteccion TO bienestar_motor;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA riesgo TO bienestar_motor;

-- Escribir bitácora. Nótese que tampoco el motor puede borrarla.
GRANT SELECT, INSERT ON auditoria.bitacora TO bienestar_motor;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA auditoria TO bienestar_motor;

-- 3. Las funciones pasan a ser del motor y a correr con sus privilegios.
ALTER FUNCTION agregado.fn_calcular_agregado_protegido(
        VARCHAR, VARCHAR, VARCHAR, VARCHAR)
    OWNER TO bienestar_motor;
ALTER FUNCTION agregado.fn_calcular_agregado_protegido(
        VARCHAR, VARCHAR, VARCHAR, VARCHAR)
    SECURITY DEFINER
    SET search_path = agregado, autoreporte, catalogo, organizacion,
                      consentimiento, usuarios, auditoria, pg_temp;

ALTER FUNCTION riesgo.fn_evaluar_unidad(VARCHAR, VARCHAR)
    OWNER TO bienestar_motor;
ALTER FUNCTION riesgo.fn_evaluar_unidad(VARCHAR, VARCHAR)
    SECURITY DEFINER
    SET search_path = riesgo, agregado, catalogo, organizacion, auditoria, pg_temp;

ALTER FUNCTION gobernanza.fn_verificar_garantias()
    OWNER TO bienestar_motor;
ALTER FUNCTION gobernanza.fn_verificar_garantias()
    SECURITY DEFINER
    SET search_path = gobernanza, agregado, autoreporte, catalogo,
                      organizacion, consentimiento, usuarios, portal, pg_temp;

-- Las funciones auxiliares son cálculo puro: no tocan tablas y no
-- necesitan privilegios prestados. Se dejan SECURITY INVOKER a propósito,
-- porque cada función SECURITY DEFINER es superficie de ataque.
--   agregado.fn_ruido_laplace, fn_analisis_utilidad, fn_clasificar_precision
-- La excepción es fn_parametro, que sí lee una tabla de configuración.
ALTER FUNCTION agregado.fn_parametro(VARCHAR) OWNER TO bienestar_motor;
ALTER FUNCTION agregado.fn_parametro(VARCHAR)
    SECURITY DEFINER
    SET search_path = agregado, pg_temp;

-- 4. Nadie puede ejecutar estas funciones por omisión; se otorga explícito.
REVOKE ALL ON FUNCTION agregado.fn_calcular_agregado_protegido(
        VARCHAR, VARCHAR, VARCHAR, VARCHAR) FROM PUBLIC;
REVOKE ALL ON FUNCTION riesgo.fn_evaluar_unidad(VARCHAR, VARCHAR) FROM PUBLIC;
REVOKE ALL ON FUNCTION gobernanza.fn_verificar_garantias() FROM PUBLIC;

COMMIT;
