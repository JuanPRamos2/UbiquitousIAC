"""Autores y su relación con los libros."""
import psycopg2

from libreria_platform.postgres import ping, query

AUTHOR = """
    a.id, a.full_name, a.biography, a.created_at
"""


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


def _map(exc):
    if isinstance(exc, psycopg2.errors.UniqueViolation):
        raise Conflict("Ese autor o esa relación ya existe.") from exc
    if isinstance(exc, psycopg2.errors.ForeignKeyViolation):
        raise Conflict("El autor tiene libros ligados o el libro no existe.") from exc
    raise exc


def list_authors():
    return query(
        f"""
        SELECT {AUTHOR},
               COUNT(ba.book_id) AS book_count
        FROM authors a
        LEFT JOIN book_authors ba ON ba.author_id = a.id
        GROUP BY a.id
        ORDER BY a.full_name
        """
    )


def get_author(author_id):
    author = query(
        f"SELECT {AUTHOR} FROM authors a WHERE a.id = %s",
        (author_id,),
        fetch="one",
    )
    if not author:
        return None
    author["books"] = query(
        """
        SELECT b.id AS book_id, b.isbn, b.title
        FROM book_authors ba
        JOIN books b ON b.id = ba.book_id
        WHERE ba.author_id = %s
        ORDER BY b.title
        """,
        (author_id,),
    )
    return author


def insert_author(full_name, biography):
    try:
        return query(
            """
            INSERT INTO authors (full_name, biography)
            VALUES (%s, %s)
            RETURNING id, full_name, biography, created_at
            """,
            (full_name, biography or None),
            fetch="one",
        )
    except psycopg2.Error as exc:
        _map(exc)


def update_author(author_id, changes):
    allowed = {"full_name": "full_name", "biography": "biography"}
    sets = []
    params = []
    for key, column in allowed.items():
        if key in changes:
            sets.append(f"{column} = %s")
            params.append(changes[key])
    if not sets:
        return get_author(author_id)
    params.append(author_id)
    try:
        query(
            f"UPDATE authors SET {', '.join(sets)} WHERE id = %s",
            tuple(params),
            fetch="none",
        )
    except psycopg2.Error as exc:
        _map(exc)
    return get_author(author_id)


def delete_author(author_id):
    current = get_author(author_id)
    if not current:
        return None
    if current.get("books"):
        raise Conflict("Quita los libros del autor antes de eliminarlo.")
    query("DELETE FROM authors WHERE id = %s", (author_id,), fetch="none")
    return current


def link_book(author_id, isbn=None, book_id=None):
    if not get_author(author_id):
        return None
    book = query(
        "SELECT id, isbn, title FROM books WHERE isbn = %s OR id = %s",
        (isbn or "", book_id or 0),
        fetch="one",
    )
    if not book:
        raise Invalid("No hay un libro con ese ISBN o id.")
    try:
        query(
            """
            INSERT INTO book_authors (book_id, author_id)
            VALUES (%s, %s)
            """,
            (book["id"], author_id),
            fetch="none",
        )
    except psycopg2.Error as exc:
        _map(exc)
    return get_author(author_id)


def unlink_book(author_id, book_id):
    query(
        "DELETE FROM book_authors WHERE author_id = %s AND book_id = %s",
        (author_id, book_id),
        fetch="none",
    )
    return get_author(author_id)
