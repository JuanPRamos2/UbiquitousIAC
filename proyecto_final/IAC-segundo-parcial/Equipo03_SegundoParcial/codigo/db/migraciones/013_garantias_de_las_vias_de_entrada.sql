-- =====================================================================
-- 013 — Dos garantías más, para las vías de entrada nuevas
--
-- QUÉ AGREGA, Y POR QUÉ NO ESTABA
-- --------------------------------
-- `gobernanza.fn_verificar_garantias()` comprueba contra el catálogo del
-- sistema que las garantías del proyecto se sostienen **a nivel de
-- modelo** y no solo de interfaz. Las seis que tenía cubrían lo que
-- existía cuando se escribió: intervenciones, autoreporte, riesgo,
-- agregación y catálogos.
--
-- Las migraciones 011 y 012 abrieron dos vías de entrada nuevas —la
-- sincronización desde los clientes y la integración corporativa— y
-- ninguna garantía las miraba. Eso importa más de lo que parece, porque
-- las dos vías existen justamente para **recibir datos de fuera**, y
-- `integration-service` se conecta a un sistema que tiene los nombres,
-- los puestos y los sueldos de toda la organización.
--
-- POR QUÉ UNA GARANTÍA Y NO SOLO EL FILTRO DEL SERVICIO
-- ------------------------------------------------------
-- `integration-service` ya rechaza los campos de persona que lleguen en
-- un archivo. Pero ese filtro es código de un servicio, y protege de lo
-- que entra por ese servicio. Lo que estas dos garantías comprueban es
-- otra cosa: que **no haya dónde guardarlos**.
--
-- La diferencia se ve al imaginar el futuro probable. Alguien agrega una
-- columna `nombre_empleado` a `integracion.identificador_externo` «para
-- depurar», y el filtro del servicio sigue funcionando perfectamente: no
-- deja entrar el campo por la API. Pero la columna ya está, y la
-- siguiente persona que necesite un nombre la va a llenar por otra vía.
-- Una garantía contra el catálogo del sistema falla el día que se crea la
-- columna, que es el día en que hay que discutirlo.
--
-- Es el mismo razonamiento de G1: la intervención no puede dirigirse a
-- una persona porque `intervencion.plan` no tiene columna para una, no
-- porque el servicio se acuerde de no permitirlo.
-- =====================================================================

BEGIN;

