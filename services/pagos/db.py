"""Pagos. Actualiza el estado del pedido en PostgreSQL, sin llamar al otro proceso."""
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

from libreria_platform.postgres import connect, execute_script, ping, query

METHODS = ("efectivo", "tarjeta", "transferencia")


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


def _order_total(cur, order_id):
    cur.execute(
        """
        SELECT o.id, o.user_id, s.name AS status
        FROM orders o
        JOIN order_statuses s ON s.id = o.status_id
        WHERE o.id = %s
        FOR UPDATE OF o
        """,
        (order_id,),
    )
    order = cur.fetchone()
    if not order:
        return None
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity * unit_price), 0) AS total
        FROM order_lines
        WHERE order_id = %s
        """,
        (order_id,),
    )
    order["total"] = cur.fetchone()["total"]
    return order


def _payment_row(payment_id):
    return query(
        """
        SELECT p.id, p.order_id, o.user_id, p.amount, p.method, p.status,
               p.reference, p.created_at, p.updated_at
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        WHERE p.id = %s
        """,
        (payment_id,),
        fetch="one",
    )


def list_payments(user_id=None):
    if user_id is None:
        return query(
            """
            SELECT p.id, p.order_id, o.user_id, p.amount, p.method, p.status,
                   p.reference, p.created_at, p.updated_at
            FROM payments p
            JOIN orders o ON o.id = p.order_id
            ORDER BY p.id DESC
            """
        )
    return query(
        """
        SELECT p.id, p.order_id, o.user_id, p.amount, p.method, p.status,
               p.reference, p.created_at, p.updated_at
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        WHERE o.user_id = %s
        ORDER BY p.id DESC
        """,
        (user_id,),
    )


def get_payment(payment_id):
    return _payment_row(payment_id)


def register_payment(order_id, amount, method, reference):
    if method not in METHODS:
        raise Invalid("El método debe ser efectivo, tarjeta o transferencia.")
    conn = connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                order = _order_total(cur, order_id)
                if not order:
                    return None
                if order["status"] == "pagado":
                    raise Conflict("Ese pedido ya tiene un pago registrado.")
                if order["status"] != "pendiente":
                    raise Conflict("Solo se puede pagar un pedido pendiente.")
                total = round(float(order["total"]), 2)
                if round(float(amount), 2) != total:
                    raise Invalid(f"El monto debe ser igual al total del pedido ({total:.2f}).")
                cur.execute(
                    """
                    INSERT INTO payments (order_id, amount, method, status, reference)
                    VALUES (%s, %s, %s, 'registrado', %s)
                    RETURNING id
                    """,
                    (order_id, total, method, reference or None),
                )
                payment_id = cur.fetchone()["id"]
                cur.execute(
                    """
                    UPDATE orders
                       SET status_id = (SELECT id FROM order_statuses WHERE name = 'pagado'),
                           updated_at = NOW()
                     WHERE id = %s
                    """,
                    (order_id,),
                )
        return get_payment(payment_id)
    finally:
        conn.close()


def update_payment(payment_id, changes):
    current = get_payment(payment_id)
    if not current:
        return None
    method = changes.get("method", current["method"])
    reference = changes.get("reference", current["reference"])
    if method not in METHODS:
        raise Invalid("El método debe ser efectivo, tarjeta o transferencia.")
    if "amount" in changes and round(float(changes["amount"]), 2) != round(float(current["amount"]), 2):
        raise Invalid("El monto del pago queda ligado al total del pedido.")
    query(
        """
        UPDATE payments
           SET method = %s, reference = %s, updated_at = NOW()
         WHERE id = %s
        """,
        (method, reference, payment_id),
    )
    return get_payment(payment_id)


def delete_payment(payment_id):
    conn = connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, order_id FROM payments WHERE id = %s FOR UPDATE",
                    (payment_id,),
                )
                payment = cur.fetchone()
                if not payment:
                    return None
                order_id = payment["order_id"]
                cur.execute("DELETE FROM payments WHERE id = %s", (payment_id,))
                cur.execute("SELECT COUNT(*) AS n FROM payments WHERE order_id = %s", (order_id,))
                remaining = int(cur.fetchone()["n"])
                if remaining == 0:
                    cur.execute(
                        """
                        UPDATE orders
                           SET status_id = (SELECT id FROM order_statuses WHERE name = 'pendiente'),
                               updated_at = NOW()
                         WHERE id = %s
                           AND status_id = (SELECT id FROM order_statuses WHERE name = 'pagado')
                        """,
                        (order_id,),
                    )
        return {"id": payment_id, "order_id": order_id, "status": "eliminado"}
    finally:
        conn.close()
