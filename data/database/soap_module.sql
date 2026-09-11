-- Módulo SOAP: tablas propias, vistas, procedimientos y privilegios mínimos.
-- No altera la estructura de books, concepts, book_concepts, categories ni users.
-- Ejecutar contra library_db (o el nombre de la BD del monolito) como un rol con CREATE.

BEGIN;

CREATE TABLE IF NOT EXISTS clasificadores (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(80)  NOT NULL,
    apellidos       VARCHAR(120) NOT NULL,
    correo          VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_clasificadores_correo UNIQUE (correo),
    CONSTRAINT ck_clasificadores_correo CHECK (correo ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$')
);

CREATE TABLE IF NOT EXISTS clasificaciones_cloud (
    id               SERIAL PRIMARY KEY,
    clasificador_id  INTEGER      NOT NULL REFERENCES clasificadores(id) ON DELETE RESTRICT,
    concept_id       INTEGER      NOT NULL REFERENCES concepts(id) ON DELETE RESTRICT,
    isbn             VARCHAR(17)  NOT NULL REFERENCES books(isbn) ON DELETE RESTRICT,
    modelo           VARCHAR(10)  NOT NULL,
    tipo_cliente     VARCHAR(50)  NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_clasificaciones_modelo CHECK (modelo IN ('IaaS', 'PaaS', 'SaaS', 'FaaS')),
    CONSTRAINT uq_clasificacion_unica UNIQUE (clasificador_id, concept_id)
);

CREATE TABLE IF NOT EXISTS clientes_servidos (
    id               SERIAL PRIMARY KEY,
    tipo_cliente     VARCHAR(50)  NOT NULL,
    identificador    VARCHAR(120) NOT NULL,
    peticiones       INTEGER      NOT NULL DEFAULT 0,
    ultima_peticion  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_clientes_servidos_tipo UNIQUE (tipo_cliente),
    CONSTRAINT ck_clientes_peticiones CHECK (peticiones >= 0)
);

CREATE INDEX IF NOT EXISTS idx_clasificaciones_isbn ON clasificaciones_cloud (isbn);
CREATE INDEX IF NOT EXISTS idx_clasificaciones_modelo ON clasificaciones_cloud (modelo);
CREATE INDEX IF NOT EXISTS idx_clasificaciones_clasificador ON clasificaciones_cloud (clasificador_id);
CREATE INDEX IF NOT EXISTS idx_clasificadores_correo ON clasificadores (correo);

COMMENT ON TABLE clasificadores IS 'Identidad del usuario del cliente SOAP. Independiente de users del monolito.';
COMMENT ON TABLE clasificaciones_cloud IS 'Resultado de clasificar un concepto del catálogo como modelo Cloud.';
COMMENT ON TABLE clientes_servidos IS 'Auditoría de tipos de cliente de escritorio y peticiones atendidas.';
COMMENT ON CONSTRAINT uq_clasificacion_unica ON clasificaciones_cloud IS
    'Impide que el mismo clasificador registre dos veces el mismo concepto.';

-- Vista de sólo lectura: expone al servicio lo necesario del catálogo, no el esquema interno.
CREATE OR REPLACE VIEW v_catalogo_conceptos AS
SELECT
    c.id              AS concept_id,
    c.name            AS concept_name,
    bc.definition     AS definition,
    b.isbn            AS isbn,
    b.title           AS book_title,
    cat.name          AS category_name
FROM book_concepts bc
JOIN concepts c     ON c.id = bc.concept_id
JOIN books b        ON b.id = bc.book_id
JOIN categories cat ON cat.id = b.category_id;

COMMENT ON VIEW v_catalogo_conceptos IS
    'Contrato de lectura del módulo SOAP. Oculta price, stock, users, password_hash e imágenes.';

CREATE OR REPLACE FUNCTION sp_upsert_clasificador(
    p_nombre    VARCHAR,
    p_apellidos VARCHAR,
    p_correo    VARCHAR
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_id INTEGER;
BEGIN
    INSERT INTO clasificadores (nombre, apellidos, correo)
    VALUES (p_nombre, p_apellidos, lower(p_correo))
    ON CONFLICT (correo) DO UPDATE
        SET nombre = EXCLUDED.nombre,
            apellidos = EXCLUDED.apellidos
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION sp_registrar_cliente_servido(
    p_tipo_cliente  VARCHAR,
    p_identificador VARCHAR
) RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO clientes_servidos (tipo_cliente, identificador, peticiones, ultima_peticion)
    VALUES (p_tipo_cliente, p_identificador, 1, NOW())
    ON CONFLICT (tipo_cliente) DO UPDATE
        SET peticiones = clientes_servidos.peticiones + 1,
            identificador = EXCLUDED.identificador,
            ultima_peticion = NOW();
END;
$$;

CREATE OR REPLACE FUNCTION sp_obtener_conceptos_pendientes(p_correo VARCHAR)
RETURNS TABLE (
    concept_id    INTEGER,
    concept_name  VARCHAR,
    definition    TEXT,
    isbn          VARCHAR,
    book_title    VARCHAR,
    category_name VARCHAR
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT v.concept_id, v.concept_name, v.definition, v.isbn, v.book_title, v.category_name
    FROM v_catalogo_conceptos v
    WHERE NOT EXISTS (
        SELECT 1
        FROM clasificaciones_cloud cc
        JOIN clasificadores cl ON cl.id = cc.clasificador_id
        WHERE cl.correo = lower(p_correo)
          AND cc.concept_id = v.concept_id
    )
    ORDER BY v.category_name, v.book_title, v.concept_name;
END;
$$;

CREATE OR REPLACE FUNCTION sp_registrar_clasificacion(
    p_nombre        VARCHAR,
    p_apellidos     VARCHAR,
    p_correo        VARCHAR,
    p_concept_id    INTEGER,
    p_isbn          VARCHAR,
    p_modelo        VARCHAR,
    p_tipo_cliente  VARCHAR
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_clasificador_id INTEGER;
    v_id              INTEGER;
    v_existe          BOOLEAN;
BEGIN
    IF p_modelo NOT IN ('IaaS', 'PaaS', 'SaaS', 'FaaS') THEN
        RAISE EXCEPTION 'MODELO_INVALIDO' USING ERRCODE = '22023';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM v_catalogo_conceptos v
        WHERE v.concept_id = p_concept_id
          AND v.isbn = p_isbn
    ) INTO v_existe;

    IF NOT v_existe THEN
        RAISE EXCEPTION 'CONCEPTO_INEXISTENTE' USING ERRCODE = 'P0002';
    END IF;

    v_clasificador_id := sp_upsert_clasificador(p_nombre, p_apellidos, p_correo);

    INSERT INTO clasificaciones_cloud (
        clasificador_id, concept_id, isbn, modelo, tipo_cliente
    ) VALUES (
        v_clasificador_id, p_concept_id, p_isbn, p_modelo, p_tipo_cliente
    )
    RETURNING id INTO v_id;

    PERFORM sp_registrar_cliente_servido(p_tipo_cliente, lower(p_correo));
    RETURN v_id;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'CLASIFICACION_DUPLICADA' USING ERRCODE = '23505';
END;
$$;

CREATE OR REPLACE FUNCTION sp_obtener_progreso_usuario(p_correo VARCHAR)
RETURNS TABLE (
    correo          VARCHAR,
    nombre_completo TEXT,
    clasificados    INTEGER,
    pendientes      INTEGER,
    total_catalogo  INTEGER
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_total INTEGER;
    v_done  INTEGER;
BEGIN
    SELECT COUNT(DISTINCT concept_id)::INTEGER INTO v_total FROM v_catalogo_conceptos;
    SELECT COUNT(*)::INTEGER INTO v_done
    FROM clasificaciones_cloud cc
    JOIN clasificadores cl ON cl.id = cc.clasificador_id
    WHERE cl.correo = lower(p_correo);

    RETURN QUERY
    SELECT
        COALESCE((SELECT cl.correo FROM clasificadores cl WHERE cl.correo = lower(p_correo)), lower(p_correo)),
        COALESCE((
            SELECT cl.nombre || ' ' || cl.apellidos
            FROM clasificadores cl
            WHERE cl.correo = lower(p_correo)
        ), 'Sin registros'),
        v_done,
        GREATEST(v_total - v_done, 0),
        v_total;
END;
$$;

CREATE OR REPLACE FUNCTION sp_obtener_estadisticas_por_modelo()
RETURNS TABLE (
    modelo   VARCHAR,
    cantidad INTEGER
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT m.modelo, COUNT(cc.id)::INTEGER
    FROM (VALUES ('IaaS'), ('PaaS'), ('SaaS'), ('FaaS')) AS m(modelo)
    LEFT JOIN clasificaciones_cloud cc ON cc.modelo = m.modelo
    GROUP BY m.modelo
    ORDER BY m.modelo;
END;
$$;

CREATE OR REPLACE FUNCTION sp_concepto_existe(p_concept_id INTEGER)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (SELECT 1 FROM v_catalogo_conceptos WHERE concept_id = p_concept_id);
$$;

-- Conceptos Cloud de demostración (INSERT, no ALTER). Enriquecen el catálogo real
-- para que el clasificador de escritorio tenga evidencia IaaS/PaaS/SaaS/FaaS.
INSERT INTO concepts (name, description) VALUES
    ('Máquinas virtuales', 'Recursos de cómputo virtualizados que el usuario administra.'),
    ('Plataforma de despliegue', 'Entorno para publicar aplicaciones sin administrar servidores.'),
    ('Correo en el navegador', 'Software de productividad consumido como servicio.'),
    ('Función serverless', 'Ejecución de una función en respuesta a un evento, sin servidor permanente.')
ON CONFLICT (name) DO NOTHING;

INSERT INTO book_concepts (book_id, concept_id, definition)
SELECT b.id, c.id, data.definition
FROM (VALUES
    ('9780132350884', 'Máquinas virtuales',
     'Infraestructura con máquinas virtuales, almacenamiento y redes para instalar el propio sistema operativo.'),
    ('9780132350884', 'Plataforma de despliegue',
     'Desplegar la aplicación web sin administrar directamente servidores ni sistemas operativos.'),
    ('9780062316097', 'Correo en el navegador',
     'Los empleados utilizan una aplicación de correo electrónico desde el navegador con suscripción mensual.'),
    ('9780307474728', 'Función serverless',
     'Ejecutar una función automáticamente cada vez que un usuario suba una imagen al almacenamiento Cloud.')
) AS data(isbn, concept_name, definition)
JOIN books b ON b.isbn = data.isbn
JOIN concepts c ON c.name = data.concept_name
ON CONFLICT (book_id, concept_id) DO UPDATE
    SET definition = EXCLUDED.definition;

COMMIT;

-- Privilegios: ejecutar como postgres después del COMMIT anterior si el rol aún no existe.
-- El password NO va en este archivo. Asígnalo con:
--   ALTER ROLE soap_user PASSWORD '...';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'soap_user') THEN
        CREATE ROLE soap_user LOGIN PASSWORD 'cambia_esta_clave_en_el_servidor';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO soap_user;

GRANT SELECT ON books, concepts, book_concepts, categories, v_catalogo_conceptos TO soap_user;
GRANT SELECT, INSERT, UPDATE ON clasificadores, clasificaciones_cloud, clientes_servidos TO soap_user;
GRANT USAGE, SELECT ON SEQUENCE clasificadores_id_seq, clasificaciones_cloud_id_seq, clientes_servidos_id_seq TO soap_user;

GRANT EXECUTE ON FUNCTION sp_upsert_clasificador(VARCHAR, VARCHAR, VARCHAR) TO soap_user;
GRANT EXECUTE ON FUNCTION sp_registrar_cliente_servido(VARCHAR, VARCHAR) TO soap_user;
GRANT EXECUTE ON FUNCTION sp_obtener_conceptos_pendientes(VARCHAR) TO soap_user;
GRANT EXECUTE ON FUNCTION sp_registrar_clasificacion(VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR) TO soap_user;
GRANT EXECUTE ON FUNCTION sp_obtener_progreso_usuario(VARCHAR) TO soap_user;
GRANT EXECUTE ON FUNCTION sp_obtener_estadisticas_por_modelo() TO soap_user;
GRANT EXECUTE ON FUNCTION sp_concepto_existe(INTEGER) TO soap_user;

REVOKE ALL ON users FROM soap_user;
REVOKE ALL ON images FROM soap_user;
REVOKE ALL ON book_images FROM soap_user;
REVOKE ALL ON book_authors FROM soap_user;
REVOKE ALL ON book_genres FROM soap_user;
REVOKE ALL ON authors FROM soap_user;
REVOKE ALL ON genres FROM soap_user;
REVOKE ALL ON formats FROM soap_user;