CREATE OR REPLACE FUNCTION gobernanza.fn_verificar_garantias()
RETURNS TABLE (garantia TEXT, cumple BOOLEAN, detalle TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT 'G1 Intervenciones sin persona objetivo'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='intervencion'
                         AND (column_name ILIKE '%empleado%'
                              OR column_name ILIKE '%seudonimo%')),
           'Ninguna tabla del esquema intervencion admite un empleado o seudonimo objetivo.'::TEXT;

    RETURN QUERY
    SELECT 'G2 Autoreporte sin identidad'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='autoreporte'
                         AND column_name ILIKE '%empleado%'),
           'Ninguna tabla de autoreporte contiene empleado_id: solo seudonimo.'::TEXT;

    RETURN QUERY
    SELECT 'G3 Sin puntaje individual publicable'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema IN ('riesgo','agregado')
                         AND (column_name ILIKE '%seudonimo%'
                              OR column_name ILIKE '%empleado%')),
           'Los esquemas de riesgo y agregacion no pueden referirse a una persona: operan solo sobre unidades.'::TEXT;

    RETURN QUERY
    SELECT 'G4 Toda publicacion lleva epsilon'::TEXT,
           NOT EXISTS (SELECT 1 FROM agregado.resultado_protegido
                       WHERE estado_publicacion='PUBLICADO'
                         AND epsilon_aplicado IS NULL),
           'Ningun resultado publicado carece de mecanismo de privacidad diferencial aplicado.'::TEXT;

    RETURN QUERY
    SELECT 'G5 Toda publicacion respeta el umbral k'::TEXT,
           NOT EXISTS (SELECT 1 FROM agregado.resultado_protegido
                       WHERE estado_publicacion='PUBLICADO'
                         AND n_observaciones < k_aplicado),
           'Ningun resultado publicado proviene de un grupo menor que k.'::TEXT;

    RETURN QUERY
    SELECT 'G6 Fuentes de vigilancia bloqueadas'::TEXT,
           NOT EXISTS (SELECT 1 FROM catalogo.instrumento i
                       JOIN catalogo.fuente_autorizada f ON f.fuente_id=i.fuente_id
                       WHERE NOT f.autorizada),
           'Ningun instrumento se alimenta de una fuente marcada como no autorizada.'::TEXT;

    -- ------------------------------------------------------------------
    -- G7 — La puerta corporativa no tiene dónde guardar una persona
    -- ------------------------------------------------------------------
    -- `integracion.identificador_externo` guarda dos cadenas opacas: el
    -- identificador que usa el sistema corporativo y el seudónimo
    -- interno. Si además guardara el nombre, el correo o el número de
    -- empleado, las tres cosas juntas reconstruirían la identificación
    -- completa, que es exactamente lo que la seudonimización evita.
    --
    -- `seudonimo_id` sí se admite —es la mitad de la correspondencia y la
    -- razón de ser de la tabla—, así que la comprobación busca lo otro.
    RETURN QUERY
    SELECT 'G7 Integracion sin datos de persona'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='integracion'
                         AND (column_name ILIKE '%empleado%'
                              OR column_name ILIKE '%correo%'
                              OR column_name ILIKE '%curp%'
                              OR column_name ILIKE '%rfc%'
                              OR column_name ILIKE '%salario%'
                              OR column_name ILIKE '%sueldo%'
                              OR column_name ILIKE '%puesto%'
                              OR column_name ILIKE '%telefono%'
                              OR column_name ILIKE '%nacimiento%'
                              -- 'nombre' a secas se usa para el nombre de
                              -- una FUENTE, que no es dato de persona. Se
                              -- buscan las formas que sí lo serian.
                              OR column_name ILIKE '%nombre_empleado%'
                              OR column_name ILIKE '%nombre_persona%'
                              OR column_name ILIKE '%nombre_completo%'
                              OR column_name ILIKE '%apellido%')),
           'El esquema integracion no tiene donde guardar un dato de persona. El filtro del servicio protege de lo que ENTRA; esto comprueba que no haya DONDE ponerlo, que es lo que sigue siendo cierto el dia que alguien agregue una columna «para depurar».'::TEXT;

    -- ------------------------------------------------------------------
    -- G8 — La sincronización va por seudónimo
    -- ------------------------------------------------------------------
    -- `sincronizacion.operacion` registra qué operación se aplicó, y lo
    -- hace con el seudónimo. Un `empleado_id` aquí, junto al
    -- `campania_id` y al resultado, sería un vínculo
    -- persona-respuesta-campaña en una tabla que el rol de la aplicación
    -- lee sin restricción: justo lo que G2 evita en autoreporte.
    RETURN QUERY
    SELECT 'G8 Sincronizacion sin identidad'::TEXT,
           NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='sincronizacion'
                         AND column_name ILIKE '%empleado%'),
           'Ninguna tabla de sincronizacion contiene empleado_id: la memoria de operaciones va por seudonimo. Un empleado_id junto al campania_id y al resultado seria un vinculo persona-respuesta-campania en una tabla de lectura libre para el rol de la aplicacion.'::TEXT;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION gobernanza.fn_verificar_garantias IS
  'Verifica contra el catalogo del sistema que las garantias de privacidad '
  'se sostienen a nivel de modelo y no solo de interfaz. Ocho garantias: '
  'las seis originales mas G7 y G8, que cubren las dos vias de entrada '
  'que abrieron las migraciones 011 y 012. Se ejecuta durante la '
  'demostracion.';

-- Los privilegios se vuelven a otorgar: CREATE OR REPLACE conserva los
-- del objeto, pero dejarlo explícito evita que una base creada en otro
-- orden se quede sin ellos.
GRANT EXECUTE ON FUNCTION gobernanza.fn_verificar_garantias() TO bienestar_app;

COMMIT;

-- Verificación:
--
--   SELECT * FROM gobernanza.fn_verificar_garantias();
--   -- Ocho renglones, los ocho en true.
--
--   -- Y la comprobación de que G7 de verdad protege: agregar una columna
--   -- de persona al esquema integracion tiene que hacerla fallar.
--   -- (No ejecutar en una base que importe; es para entender la garantia.)
--   --   ALTER TABLE integracion.fuente ADD COLUMN correo_contacto TEXT;
--   --   SELECT * FROM gobernanza.fn_verificar_garantias() WHERE NOT cumple;
--   --   ALTER TABLE integracion.fuente DROP COLUMN correo_contacto;
