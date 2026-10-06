"""Usuarios, roles y contraseñas. PostgreSQL es la fuente de verdad."""
import psycopg2

from libreria_platform.postgres import ping, query

USER_COLUMNS = """
    u.id, u.first_name, u.paternal_surname, u.maternal_surname, u.full_name,
    u.email, u.role_id, r.name AS role, u.email_verified, u.created_at, u.updated_at
"""


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


def _map(exc):
    if isinstance(exc, psycopg2.errors.UniqueViolation):
        text = str(exc)
        if "ux_users_single_admin" in text or "role_id" in text:
            raise Conflict("Ya existe un administrador y el rol no se puede duplicar.") from exc
        raise Conflict("Ese correo ya está registrado.") from exc
    if isinstance(exc, psycopg2.errors.ForeignKeyViolation):
        raise Conflict("El usuario tiene pedidos u otra información ligada y no se puede borrar.") from exc
    if isinstance(exc, psycopg2.errors.CheckViolation):
        raise Invalid("Hay un dato que no cumple las reglas de la cuenta.") from exc
    raise exc


def list_users():
    return query(
        f"""
        SELECT {USER_COLUMNS}
        FROM users u
        JOIN roles r ON r.id = u.role_id
        ORDER BY u.id
        """
    )


def get_user(user_id):
    return query(
        f"""
        SELECT {USER_COLUMNS}
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
        """,
        (user_id,),
        fetch="one",
    )


def password_hash(user_id):
    row = query("SELECT password_hash FROM users WHERE id = %s", (user_id,), fetch="one")
    return None if not row else row["password_hash"]


def role_id_by_name(name):
    row = query("SELECT id FROM roles WHERE name = %s", (name,), fetch="one")
    return None if not row else row["id"]


def insert_user(first_name, paternal, maternal, email, password_hash_value, role_name):
    role_id = role_id_by_name(role_name or "client")
    if not role_id:
        raise Invalid("El rol no existe.")
    try:
        created = query(
            """
            INSERT INTO users (
                first_name, paternal_surname, maternal_surname, email,
                password_hash, role_id, email_verified
            )
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id
            """,
            (first_name, paternal, maternal, email, password_hash_value, role_id),
            fetch="one",
        )
    except psycopg2.Error as exc:
        _map(exc)
    if not created:
        return None
    return get_user(created["id"])


def update_names(user_id, changes):
    allowed = {
        "first_name": "first_name",
        "paternal_surname": "paternal_surname",
        "maternal_surname": "maternal_surname",
    }
    sets = []
    params = []
    for key, column in allowed.items():
        if key in changes:
            sets.append(f"{column} = %s")
            params.append(changes[key])
    if not sets:
        return get_user(user_id)
    sets.append("updated_at = NOW()")
    params.append(user_id)
    try:
        query(
            f"UPDATE users SET {', '.join(sets)} WHERE id = %s",
            tuple(params),
            fetch="none",
        )
    except psycopg2.Error as exc:
        _map(exc)
    return get_user(user_id)


def update_role(user_id, role_name):
    role_id = role_id_by_name(role_name)
    if not role_id:
        raise Invalid("El rol no existe.")
    try:
        query(
            "UPDATE users SET role_id = %s, updated_at = NOW() WHERE id = %s",
            (role_id, user_id),
            fetch="none",
        )
    except psycopg2.Error as exc:
        _map(exc)
    return get_user(user_id)


def update_password(user_id, password_hash_value):
    query(
        "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
        (password_hash_value, user_id),
        fetch="none",
    )
    return get_user(user_id)


def delete_user(user_id):
    current = get_user(user_id)
    if not current:
        return None
    if int(current["role_id"]) == 1:
        raise Conflict("El administrador único no se puede eliminar.")
    try:
        query("DELETE FROM users WHERE id = %s", (user_id,), fetch="none")
    except psycopg2.Error as exc:
        _map(exc)
    return current
