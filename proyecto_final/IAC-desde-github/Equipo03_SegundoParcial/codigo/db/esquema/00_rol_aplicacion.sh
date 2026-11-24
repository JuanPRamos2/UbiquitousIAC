#!/bin/bash
# Crea el rol con el que se conecta la aplicación.
#
# Por qué un rol aparte del superusuario: la aplicación no necesita poder
# borrar tablas ni crear roles. Si una credencial de la aplicación se
# filtra, el daño queda acotado a lo que ese rol puede hacer. Esto es el
# principio de menor privilegio declarado en el documento de arquitectura
# de hardware, aplicado dentro de la base.
set -e

: "${PG_USUARIO:?falta PG_USUARIO}"
: "${PG_CLAVE:?falta PG_CLAVE}"

# Idempotente: en el contenedor el clúster siempre nace vacío, pero este
# mismo script se usa para cargar una instancia de PostgreSQL existente
# (scripts/arranque_base.sh), donde el rol puede ya estar creado.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${PG_USUARIO}') THEN
            ALTER ROLE ${PG_USUARIO} WITH LOGIN PASSWORD '${PG_CLAVE}'
                NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
                CONNECTION LIMIT 40;
        ELSE
            CREATE ROLE ${PG_USUARIO} WITH LOGIN PASSWORD '${PG_CLAVE}'
                NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
                CONNECTION LIMIT 40;
        END IF;
    END \$\$;
    COMMENT ON ROLE ${PG_USUARIO} IS
        'Rol de la aplicación. Sin privilegios de esquema; los permisos se otorgan en 09_permisos.sh';
EOSQL

echo "Rol ${PG_USUARIO} creado."
