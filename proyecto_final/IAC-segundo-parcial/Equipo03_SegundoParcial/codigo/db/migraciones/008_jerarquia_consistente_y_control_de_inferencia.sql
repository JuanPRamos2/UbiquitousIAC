-- =====================================================================
-- Migración 008 — Jerarquía consistente y acciones del control de inferencia
--
-- Corrige un defecto de datos y agrega la garantía que lo habría
-- detectado, más los códigos de bitácora que necesita el nuevo control de
-- consultas de queries-service.
--
-- -------------------------------------------------------------------
-- 1. EL DEFECTO: una unidad padre más pequeña que sus hijas
-- -------------------------------------------------------------------
-- UO-OPERACIONES es la raíz del árbol organizacional y declaraba una
-- plantilla de 120 personas. Sus quince unidades hijas declaran, sumadas,
-- 1,186. Una dirección no puede tener menos gente que la suma de las áreas
-- que cuelgan de ella.
--
-- Pasó inadvertido porque ninguna pantalla suma el árbol: todas consultan
-- una unidad a la vez, y vista sola cada unidad es coherente. El dato
-- estaba mal desde los datos sintéticos iniciales.
--
-- Importa por dos razones concretas, no por prolijidad:
--
--   a) El control de inferencia que se agrega en queries-service calcula
--      «residuo = plantilla del padre − suma de las hijas ya consultadas»
--      para decidir si una consulta permitiría aislar a un grupo. Con el
--      padre declarando 120 y las hijas 1,186, ese residuo sale negativo y
--      el control nunca se dispara. Es decir: el defecto de datos dejaba
--      SIN EFECTO el mecanismo que protege de los ataques por diferencia.
--
--   b) Cualquier lectura futura que agregue hacia arriba —cobertura de la
--      dirección, participación global— daría porcentajes por encima de
--      100 sin que nada fallara.
--
-- El valor correcto es la suma de las hijas: la dirección se compone de
-- sus áreas y no tiene plantilla propia (cero empleados asignados
-- directamente, lo cual es correcto para una unidad de agrupación).
-- =====================================================================

BEGIN;

-- Red de seguridad para bases YA creadas con el dato viejo. En una base
-- nueva no hace nada: la correccion de fondo esta en la semilla
-- db/semilla/02_volumen_sintetico.sql, que es donde se crean las hijas.
-- Aqui no alcanza, porque las migraciones corren ANTES que las semillas y
-- este UPDATE lo pisaria la semilla al cargar.
UPDATE organizacion.unidad_organizacional AS padre
   SET plantilla_declarada = (
         SELECT coalesce(sum(hija.plantilla_declarada), 0)
           FROM organizacion.unidad_organizacional AS hija
          WHERE hija.unidad_padre_id = padre.unidad_organizacional_id)
 WHERE EXISTS (SELECT 1 FROM organizacion.unidad_organizacional AS h
                WHERE h.unidad_padre_id = padre.unidad_organizacional_id)
   AND padre.plantilla_declarada < (
         SELECT coalesce(sum(hija.plantilla_declarada), 0)
           FROM organizacion.unidad_organizacional AS hija
          WHERE hija.unidad_padre_id = padre.unidad_organizacional_id);

-- -------------------------------------------------------------------
-- 2. LA GARANTÍA QUE LO HABRÍA DETECTADO
-- -------------------------------------------------------------------
-- Se agrega a gobernanza.fn_verificar_garantias(), que es la consulta que
-- el proyecto ya corre para comprobar sus propias promesas. Corregir el
-- dato sin agregar la verificación dejaría el mismo error libre de
-- reaparecer en la siguiente carga de datos.
--
-- Se declara como garantía y no como restricción CHECK porque una
-- restricción se evalúa fila por fila y esta condición es del conjunto:
-- al insertar las hijas una por una, cualquier orden pasaría por estados
-- intermedios inválidos y la carga fallaría sin que nada estuviera mal.
-- =====================================================================

CREATE OR REPLACE FUNCTION gobernanza.fn_jerarquia_consistente()
RETURNS TABLE (unidad VARCHAR, declarada INTEGER, suma_hijas BIGINT) AS $$
    SELECT padre.unidad_organizacional_id,
           padre.plantilla_declarada,
           coalesce(sum(hija.plantilla_declarada), 0)
      FROM organizacion.unidad_organizacional AS padre
      JOIN organizacion.unidad_organizacional AS hija
        ON hija.unidad_padre_id = padre.unidad_organizacional_id
     GROUP BY padre.unidad_organizacional_id, padre.plantilla_declarada
    HAVING padre.plantilla_declarada < coalesce(sum(hija.plantilla_declarada), 0);
$$ LANGUAGE sql STABLE;

COMMENT ON FUNCTION gobernanza.fn_jerarquia_consistente IS
  'Devuelve las unidades padre cuya plantilla declarada es menor que la suma de sus hijas. Debe devolver cero filas: un padre mas pequeno que sus hijas deja sin efecto el control de inferencia por diferencia.';

-- -------------------------------------------------------------------
-- 3. LOS CÓDIGOS DE BITÁCORA DEL NUEVO CONTROL
-- -------------------------------------------------------------------
-- auditoria.bitacora tiene llave foránea contra auditoria.tipo_accion y
-- contra auditoria.resultado. Un código que no esté aquí hace fallar la
-- inserción, y como el registro va envuelto en un try para no tumbar la
-- operación principal, falla en silencio.
-- =====================================================================

INSERT INTO auditoria.tipo_accion (codigo, descripcion, sensible) VALUES
  ('CONSULTA_REPETIDA',
   'Un mismo actor repitio la misma consulta un numero anormal de veces '
   'dentro de la ventana de observacion. No rompe nada por si solo: '
   'describe a alguien explorando, y de eso tiene que quedar rastro.',
   TRUE),
  ('CONSULTA_BLOQUEADA',
   'Se nego una consulta porque, combinada con las que ese actor ya habia '
   'hecho, habria permitido aislar un grupo por debajo del umbral k '
   '(ataque por diferencia).',
   TRUE)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO auditoria.resultado (codigo, descripcion) VALUES
  ('DETECTADO',
   'La operacion se permitio, pero se detecto un patron que merece quedar '
   'registrado. No es exito ni rechazo: es una observacion.')
ON CONFLICT (codigo) DO NOTHING;

COMMIT;

-- Verificación:
--   SELECT * FROM gobernanza.fn_jerarquia_consistente();   -- cero filas
--   SELECT codigo FROM auditoria.tipo_accion
--    WHERE codigo IN ('CONSULTA_REPETIDA','CONSULTA_BLOQUEADA');
