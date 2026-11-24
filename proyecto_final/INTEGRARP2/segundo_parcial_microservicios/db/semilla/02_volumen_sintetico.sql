DO $$
DECLARE
    v_u TEXT[] := ARRAY['UO-OPS-CC-T1','UO-OPS-CC-T2','UO-OPS-CC-T3','UO-OPS-ST-N1',
                        'UO-OPS-ST-N2','UO-CAL-T1','UO-CAL-T2','UO-CAP-T1',
                        'UO-TI-T1','UO-RH-T1','UO-FIN-T1','UO-VTA-T1'];
    v_t INT[] := ARRAY[210,195,140,120,95,70,55,45,38,32,28,122];
    i INT; j INT; v_emp INT := 200; v_seud TEXT;
BEGIN
    FOR i IN 1..array_length(v_u,1) LOOP
        INSERT INTO organizacion.unidad_organizacional
          (unidad_organizacional_id,nombre,tipo,unidad_padre_id,nivel_jerarquico,plantilla_declarada)
        VALUES (v_u[i],'Unidad '||v_u[i],'TURNO','UO-OPERACIONES',1,v_t[i]);
        FOR j IN 1..v_t[i] LOOP
            v_emp := v_emp + 1;
            INSERT INTO usuarios.empleado
              (empleado_id,usuario_id,nombre,apellido_paterno,fecha_ingreso,unidad_organizacional_id)
            VALUES ('EMP-'||LPAD(v_emp::text,5,'0'),NULL,'Nombre'||v_emp,'Apellido'||v_emp,
                    DATE '2022-01-01' + (random()*1400)::int, v_u[i]);
            v_seud := 'SEUD-'||LPAD(v_emp::text,5,'0');
            INSERT INTO consentimiento.seudonimo (seudonimo_id,empleado_id)
            VALUES (v_seud,'EMP-'||LPAD(v_emp::text,5,'0'));
            INSERT INTO consentimiento.consentimiento (seudonimo_id,aviso_id,estado,fecha_evento)
            VALUES (v_seud,'AVISO-v1',CASE WHEN random()<0.82 THEN 'ACEPTADO' ELSE 'REVOCADO' END,
                    '2026-08-01 09:00:00-06'::timestamptz);
        END LOOP;
    END LOOP;
END $$;

INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id)
SELECT c.campania_id, u.unidad_organizacional_id
FROM catalogo.campania c CROSS JOIN organizacion.unidad_organizacional u
WHERE u.unidad_organizacional_id LIKE 'UO-%T%' ON CONFLICT DO NOTHING;

DO $$
DECLARE c RECORD; s RECORD; v_id BIGINT; rx RECORD; v_base NUMERIC;
BEGIN
  FOR c IN SELECT campania_id, secuencia FROM catalogo.campania ORDER BY secuencia LOOP
    FOR s IN SELECT sd.seudonimo_id, e.unidad_organizacional_id
             FROM consentimiento.seudonimo sd
             JOIN usuarios.empleado e ON e.empleado_id = sd.empleado_id
             JOIN consentimiento.v_estado_vigente ev ON ev.seudonimo_id = sd.seudonimo_id
             WHERE ev.estado='ACEPTADO' AND e.empleado_id LIKE 'EMP-0%'
    LOOP
      v_base := 3.9 - (c.secuencia-1)*0.18;
      INSERT INTO autoreporte.respuesta
        (seudonimo_id,campania_id,unidad_organizacional_id,aviso_id,fecha_respuesta)
      VALUES (s.seudonimo_id,c.campania_id,s.unidad_organizacional_id,'AVISO-v1',
              NOW() - (4-c.secuencia)*INTERVAL '7 days')
      ON CONFLICT DO NOTHING RETURNING respuesta_id INTO v_id;
      IF v_id IS NOT NULL THEN
        FOR rx IN SELECT reactivo_id FROM catalogo.reactivo LOOP
          INSERT INTO autoreporte.respuesta_detalle (respuesta_id,reactivo_id,valor)
          VALUES (v_id, rx.reactivo_id, GREATEST(1,LEAST(5,ROUND(v_base+(random()-0.5)*1.6)))::smallint);
        END LOOP;
      END IF;
    END LOOP;
  END LOOP;
END $$;
