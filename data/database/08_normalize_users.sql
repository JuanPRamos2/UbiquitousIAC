-- Normaliza users para el microservicio de login.
-- Idempotente: sirve tanto para volúmenes antiguos (full_name + role)
-- como para instalaciones nuevas (first_name + role_id).
BEGIN;

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE CHECK (name IN ('admin', 'client')),
    description TEXT
);

INSERT INTO roles (id, name, description) VALUES
    (1, 'admin', 'Administrador único de la librería'),
    (2, 'client', 'Usuario registrado')
ON CONFLICT (name) DO NOTHING;
SELECT setval('roles_id_seq', GREATEST((SELECT MAX(id) FROM roles), 1));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'first_name'
    ) THEN
        ALTER TABLE users ADD COLUMN first_name VARCHAR(80);
        ALTER TABLE users ADD COLUMN paternal_surname VARCHAR(80);
        ALTER TABLE users ADD COLUMN maternal_surname VARCHAR(80) DEFAULT '';
        ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(id);

        UPDATE users SET
            first_name = split_part(btrim(full_name), ' ', 1),
            paternal_surname = COALESCE(NULLIF(split_part(btrim(full_name), ' ', 2), ''), split_part(btrim(full_name), ' ', 1)),
            maternal_surname = COALESCE(
                NULLIF(btrim(regexp_replace(btrim(full_name), '^[^[:space:]]+[[:space:]]+[^[:space:]]+[[:space:]]*', '')), ''),
                ''
            )
        WHERE first_name IS NULL;

        UPDATE users SET paternal_surname = first_name
        WHERE paternal_surname IS NULL OR btrim(paternal_surname) = '';

        UPDATE users u
           SET role_id = r.id
          FROM roles r
         WHERE r.name = u.role
           AND u.role_id IS NULL;

        ALTER TABLE users ALTER COLUMN first_name SET NOT NULL;
        ALTER TABLE users ALTER COLUMN paternal_surname SET NOT NULL;
        ALTER TABLE users ALTER COLUMN maternal_surname SET NOT NULL;
        ALTER TABLE users ALTER COLUMN maternal_surname SET DEFAULT '';
        ALTER TABLE users ALTER COLUMN role_id SET NOT NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'role'
    ) THEN
        DROP VIEW IF EXISTS v_admin_unique;
        DROP VIEW IF EXISTS v_users;
        DROP TRIGGER IF EXISTS trg_users_single_admin ON users;
        DROP INDEX IF EXISTS ux_users_single_admin;
        DROP INDEX IF EXISTS idx_users_role;
        ALTER TABLE users DROP COLUMN role;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users'
          AND column_name = 'full_name' AND is_generated = 'NEVER'
    ) THEN
        ALTER TABLE users DROP COLUMN full_name;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'full_name'
    ) THEN
        ALTER TABLE users ADD COLUMN full_name VARCHAR(240) GENERATED ALWAYS AS (
            btrim(
                first_name || ' ' || paternal_surname ||
                CASE WHEN btrim(maternal_surname) = '' THEN '' ELSE ' ' || maternal_surname END
            )
        ) STORED;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users (role_id);
DROP INDEX IF EXISTS ux_users_single_admin;
CREATE UNIQUE INDEX ux_users_single_admin ON users (role_id) WHERE role_id = 1;

DROP VIEW IF EXISTS v_users;
CREATE VIEW v_users AS
SELECT u.id,
       u.first_name,
       u.paternal_surname,
       u.maternal_surname,
       u.full_name,
       u.email,
       u.password_hash,
       r.id AS role_id,
       r.name AS role,
       u.created_at,
       u.updated_at
FROM users u
JOIN roles r ON r.id = u.role_id;

COMMIT;
