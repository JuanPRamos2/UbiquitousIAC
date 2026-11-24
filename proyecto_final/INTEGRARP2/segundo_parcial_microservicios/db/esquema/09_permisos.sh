#!/bin/bash
# Otorga a la aplicación exactamente lo que necesita, y nada más.
#
# Decisiones que este archivo hace cumplir, y que sostienen las garantías
# G1 a G6 verificadas por gobernanza.fn_verificar_garantias():
#
#   - La aplicación NO puede leer directamente autoreporte.respuesta ni
#     autoreporte.respuesta_detalle. Solo puede invocar la función de
#     agregado protegido. Así, ni siquiera un error de programación en la
#     aplicación puede devolver respuestas individuales.
#   - La aplicación NO puede borrar de auditoria.bitacora. Una bitácora
#     que el servicio puede borrar no sirve como evidencia.
#   - La aplicación NO puede alterar el presupuesto de privacidad por
#     fuera de la función. El consumo de epsilon solo ocurre dentro del
#     mecanismo, nunca por un UPDATE de la aplicación.
set -e

: "${PG_USUARIO:?falta PG_USUARIO}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Conexión y uso de esquemas de lectura
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${PG_USUARIO};
    GRANT USAGE ON SCHEMA catalogo, organizacion, usuarios, agregado,
                          consentimiento, riesgo, intervencion,
                          transparencia, gobernanza, auditoria, portal
          TO ${PG_USUARIO};

    -- Lectura de catálogos y estructura
    GRANT SELECT ON ALL TABLES IN SCHEMA catalogo, organizacion,
                                        transparencia, gobernanza
          TO ${PG_USUARIO};

    -- Usuarios y perfiles: leer para autenticar y resolver permisos
    GRANT SELECT ON usuarios.usuario, usuarios.perfil, usuarios.permiso,
                    usuarios.perfil_permiso, usuarios.usuario_perfil,
                    usuarios.empleado
          TO ${PG_USUARIO};
    -- Alta de usuarios y asignacion de perfiles (users-service). Esto NO
    -- debilita la garantia central: administrar cuentas no da acceso al
    -- contenido de las respuestas, porque el permiso de lectura sobre el
    -- esquema autoreporte sigue negado. Se otorga INSERT y UPDATE, nunca
    -- DELETE: un usuario se inactiva, no se borra, para que la bitacora
    -- siga pudiendo explicar quien hizo que.
    GRANT INSERT, UPDATE ON usuarios.usuario TO ${PG_USUARIO};
    GRANT INSERT, UPDATE, DELETE ON usuarios.usuario_perfil TO ${PG_USUARIO};

    -- Consentimiento: registrar eventos y consultar el estado vigente
    GRANT SELECT ON consentimiento.aviso_privacidad TO ${PG_USUARIO};
    GRANT SELECT, INSERT ON consentimiento.consentimiento TO ${PG_USUARIO};
    GRANT SELECT ON consentimiento.v_estado_vigente TO ${PG_USUARIO};
    GRANT USAGE ON SEQUENCE consentimiento.consentimiento_consentimiento_id_seq
          TO ${PG_USUARIO};

    -- Autorreporte: SOLO insertar. Nunca leer respuestas individuales.
    GRANT INSERT ON autoreporte.respuesta, autoreporte.respuesta_detalle
          TO ${PG_USUARIO};
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA autoreporte TO ${PG_USUARIO};
    -- El portal expone al colaborador solo su propia participación,
    -- sin identificador de empleado. Esa vista sí se puede leer.
    GRANT SELECT ON ALL TABLES IN SCHEMA portal TO ${PG_USUARIO};

    -- Agregados: leer resultados publicados e invocar el mecanismo.
    GRANT SELECT ON agregado.resultado_protegido, agregado.parametro_privacidad,
                    agregado.consulta_privada, agregado.presupuesto_privacidad
          TO ${PG_USUARIO};
    -- Las vistas de agregado solo reorganizan tablas que la aplicacion ya
    -- puede leer; no exponen nada nuevo, pero necesitan permiso explicito.
    GRANT SELECT ON agregado.v_tablero_unidad, agregado.v_tendencia,
                    agregado.v_estado_presupuesto
          TO ${PG_USUARIO};
    -- Sin INSERT, UPDATE ni DELETE sobre el presupuesto: el epsilon solo
    -- se consume dentro de la función, que corre con privilegios propios.

    -- Riesgo e intervención
    GRANT SELECT ON ALL TABLES IN SCHEMA riesgo TO ${PG_USUARIO};
    GRANT SELECT, INSERT, UPDATE ON intervencion.plan, intervencion.seguimiento,
                                    intervencion.evaluacion
          TO ${PG_USUARIO};
    GRANT SELECT ON intervencion.tipo_intervencion TO ${PG_USUARIO};
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA intervencion, riesgo TO ${PG_USUARIO};

    -- Auditoría: escribir sí, borrar nunca.
    GRANT SELECT, INSERT ON auditoria.bitacora TO ${PG_USUARIO};
    GRANT SELECT ON auditoria.tipo_accion, auditoria.resultado TO ${PG_USUARIO};
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA auditoria TO ${PG_USUARIO};

    -- Funciones del dominio
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA agregado, riesgo, gobernanza,
                                             consentimiento, auditoria
          TO ${PG_USUARIO};

    -- Nada de lo que se cree después hereda permisos por accidente.
    ALTER DEFAULT PRIVILEGES IN SCHEMA autoreporte
        REVOKE SELECT ON TABLES FROM ${PG_USUARIO};
EOSQL

echo "Permisos otorgados a ${PG_USUARIO} (menor privilegio)."
