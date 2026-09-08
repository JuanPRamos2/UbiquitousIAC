-- Ejecutar como superusuario de PostgreSQL (por ejemplo postgres).
-- No ejecutar la aplicación web con este usuario.
-- Sustituya CAMBIAR_ESTA_CLAVE por un secreto almacenado fuera de git.

CREATE DATABASE library_db
    WITH OWNER = postgres
         ENCODING = 'UTF8'
         TEMPLATE = template0;

\connect library_db

CREATE ROLE library_user WITH LOGIN PASSWORD 'CAMBIAR_ESTA_CLAVE';

GRANT CONNECT ON DATABASE library_db TO library_user;
GRANT USAGE ON SCHEMA public TO library_user;

-- Tras cargar 01 a 06, otorgar privilegios mínimos (no superusuario):
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO library_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO library_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO library_user;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO library_user;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO library_user;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO library_user;
