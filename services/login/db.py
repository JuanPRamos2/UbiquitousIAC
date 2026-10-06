from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import DSN

_pool = None


def pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=DSN,
            min_size=1,
            max_size=8,
            timeout=5,
            reconnect_timeout=5,
            open=True,
            kwargs={"row_factory": dict_row, "connect_timeout": 5},
        )
    return _pool


def query(sql, params=None, fetch="all"):
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch == "none":
                return None
            if fetch == "one":
                return cur.fetchone()
            return cur.fetchall()


def ping():
    row = query("SELECT 1 AS ok", fetch="one")
    return bool(row and row.get("ok") == 1)


def find_user_by_email(email):
    return query(
        """
        SELECT u.id, u.first_name, u.paternal_surname, u.maternal_surname,
               u.full_name, u.email, u.password_hash, r.name AS role, u.role_id,
               u.email_verified, u.created_at, u.updated_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.email = %s
        """,
        (email,),
        fetch="one",
    )


def find_user_by_id(user_id):
    return query(
        """
        SELECT u.id, u.first_name, u.paternal_surname, u.maternal_surname,
               u.full_name, u.email, r.name AS role, u.role_id,
               u.email_verified, u.created_at, u.updated_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
        """,
        (user_id,),
        fetch="one",
    )


def register_user(first_name, paternal_surname, maternal_surname, email, password_hash):
    return query(
        """
        SELECT * FROM sp_register_user(%s, %s, %s, %s, %s, 'client')
        """,
        (first_name, paternal_surname, maternal_surname, email, password_hash),
        fetch="one",
    )


def update_profile(user_id, changes, password_hash=None):
    allowed = {
        "first_name": "first_name",
        "paternal_surname": "paternal_surname",
        "maternal_surname": "maternal_surname",
        "email": "email",
    }
    sets = []
    params = []
    for key, column in allowed.items():
        if key in changes:
            sets.append(f"{column} = %s")
            params.append(changes[key])
    if password_hash:
        sets.append("password_hash = %s")
        params.append(password_hash)
    if not sets:
        return find_user_by_id(user_id)
    sets.append("updated_at = NOW()")
    params.append(user_id)
    query(
        f"UPDATE users SET {', '.join(sets)} WHERE id = %s",
        tuple(params),
        fetch="none",
    )
    return find_user_by_id(user_id)


def set_verification_token(user_id, token_hash, expires_at):
    query(
        """
        UPDATE users
           SET verification_token_hash = %s,
               verification_expires_at = %s
         WHERE id = %s
        """,
        (token_hash, expires_at, user_id),
        fetch="none",
    )


def verify_email_token(token_hash):
    user = query(
        """
        SELECT u.id, u.first_name, u.paternal_surname, u.maternal_surname,
               u.full_name, u.email, r.name AS role, u.role_id,
               u.email_verified, u.created_at, u.updated_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.verification_token_hash = %s
          AND u.verification_expires_at > NOW()
        """,
        (token_hash,),
        fetch="one",
    )
    if not user:
        return None
    query(
        """
        UPDATE users
           SET email_verified = TRUE,
               verification_token_hash = NULL,
               verification_expires_at = NULL
         WHERE id = %s
        """,
        (user["id"],),
        fetch="none",
    )
    user["email_verified"] = True
    return user

