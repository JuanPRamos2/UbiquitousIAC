"""Catálogo y CRUD de libros. Solo habla con el microservicio de books."""
from urllib.parse import quote


def _number(value):
    if value is None or value == "":
        return None
    return float(value)


def filter_books(books, isbn="", title="", year="", price_min="", price_max=""):
    isbn_q = (isbn or "").strip().lower()
    title_q = (title or "").strip().lower()
    year_q = (year or "").strip()
    minimum = _number(price_min) if str(price_min).strip() else None
    maximum = _number(price_max) if str(price_max).strip() else None
    found = []
    for book in books:
        if isbn_q and isbn_q not in str(book.get("isbn") or "").lower():
            continue
        if title_q and title_q not in str(book.get("title") or "").lower():
            continue
        if year_q and str(book.get("publicationYear") or "") != year_q:
            continue
        price = book.get("price")
        if minimum is not None:
            if price is None or float(price) < minimum:
                continue
        if maximum is not None:
            if price is None or float(price) > maximum:
                continue
        found.append(book)
    return found


def authors_text(book):
    authors = book.get("authors") or []
    if isinstance(authors, list):
        return ", ".join(str(author) for author in authors if str(author).strip())
    return str(authors or "")


def has_image(book):
    images = book.get("images") or []
    if images:
        return True
    return bool(book.get("coverUrl"))


class BooksApi:
    def __init__(self, http, auth):
        self.http = http
        self.auth = auth

    def _path(self, path):
        separator = "&" if "?" in path else "?"
        return path + separator + "format=json"

    def list_books(self):
        payload = self.http.request("GET", self.http.books_url, self._path("/books"))
        books = payload.get("books") or []
        return books if isinstance(books, list) else []

    def get_book(self, isbn):
        payload = self.http.request(
            "GET",
            self.http.books_url,
            self._path(f"/books/{quote(str(isbn))}"),
        )
        return payload.get("book") or payload

    def create_book(self, book):
        return self.http.request(
            "POST",
            self.http.books_url,
            self._path("/books"),
            book,
            use_token=True,
        )

    def replace_book(self, isbn, book):
        return self.http.request(
            "PUT",
            self.http.books_url,
            self._path(f"/books/{quote(str(isbn))}"),
            book,
            use_token=True,
        )

    def patch_book(self, isbn, changes):
        return self.http.request(
            "PATCH",
            self.http.books_url,
            self._path(f"/books/{quote(str(isbn))}"),
            changes,
            use_token=True,
        )

    def delete_book(self, isbn):
        return self.http.request(
            "DELETE",
            self.http.books_url,
            self._path(f"/books/{quote(str(isbn))}"),
            use_token=True,
        )
