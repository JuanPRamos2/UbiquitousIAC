"""Formularios CRUD de users, autores, pedidos y pagos."""
import tkinter as tk
from tkinter import messagebox, ttk

from http_api import ApiError

NAVY = "#1e3a5f"
BG = "#f3f5f8"
CARD = "#ffffff"


def _lines(text):
    rows = []
    for raw in text.splitlines():
        piece = raw.strip()
        if not piece:
            continue
        if "," not in piece:
            raise ValueError("Cada línea debe ser ISBN,cantidad.")
        isbn, quantity = piece.split(",", 1)
        rows.append({"isbn": isbn.strip(), "quantity": int(quantity.strip())})
    if not rows:
        raise ValueError("Escribe al menos una línea ISBN,cantidad.")
    return rows


class Panels:
    def __init__(self, app):
        self.app = app

    def _guard(self):
        return self.app._ensure_session()

    def _run(self, action, title):
        if not self._guard():
            return None
        try:
            payload = action()
        except (ApiError, ValueError) as exc:
            self.app._note_http()
            messagebox.showerror(title, str(exc), parent=self.app)
            return None
        self.app._note_http()
        return payload

    def _box(self, parent, title, note):
        box = tk.Frame(parent, bg=CARD, padx=12, pady=12)
        box.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(box, text=title, bg=CARD, fg=NAVY, font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        tk.Label(box, text=note, bg=CARD, fg="#445066", wraplength=860, justify="left").pack(anchor="w", pady=(4, 8))
        return box

    def _tree(self, parent, columns):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=140, anchor="w")
        tree.pack(fill="both", expand=True, pady=(0, 8))
        return tree

    def _fill(self, tree, rows, columns, getters):
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=tuple(getter(row) for getter in getters))

    def _selected(self, tree):
        chosen = tree.selection()
        if not chosen:
            return None
        return tree.item(chosen[0], "values")

    def build_users(self, parent):
        box = self._box(
            parent,
            "Usuarios",
            "El correo no se cambia: es la llave de acceso. La contraseña pide la actual, la nueva y la confirmación. "
            "Listar, crear, borrar y cambiar rol exigen un administrador.",
        )
        tree = self._tree(box, ("id", "nombre", "correo", "rol"))
        form = tk.Frame(box, bg=CARD)
        form.pack(fill="x")
        fields = {
            key: tk.StringVar()
            for key in ("id", "nombre", "paterno", "materno", "email", "password", "rol", "actual", "nueva", "confirma")
        }
        labels = [
            ("Id", "id"),
            ("Nombre", "nombre"),
            ("Apellido paterno", "paterno"),
            ("Apellido materno", "materno"),
            ("Correo (solo alta)", "email"),
            ("Contraseña inicial", "password"),
            ("Rol", "rol"),
            ("Contraseña actual", "actual"),
            ("Contraseña nueva", "nueva"),
            ("Confirmar contraseña", "confirma"),
        ]
        for index, (label, key) in enumerate(labels):
            column = (index % 2) * 2
            row = index // 2
            tk.Label(form, text=label, bg=CARD).grid(row=row, column=column, sticky="w", padx=(0, 6), pady=2)
            show = "*" if key in ("password", "actual", "nueva", "confirma") else ""
            tk.Entry(form, textvariable=fields[key], width=28, show=show).grid(row=row, column=column + 1, sticky="w", pady=2)

        def names():
            return {
                "nombre": fields["nombre"].get().strip(),
                "apellidoPaterno": fields["paterno"].get().strip(),
                "apellidoMaterno": fields["materno"].get().strip(),
            }

        def reload():
            payload = self._run(self.app.users.list_users, "Usuarios")
            if not payload:
                return
            self._fill(
                tree,
                payload.get("users") or [],
                ("id", "nombre", "correo", "rol"),
                (
                    lambda row: row.get("id"),
                    lambda row: row.get("full_name"),
                    lambda row: row.get("email"),
                    lambda row: row.get("role"),
                ),
            )

        def selected_id():
            values = self._selected(tree)
            typed = fields["id"].get().strip()
            if typed:
                return typed
            if not values:
                messagebox.showinfo("Usuarios", "Elige un usuario o escribe su id.", parent=self.app)
                return None
            fields["id"].set(str(values[0]))
            return str(values[0])

        def create():
            body = names()
            body["email"] = fields["email"].get().strip()
            body["password"] = fields["password"].get()
            body["role"] = fields["rol"].get().strip() or "client"
            payload = self._run(lambda: self.app.users.create(body), "Usuarios")
            if payload:
                reload()

        def replace():
            user_id = selected_id()
            if not user_id:
                return
            payload = self._run(lambda: self.app.users.replace(user_id, names()), "Usuarios")
            if payload:
                reload()

        def patch():
            user_id = selected_id()
            if not user_id:
                return
            body = {key: value for key, value in names().items() if value}
            payload = self._run(lambda: self.app.users.patch(user_id, body), "Usuarios")
            if payload:
                reload()

        def remove():
            user_id = selected_id()
            if not user_id:
                return
            if not messagebox.askyesno("Usuarios", f"¿Eliminar el usuario {user_id}?", parent=self.app):
                return
            payload = self._run(lambda: self.app.users.delete(user_id), "Usuarios")
            if payload:
                reload()

        def password():
            user_id = selected_id()
            if not user_id:
                return
            payload = self._run(
                lambda: self.app.users.change_password(
                    user_id,
                    fields["actual"].get(),
                    fields["nueva"].get(),
                    fields["confirma"].get(),
                ),
                "Contraseña",
            )
            if payload:
                fields["actual"].set("")
                fields["nueva"].set("")
                fields["confirma"].set("")
                messagebox.showinfo("Contraseña", "La contraseña quedó actualizada.", parent=self.app)

        buttons = tk.Frame(box, bg=CARD)
        buttons.pack(anchor="w", pady=(8, 0))
        for text, command in (
            ("Consultar", reload),
            ("Crear", create),
            ("Reemplazar", replace),
            ("Modificar", patch),
            ("Eliminar", remove),
            ("Cambiar contraseña", password),
        ):
            tk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 6))

    def build_authors(self, parent):
        box = self._box(
            parent,
            "Autores",
            "Consultar es público. Crear, cambiar, borrar y ligar un ISBN exigen el JWT de administrador.",
        )
        tree = self._tree(box, ("id", "nombre", "libros"))
        name = tk.StringVar()
        biography = tk.StringVar()
        author_id = tk.StringVar()
        isbn = tk.StringVar()
        book_id = tk.StringVar()
        form = tk.Frame(box, bg=CARD)
        form.pack(fill="x", pady=(0, 8))
        for index, (label, var) in enumerate(
            (("Id", author_id), ("Nombre", name), ("Biografía", biography), ("ISBN", isbn), ("Id libro", book_id))
        ):
            tk.Label(form, text=label, bg=CARD).grid(row=0, column=index * 2, sticky="w")
            tk.Entry(form, textvariable=var, width=18).grid(row=0, column=index * 2 + 1, padx=(4, 10))

        def reload():
            payload = self.app.authors.list_authors()
            self.app._note_http()
            self._fill(
                tree,
                payload.get("authors") or [],
                ("id", "nombre", "libros"),
                (
                    lambda row: row.get("id"),
                    lambda row: row.get("full_name"),
                    lambda row: row.get("book_count"),
                ),
            )

        def chosen():
            typed = author_id.get().strip()
            if typed:
                return typed
            values = self._selected(tree)
            if not values:
                messagebox.showinfo("Autores", "Elige un autor o escribe su id.", parent=self.app)
                return None
            author_id.set(str(values[0]))
            return str(values[0])

        def create():
            body = {"nombre": name.get().strip(), "biografia": biography.get().strip()}
            if self._run(lambda: self.app.authors.create(body), "Autores"):
                reload()

        def replace():
            selected = chosen()
            if selected and self._run(
                lambda: self.app.authors.replace(selected, {"nombre": name.get().strip(), "biografia": biography.get().strip()}),
                "Autores",
            ):
                reload()

        def patch():
            selected = chosen()
            body = {}
            if name.get().strip():
                body["nombre"] = name.get().strip()
            if biography.get().strip():
                body["biografia"] = biography.get().strip()
            if selected and self._run(lambda: self.app.authors.patch(selected, body), "Autores"):
                reload()

        def remove():
            selected = chosen()
            if not selected:
                return
            if messagebox.askyesno("Autores", f"¿Eliminar el autor {selected}?", parent=self.app) and self._run(
                lambda: self.app.authors.delete(selected), "Autores"
            ):
                reload()

        def link():
            selected = chosen()
            if selected and self._run(lambda: self.app.authors.link(selected, isbn.get().strip()), "Autores"):
                reload()

        def unlink():
            selected = chosen()
            if selected and book_id.get().strip() and self._run(
                lambda: self.app.authors.unlink(selected, book_id.get().strip()), "Autores"
            ):
                reload()

        def public_reload():
            try:
                reload()
            except ApiError as exc:
                self.app._note_http()
                messagebox.showerror("Autores", str(exc), parent=self.app)

        buttons = tk.Frame(box, bg=CARD)
        buttons.pack(anchor="w")
        for text, command in (
            ("Consultar", public_reload),
            ("Crear", create),
            ("Reemplazar", replace),
            ("Modificar", patch),
            ("Eliminar", remove),
            ("Ligar ISBN", link),
            ("Quitar libro", unlink),
        ):
            tk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 6))

    def build_orders(self, parent):
        box = self._box(
            parent,
            "Pedidos",
            "Cada línea es ISBN,cantidad. Crear descuenta stock. Cancelar o eliminar lo devuelve si el pedido sigue pendiente. "
            "El estado pagado lo pone el servicio de pagos.",
        )
        tree = self._tree(box, ("id", "usuario", "estado", "total"))
        order_id = tk.StringVar()
        lines = tk.Text(box, height=4, width=40)
        tk.Label(box, text="Id del pedido", bg=CARD).pack(anchor="w")
        tk.Entry(box, textvariable=order_id, width=12).pack(anchor="w")
        tk.Label(box, text="Líneas", bg=CARD).pack(anchor="w", pady=(6, 0))
        lines.pack(anchor="w", pady=(0, 8))

        def parsed():
            return _lines(lines.get("1.0", "end"))

        def reload():
            payload = self._run(self.app.orders.list_orders, "Pedidos")
            if not payload:
                return
            self._fill(
                tree,
                payload.get("pedidos") or [],
                ("id", "usuario", "estado", "total"),
                (
                    lambda row: row.get("id"),
                    lambda row: row.get("user_email"),
                    lambda row: row.get("status"),
                    lambda row: row.get("total"),
                ),
            )

        def chosen():
            typed = order_id.get().strip()
            if typed:
                return typed
            values = self._selected(tree)
            if not values:
                messagebox.showinfo("Pedidos", "Elige un pedido o escribe su id.", parent=self.app)
                return None
            order_id.set(str(values[0]))
            return str(values[0])

        def create():
            if self._run(lambda: self.app.orders.create(parsed()), "Pedidos"):
                reload()

        def replace():
            selected = chosen()
            if selected and self._run(lambda: self.app.orders.replace(selected, parsed()), "Pedidos"):
                reload()

        def cancel():
            selected = chosen()
            if selected and self._run(lambda: self.app.orders.cancel(selected), "Pedidos"):
                reload()

        def remove():
            selected = chosen()
            if selected and messagebox.askyesno("Pedidos", f"¿Cancelar el pedido {selected}?", parent=self.app):
                if self._run(lambda: self.app.orders.delete(selected), "Pedidos"):
                    reload()

        buttons = tk.Frame(box, bg=CARD)
        buttons.pack(anchor="w")
        for text, command in (
            ("Consultar", reload),
            ("Crear", create),
            ("Reemplazar líneas", replace),
            ("Cancelar", cancel),
            ("Eliminar", remove),
        ):
            tk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 6))

    def build_payments(self, parent):
        box = self._box(
            parent,
            "Pagos",
            "El monto tiene que ser el total del pedido. Al registrarlo, el pedido pasa a pagado. "
            "Borrar un pago es de administrador y regresa el pedido a pendiente.",
        )
        tree = self._tree(box, ("id", "pedido", "monto", "método", "estado"))
        payment_id = tk.StringVar()
        order_id = tk.StringVar()
        amount = tk.StringVar()
        method = tk.StringVar(value="efectivo")
        reference = tk.StringVar()
        form = tk.Frame(box, bg=CARD)
        form.pack(fill="x", pady=(0, 8))
        for index, (label, var) in enumerate(
            (("Id pago", payment_id), ("Id pedido", order_id), ("Monto", amount), ("Referencia", reference))
        ):
            tk.Label(form, text=label, bg=CARD).grid(row=0, column=index * 2, sticky="w")
            tk.Entry(form, textvariable=var, width=16).grid(row=0, column=index * 2 + 1, padx=(4, 10))
        tk.Label(form, text="Método", bg=CARD).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(form, textvariable=method, values=("efectivo", "tarjeta", "transferencia"), width=14, state="readonly").grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        def reload():
            payload = self._run(self.app.payments.list_payments, "Pagos")
            if not payload:
                return
            self._fill(
                tree,
                payload.get("pagos") or [],
                ("id", "pedido", "monto", "método", "estado"),
                (
                    lambda row: row.get("id"),
                    lambda row: row.get("order_id"),
                    lambda row: row.get("amount"),
                    lambda row: row.get("method"),
                    lambda row: row.get("status"),
                ),
            )

        def chosen():
            typed = payment_id.get().strip()
            if typed:
                return typed
            values = self._selected(tree)
            if not values:
                messagebox.showinfo("Pagos", "Elige un pago o escribe su id.", parent=self.app)
                return None
            payment_id.set(str(values[0]))
            return str(values[0])

        def create():
            if self._run(
                lambda: self.app.payments.create(order_id.get().strip(), amount.get().strip(), method.get(), reference.get().strip()),
                "Pagos",
            ):
                reload()

        def patch():
            selected = chosen()
            body = {}
            if method.get():
                body["method"] = method.get()
            if reference.get().strip():
                body["reference"] = reference.get().strip()
            if selected and self._run(lambda: self.app.payments.patch(selected, body), "Pagos"):
                reload()

        def replace():
            selected = chosen()
            if selected and self._run(
                lambda: self.app.payments.replace(
                    selected,
                    {"method": method.get(), "reference": reference.get().strip(), "amount": amount.get().strip()},
                ),
                "Pagos",
            ):
                reload()

        def remove():
            selected = chosen()
            if selected and messagebox.askyesno("Pagos", f"¿Eliminar el pago {selected}?", parent=self.app):
                if self._run(lambda: self.app.payments.delete(selected), "Pagos"):
                    reload()

        buttons = tk.Frame(box, bg=CARD)
        buttons.pack(anchor="w")
        for text, command in (
            ("Consultar", reload),
            ("Registrar", create),
            ("Modificar", patch),
            ("Reemplazar", replace),
            ("Eliminar", remove),
        ):
            tk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 6))
