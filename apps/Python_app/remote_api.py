"""Clientes HTTP de users, autores, pedidos y pagos."""


class UsersApi:
    def __init__(self, http):
        self.http = http

    def list_users(self):
        return self.http.request("GET", self.http.users_url, "/users", use_token=True)

    def get_user(self, user_id):
        return self.http.request("GET", self.http.users_url, f"/users/{user_id}", use_token=True)

    def create(self, body):
        return self.http.request("POST", self.http.users_url, "/users", body, use_token=True)

    def replace(self, user_id, body):
        return self.http.request("PUT", self.http.users_url, f"/users/{user_id}", body, use_token=True)

    def patch(self, user_id, body):
        return self.http.request("PATCH", self.http.users_url, f"/users/{user_id}", body, use_token=True)

    def delete(self, user_id):
        return self.http.request("DELETE", self.http.users_url, f"/users/{user_id}", use_token=True)

    def change_password(self, user_id, current, new_password, confirm):
        return self.http.request(
            "POST",
            self.http.users_url,
            f"/users/{user_id}/password",
            {
                "currentPassword": current,
                "newPassword": new_password,
                "confirmPassword": confirm,
            },
            use_token=True,
        )


class AuthorsApi:
    def __init__(self, http):
        self.http = http

    def list_authors(self):
        return self.http.request("GET", self.http.authors_url, "/authors")

    def get_author(self, author_id):
        return self.http.request("GET", self.http.authors_url, f"/authors/{author_id}")

    def create(self, body):
        return self.http.request("POST", self.http.authors_url, "/authors", body, use_token=True)

    def replace(self, author_id, body):
        return self.http.request("PUT", self.http.authors_url, f"/authors/{author_id}", body, use_token=True)

    def patch(self, author_id, body):
        return self.http.request("PATCH", self.http.authors_url, f"/authors/{author_id}", body, use_token=True)

    def delete(self, author_id):
        return self.http.request("DELETE", self.http.authors_url, f"/authors/{author_id}", use_token=True)

    def link(self, author_id, isbn):
        return self.http.request(
            "POST",
            self.http.authors_url,
            f"/authors/{author_id}/books",
            {"isbn": isbn},
            use_token=True,
        )

    def unlink(self, author_id, book_id):
        return self.http.request(
            "DELETE",
            self.http.authors_url,
            f"/authors/{author_id}/books/{book_id}",
            use_token=True,
        )


class OrdersApi:
    def __init__(self, http):
        self.http = http

    def list_orders(self):
        return self.http.request("GET", self.http.pedidos_url, "/pedidos", use_token=True)

    def create(self, lines):
        return self.http.request("POST", self.http.pedidos_url, "/pedidos", {"lines": lines}, use_token=True)

    def replace(self, order_id, lines):
        return self.http.request(
            "PUT",
            self.http.pedidos_url,
            f"/pedidos/{order_id}",
            {"lines": lines},
            use_token=True,
        )

    def cancel(self, order_id):
        return self.http.request(
            "PATCH",
            self.http.pedidos_url,
            f"/pedidos/{order_id}",
            {"status": "cancelado"},
            use_token=True,
        )

    def delete(self, order_id):
        return self.http.request("DELETE", self.http.pedidos_url, f"/pedidos/{order_id}", use_token=True)


class PaymentsApi:
    def __init__(self, http):
        self.http = http

    def list_payments(self):
        return self.http.request("GET", self.http.pagos_url, "/pagos", use_token=True)

    def create(self, order_id, amount, method, reference):
        return self.http.request(
            "POST",
            self.http.pagos_url,
            "/pagos",
            {
                "order_id": order_id,
                "amount": amount,
                "method": method,
                "reference": reference,
            },
            use_token=True,
        )

    def patch(self, payment_id, body):
        return self.http.request("PATCH", self.http.pagos_url, f"/pagos/{payment_id}", body, use_token=True)

    def replace(self, payment_id, body):
        return self.http.request("PUT", self.http.pagos_url, f"/pagos/{payment_id}", body, use_token=True)

    def delete(self, payment_id):
        return self.http.request("DELETE", self.http.pagos_url, f"/pagos/{payment_id}", use_token=True)
