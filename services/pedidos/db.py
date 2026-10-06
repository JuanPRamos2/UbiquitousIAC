"""Pedidos, líneas, stock y estados."""
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

from libreria_platform.postgres import clean, connect, execute_script, ping, query


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


def ensure_schema():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "database" / "10_orders_payments.sql"
        if candidate.is_file():
            execute_script(candidate.read_text(encoding="utf-8"))
            return
    raise FileNotFoundError("No está data/database/10_orders_payments.sql")


def _map(exc):
    if isinstance(exc, psycopg2.errors.ForeignKeyViolation):
        raise Conflict("El pedido referencia un usuario o un libro que no existe.") from exc
    if isinstance(exc, psycopg2.errors.CheckViolation):
        raise Invalid("La cantidad o el precio no son válidos.") from exc
    raise exc


def _lines(order_id):
    return query(
        """
        SELECT ol.id, ol.book_id, b.isbn, b.title, ol.quantity, ol.unit_price
        FROM order_lines ol
        JOIN books b ON b.id = ol.book_id
        WHERE ol.order_id = %s
        ORDER BY ol.id
        """,
        (order_id,),
    )


def _attach(order):
    if not order:
        return None
    lines = _lines(order["id"])
    order["lines"] = lines
    order["total"] = round(sum(float(line["quantity"]) * float(line["unit_price"]) for line in lines), 2)
    return order


def list_orders(user_id=None):
    if user_id is None:
        rows = query(
            """
            SELECT o.id, o.user_id, u.email AS user_email, s.name AS status,
                   o.created_at, o.updated_at
            FROM orders o
            JOIN order_statuses s ON s.id = o.status_id
            JOIN users u ON u.id = o.user_id
            ORDER BY o.id DESC
            """
        )
    else:
        rows = query(
            """
            SELECT o.id, o.user_id, u.email AS user_email, s.name AS status,
                   o.created_at, o.updated_at
            FROM orders o
            JOIN order_statuses s ON s.id = o.status_id
            JOIN users u ON u.id = o.user_id
            WHERE o.user_id = %s
            ORDER BY o.id DESC
            """,
            (user_id,),
        )
    return [_attach(row) for row in rows]


def get_order(order_id):
    order = query(
        """
        SELECT o.id, o.user_id, u.email AS user_email, s.name AS status,
               o.created_at, o.updated_at
        FROM orders o
        JOIN order_statuses s ON s.id = o.status_id
        JOIN users u ON u.id = o.user_id
        WHERE o.id = %s
        """,
        (order_id,),
        fetch="one",
    )
    return _attach(order)


def _status_id(cur, name):
    cur.execute("SELECT id FROM order_statuses WHERE name = %s", (name,))
    row = cur.fetchone()
    if not row:
        raise Invalid("Faltan los estados del pedido. Revisa el esquema.")
    return row["id"]


def _take_lines(cur, order_id, lines):
    if not lines:
        raise Invalid("El pedido necesita al menos una línea.")
    for line in lines:
        isbn = str(line.get("isbn") or "").strip()
        book_id = line.get("book_id") or line.get("bookId")
        try:
            quantity = int(line.get("quantity") if line.get("quantity") not in (None, "") else line.get("cantidad"))
        except (TypeError, ValueError):
            raise Invalid("La cantidad debe ser un entero.")
        if quantity < 1:
            raise Invalid("La cantidad debe ser mayor que cero.")
        if isbn:
            cur.execute(
                "SELECT id, isbn, price, stock FROM books WHERE isbn = %s FOR UPDATE",
                (isbn,),
            )
        else:
            cur.execute(
                "SELECT id, isbn, price, stock FROM books WHERE id = %s FOR UPDATE",
                (book_id,),
            )
        book = cur.fetchone()
        if not book:
            raise Invalid("Hay un libro que no existe en el catálogo.")
        if int(book["stock"]) < quantity:
            raise Conflict(f"No hay stock suficiente de {book['isbn']}. Disponible: {book['stock']}.")
        cur.execute(
            "UPDATE books SET stock = stock - %s, updated_at = NOW() WHERE id = %s",
            (quantity, book["id"]),
        )
        cur.execute(
            """
            INSERT INTO order_lines (order_id, book_id, quantity, unit_price)
            VALUES (%s, %s, %s, %s)
            """,
            (order_id, book["id"], quantity, book["price"]),
        )


def _restore_stock(cur, order_id):
    cur.execute(
        "SELECT book_id, quantity FROM order_lines WHERE order_id = %s",
        (order_id,),
    )
    for line in cur.fetchall():
        cur.execute(
            "UPDATE books SET stock = stock + %s, updated_at = NOW() WHERE id = %s",
            (line["quantity"], line["book_id"]),
        )
    cur.execute("DELETE FROM order_lines WHERE order_id = %s", (order_id,))


def create_order(user_id, lines):
    conn = connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                status_id = _status_id(cur, "pendiente")
                cur.execute(
                    "INSERT INTO orders (user_id, status_id) VALUES (%s, %s) RETURNING id",
                    (user_id, status_id),
                )
                order_id = cur.fetchone()["id"]
                _take_lines(cur, order_id, lines)
        return get_order(order_id)
    except psycopg2.Error as exc:
        _map(exc)
    finally:
        conn.close()


def replace_lines(order_id, lines):
    conn = connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT s.name AS status
                    FROM orders o
                    JOIN order_statuses s ON s.id = o.status_id
                    WHERE o.id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                order = cur.fetchone()
                if not order:
                    return None
                if order["status"] != "pendiente":
                    raise Conflict("Solo se pueden cambiar las líneas de un pedido pendiente.")
                _restore_stock(cur, order_id)
                _take_lines(cur, order_id, lines)
                cur.execute("UPDATE orders SET updated_at = NOW() WHERE id = %s", (order_id,))
        return get_order(order_id)
    except psycopg2.Error as exc:
        _map(exc)
    finally:
        conn.close()


def cancel_order(order_id):
    conn = connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT s.name AS status
                    FROM orders o
                    JOIN order_statuses s ON s.id = o.status_id
                    WHERE o.id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                order = cur.fetchone()
                if not order:
                    return None
                if order["status"] == "cancelado":
                    raise Conflict("El pedido ya está cancelado.")
                if order["status"] == "pagado":
                    raise Conflict("El pedido está pagado. Elimina el pago antes de cancelarlo.")
                _restore_stock(cur, order_id)
                status_id = _status_id(cur, "cancelado")
                cur.execute(
                    "UPDATE orders SET status_id = %s, updated_at = NOW() WHERE id = %s",
                    (status_id, order_id),
                )
        return get_order(order_id)
    except psycopg2.Error as exc:
        _map(exc)
    finally:
        conn.close()
