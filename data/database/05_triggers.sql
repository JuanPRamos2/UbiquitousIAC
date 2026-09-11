BEGIN;

CREATE OR REPLACE FUNCTION fn_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_books_updated_at ON books;
CREATE TRIGGER trg_books_updated_at
BEFORE UPDATE ON books
FOR EACH ROW
EXECUTE FUNCTION fn_touch_updated_at();

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION fn_touch_updated_at();

CREATE OR REPLACE FUNCTION fn_prevent_second_admin()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.role = 'admin' AND EXISTS (
        SELECT 1 FROM users WHERE role = 'admin' AND id IS DISTINCT FROM NEW.id
    ) THEN
        RAISE EXCEPTION 'Solo se permite un usuario con rol Administrador'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_single_admin ON users;
CREATE TRIGGER trg_users_single_admin
BEFORE INSERT OR UPDATE OF role ON users
FOR EACH ROW
EXECUTE FUNCTION fn_prevent_second_admin();

COMMIT;
