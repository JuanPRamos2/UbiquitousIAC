"""Interfaz Tk: login, perfil, catálogo, administración, salud y configuración."""
import queue
import threading
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import messagebox, ttk

import health_api
from auth_api import AuthApi
from books_api import BooksApi, authors_text, filter_books, has_image
from config_store import config_path, load, restore_defaults, save, with_scheme
from http_api import ApiError, HttpClient
from panels import Panels
from remote_api import AuthorsApi, OrdersApi, PaymentsApi, UsersApi

NAVY = "#1e3a5f"
BG = "#f3f5f8"
CARD = "#ffffff"
GREEN = "#1b7f3a"
YELLOW = "#c9a227"
RED = "#c0392b"
DIM = "#d5dbe3"
STATE_COLOR = {"up": GREEN, "degraded": YELLOW, "down": RED, "unknown": DIM}


def _blank(value):
    text = "" if value is None else str(value).strip()
    return text or "No informado"


class LibreriaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Librería — cliente Python")
        self.geometry("1280x820")
        self.minsize(1100, 680)
        self.configure(bg=BG)
        stored = load()
        self.http = HttpClient(
            stored["loginUrl"],
            stored["booksUrl"],
            stored["usersUrl"],
            stored["authorsUrl"],
            stored["pedidosUrl"],
            stored["pagosUrl"],
        )
        self.scheme = stored.get("scheme") or "http"
        self.auth = AuthApi(self.http)
        self.books = BooksApi(self.http, self.auth)
        self.users = UsersApi(self.http)
        self.authors = AuthorsApi(self.http)
        self.orders = OrdersApi(self.http)
        self.payments = PaymentsApi(self.http)
        self.panels = Panels(self)
        self.services = (
            ("login", "Login"),
            ("books", "Books"),
            ("users", "Users"),
            ("authors", "Autores"),
            ("pedidos", "Pedidos"),
            ("pagos", "Pagos"),
        )
        self.catalog = []
        self._health = {key: "unknown" for key, _label in self.services}
        self.state_vars = {
            key: tk.StringVar(value=health_api.describe(label, "unknown"))
            for key, label in self.services
        }
        self._lamps = {}
        self._checked_at = "aún no"
        self._health_queue = queue.Queue()
        self._stop = threading.Event()
        self._style()
        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="")
        self.user_var = tk.StringVar(value="")
        self.warning_var = tk.StringVar(value="")
        self.checked_var = tk.StringVar(value="Última comprobación: aún no")
        self.login_state_var = self.state_vars["login"]
        self.books_state_var = self.state_vars["books"]
        self.protocol("WM_DELETE_WINDOW", self._close)
        threading.Thread(target=self._health_loop, daemon=True).start()
        self.after(400, self._drain_health)
        self.after(15000, self._poll_session)
        self._open_according_to_session()

    def _style(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=26, font=("TkDefaultFont", 10))
        style.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"))
        style.configure("TNotebook.Tab", padding=(12, 8))

    def _clear(self):
        self.unbind("<Return>")
        for child in self.container.winfo_children():
            child.destroy()

    def _note_http(self):
        self.status_var.set("Última respuesta: " + (self.http.last_exchange or "—"))

    def _open_according_to_session(self):
        had_cookies = self.http.has_stored_cookies()
        try:
            payload = self.auth.session()
        except ApiError as exc:
            self._note_http()
            if exc.status == 0:
                self.show_login(
                    "No se pudo comprobar la sesión porque el login no responde. "
                    "Los datos locales se conservan."
                )
                return
            self.show_login(str(exc))
            return
        self._note_http()
        state = payload.get("session") or {}
        if state.get("authenticated") and self.auth.user:
            if not self.http.token:
                self.show_login("La sesión existe, pero falta el JWT. Vuelve a entrar para obtenerlo.")
                return
            self.show_main()
            return
        if had_cookies or self.http.token:
            self.http.clear_cookies()
            self.http.clear_token()
            self.show_login("La sesión guardada ya no es válida en el servidor. Vuelve a entrar.")
            return
        self.show_login()

    def show_login(self, notice=""):
        self._clear()
        card = tk.Frame(self.container, bg=CARD, highlightbackground="#d9dee7", highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center")
        inner = tk.Frame(card, bg=CARD, padx=28, pady=22)
        inner.pack()
        tk.Label(inner, text="Librería", bg=CARD, fg=NAVY, font=("TkDefaultFont", 22, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        tk.Label(inner, text="Correo y contraseña del microservicio de login.", bg=CARD, fg="#445066").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 8)
        )
        if notice:
            tk.Label(inner, text=notice, bg=CARD, fg=RED, wraplength=420, justify="left").grid(
                row=2, column=0, columnspan=2, sticky="w", pady=(0, 8)
            )
        email = tk.StringVar()
        password = tk.StringVar()
        tk.Label(inner, text="Correo", bg=CARD).grid(row=3, column=0, sticky="w")
        email_entry = tk.Entry(inner, textvariable=email, width=42)
        email_entry.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        tk.Label(inner, text="Contraseña", bg=CARD).grid(row=5, column=0, sticky="w")
        tk.Entry(inner, textvariable=password, show="*", width=42).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(2, 14)
        )

        def submit(_event=None):
            if not email.get().strip() or not password.get():
                messagebox.showerror("Login", "Escribe correo y contraseña.", parent=self)
                return
            try:
                self.auth.login(email.get(), password.get())
            except ApiError as exc:
                self._note_http()
                messagebox.showerror("Login", str(exc), parent=self)
                return
            self._note_http()
            self.show_main()

        tk.Button(inner, text="Entrar", command=submit, bg=NAVY, fg="white", padx=12, pady=6, relief="flat").grid(
            row=7, column=0, sticky="w"
        )
        tk.Button(inner, text="Registrar", command=self.show_register, padx=12, pady=6).grid(
            row=7, column=1, sticky="e"
        )
        email_entry.focus_set()
        self.bind("<Return>", submit)

    def show_register(self):
        self._clear()
        card = tk.Frame(self.container, bg=CARD, highlightbackground="#d9dee7", highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center")
        inner = tk.Frame(card, bg=CARD, padx=28, pady=18)
        inner.pack()
        tk.Label(inner, text="Registrar", bg=CARD, fg=NAVY, font=("TkDefaultFont", 18, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        tk.Label(
            inner,
            text="Contraseña de al menos 8 caracteres, con letras y números. El captcha lo pide el login.",
            bg=CARD,
            fg="#445066",
            wraplength=460,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))
        fields = {key: tk.StringVar() for key in ("nombre", "paterno", "materno", "email", "password", "captcha")}
        labels = [
            ("Nombre", "nombre", False),
            ("Apellido paterno", "paterno", False),
            ("Apellido materno", "materno", False),
            ("Correo", "email", False),
            ("Contraseña", "password", True),
        ]
        for index, (label, key, secret) in enumerate(labels):
            tk.Label(inner, text=label, bg=CARD).grid(row=2 + index * 2, column=0, sticky="w")
            tk.Entry(inner, textvariable=fields[key], width=42, show="*" if secret else "").grid(
                row=3 + index * 2, column=0, columnspan=2, sticky="ew", pady=(2, 6)
            )
        captcha_var = tk.StringVar(value="Cargando captcha…")
        captcha_id = {"value": ""}
        tk.Label(inner, textvariable=captcha_var, bg=CARD, fg=NAVY).grid(row=14, column=0, columnspan=2, sticky="w")
        tk.Entry(inner, textvariable=fields["captcha"], width=16).grid(row=15, column=0, sticky="w")

        def load_captcha():
            try:
                challenge = self.auth.captcha()
            except ApiError as exc:
                self._note_http()
                captcha_id["value"] = ""
                captcha_var.set(str(exc))
                return
            self._note_http()
            captcha_id["value"] = challenge.get("captchaId") or ""
            captcha_var.set("Captcha: " + str(challenge.get("question") or ""))
            fields["captcha"].set("")

        def submit():
            if any(not fields[key].get().strip() for key in fields):
                messagebox.showerror("Registro", "Completa todos los campos, incluido el captcha.", parent=self)
                return
            try:
                self.auth.register(
                    fields["nombre"].get().strip(),
                    fields["paterno"].get().strip(),
                    fields["materno"].get().strip(),
                    fields["email"].get().strip(),
                    fields["password"].get(),
                    captcha_id["value"],
                    fields["captcha"].get().strip(),
                )
            except ApiError as exc:
                self._note_http()
                load_captcha()
                messagebox.showerror("Registro", str(exc), parent=self)
                return
            self._note_http()
            self.show_main()

        tk.Button(inner, text="Otro captcha", command=load_captcha).grid(row=15, column=1, sticky="w")
        tk.Button(inner, text="Crear cuenta", command=submit, bg=NAVY, fg="white", padx=12, pady=6, relief="flat").grid(
            row=16, column=0, sticky="w", pady=(12, 0)
        )
        tk.Button(inner, text="Volver", command=self.show_login, padx=12, pady=6).grid(
            row=16, column=1, sticky="e", pady=(12, 0)
        )
        load_captcha()

    def show_main(self):
        self._clear()
        self._refresh_user()
        root = tk.Frame(self.container, bg=BG)
        root.pack(fill="both", expand=True)
        header = tk.Frame(root, bg=NAVY, padx=14, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Librería", bg=NAVY, fg="white", font=("TkDefaultFont", 16, "bold")).pack(side="left")
        tk.Button(header, text="Cerrar sesión", command=self._logout, padx=10, pady=4).pack(side="right")
        tk.Label(header, textvariable=self.user_var, bg=NAVY, fg="#d6e2f0").pack(side="right", padx=12)

        signal = tk.Frame(root, bg=CARD, padx=12, pady=8)
        signal.pack(fill="x", padx=10, pady=(10, 0))
        lamps = tk.Frame(signal, bg=CARD)
        lamps.pack(side="left", fill="x", expand=True)
        self._lamps = {}
        for index, (key, _label) in enumerate(self.services):
            cell = tk.Frame(lamps, bg=CARD)
            cell.grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 12), pady=2)
            canvas = tk.Canvas(cell, width=22, height=22, bg=CARD, highlightthickness=0)
            canvas.pack(side="left")
            dot = canvas.create_oval(2, 2, 20, 20, fill=DIM, outline="")
            self._lamps[key] = (canvas, dot)
            tk.Label(cell, textvariable=self.state_vars[key], bg=CARD).pack(side="left", padx=(4, 0))
        side = tk.Frame(signal, bg=CARD)
        side.pack(side="right")
        tk.Label(side, textvariable=self.checked_var, bg=CARD, fg="#445066").pack(anchor="e")
        tk.Button(side, text="Comprobar ahora", command=self._check_now).pack(anchor="e", pady=(4, 0))
        self._paint_health()

        self.warning_label = tk.Label(root, textvariable=self.warning_var, bg=BG, fg="#7a4b00", anchor="w")
        self.warning_label.pack(fill="x", padx=10, pady=(8, 0))
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.profile_tab = tk.Frame(self.notebook, bg=BG)
        self.catalog_tab = tk.Frame(self.notebook, bg=BG)
        self.admin_tab = tk.Frame(self.notebook, bg=BG)
        self.users_tab = tk.Frame(self.notebook, bg=BG)
        self.authors_tab = tk.Frame(self.notebook, bg=BG)
        self.orders_tab = tk.Frame(self.notebook, bg=BG)
        self.payments_tab = tk.Frame(self.notebook, bg=BG)
        self.health_tab = tk.Frame(self.notebook, bg=BG)
        self.config_tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.profile_tab, text="Sesión y perfil")
        self.notebook.add(self.catalog_tab, text="Catálogo")
        self.notebook.add(self.admin_tab, text="Libros")
        self.notebook.add(self.users_tab, text="Usuarios")
        self.notebook.add(self.authors_tab, text="Autores")
        self.notebook.add(self.orders_tab, text="Pedidos")
        self.notebook.add(self.payments_tab, text="Pagos")
        self.notebook.add(self.health_tab, text="Estado de los servicios")
        self.notebook.add(self.config_tab, text="Configuración")
        self._build_profile()
        self._build_catalog()
        self._build_admin()
        self.panels.build_users(self.users_tab)
        self.panels.build_authors(self.authors_tab)
        self.panels.build_orders(self.orders_tab)
        self.panels.build_payments(self.payments_tab)
        self._build_health_tab()
        self._build_config()
        tk.Label(root, textvariable=self.status_var, bg=BG, fg="#445066", anchor="w").pack(fill="x", padx=10, pady=(0, 8))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab)
        self._apply_session_warning()
        self.reload_catalog()

    def _refresh_user(self):
        user = self.auth.user or {}
        name = user.get("full_name") or user.get("email") or ""
        role = user.get("role") or ""
        self.user_var.set(f"{name}   ·   {role}".strip(" ·"))

    def _logout(self):
        self.auth.logout()
        self._note_http()
        self.catalog = []
        self.show_login("Sesión cerrada en el servidor.")

    def _poll_session(self):
        if not self._stop.is_set():
            if self.auth.user and self.notebook_alive():
                try:
                    payload = self.auth.session()
                except ApiError as exc:
                    self._note_http()
                    if exc.status == 0:
                        self.warning_var.set("No se pudo renovar el estado de la sesión: el login no responde.")
                    elif exc.status == 401:
                        self.force_login("La sesión expiró en el servidor.")
                else:
                    self._note_http()
                    state = payload.get("session") or {}
                    if not state.get("authenticated"):
                        self.http.clear_cookies()
                        self.http.clear_token()
                        self.force_login("La sesión expiró en el servidor.")
                    else:
                        self._renew_token_if_needed()
                        self._apply_session_warning(payload)
                        self._refresh_user()
            self.after(15000, self._poll_session)

    def notebook_alive(self):
        return getattr(self, "notebook", None) is not None and self.notebook.winfo_exists()

    def _apply_session_warning(self, payload=None):
        if payload is None:
            self.warning_var.set("")
            if getattr(self, "warning_label", None) is not None and self.warning_label.winfo_exists():
                self.warning_label.configure(bg=BG)
            return
        state = payload.get("session") or {}
        notice = state.get("notification") or {}
        remaining = state.get("remainingSeconds")
        def show(text):
            self.warning_var.set(text)
            if getattr(self, "warning_label", None) is not None and self.warning_label.winfo_exists():
                self.warning_label.configure(bg="#fff4d6" if text else BG)

        if isinstance(notice, dict) and notice.get("message") and (
            notice.get("code") in ("SESSION_EXPIRING", "SESSION_EXPIRED") or (isinstance(remaining, int) and remaining <= 120)
        ):
            show(notice.get("message"))
            return
        if isinstance(remaining, int) and remaining <= 120:
            show(f"La sesión expira en {remaining} segundos. Puedes extenderla en Sesión y perfil.")
            return
        show("")

    def force_login(self, message):
        self.auth.user = None
        self.http.clear_token()
        self.show_login(message)

    def prompt_login(self):
        dialog = tk.Toplevel(self)
        dialog.title("Iniciar sesión")
        dialog.transient(self)
        dialog.configure(bg=CARD)
        frame = tk.Frame(dialog, bg=CARD, padx=16, pady=14)
        frame.pack()
        tk.Label(
            frame,
            text="La escritura necesita un JWT vigente, emitido por el login.",
            bg=CARD,
            wraplength=360,
            justify="left",
        ).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        email = tk.StringVar(value=(self.auth.user or {}).get("email") or "")
        password = tk.StringVar()
        tk.Label(frame, text="Correo", bg=CARD).grid(row=1, column=0, sticky="w")
        tk.Entry(frame, textvariable=email, width=36).grid(row=2, column=0, columnspan=2, pady=(2, 6))
        tk.Label(frame, text="Contraseña", bg=CARD).grid(row=3, column=0, sticky="w")
        tk.Entry(frame, textvariable=password, show="*", width=36).grid(row=4, column=0, columnspan=2, pady=(2, 10))
        result = {"ok": False}

        def submit():
            try:
                self.auth.login(email.get(), password.get())
            except ApiError as exc:
                self._note_http()
                messagebox.showerror("Login", str(exc), parent=dialog)
                return
            self._note_http()
            result["ok"] = True
            dialog.destroy()

        tk.Button(frame, text="Entrar", command=submit, bg=NAVY, fg="white", relief="flat", padx=10, pady=4).grid(row=5, column=0, sticky="w")
        tk.Button(frame, text="Cancelar", command=dialog.destroy, padx=10, pady=4).grid(row=5, column=1, sticky="e")
        dialog.grab_set()
        dialog.bind("<Return>", lambda _event: submit())
        dialog.wait_window()
        if result["ok"]:
            self._refresh_user()
        return result["ok"]

    def _ensure_session(self):
        if self.auth.session_active() and self.http.token:
            self._note_http()
            return True
        return self.prompt_login()

    def _build_profile(self):
        box = tk.Frame(self.profile_tab, bg=CARD, padx=16, pady=14)
        box.pack(fill="both", expand=True, padx=8, pady=8)
        self.profile_text = tk.StringVar(value="Cargando sesión…")
        tk.Label(box, text="Sesión", bg=CARD, fg=NAVY, font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        tk.Label(box, textvariable=self.profile_text, bg=CARD, justify="left", anchor="w").pack(anchor="w", pady=(4, 8))
        tk.Button(box, text="Renovar JWT antes de que caduque", command=self._extend).pack(anchor="w")
        tk.Label(box, text="Perfil", bg=CARD, fg=NAVY, font=("TkDefaultFont", 13, "bold")).pack(anchor="w", pady=(16, 4))
        tk.Label(
            box,
            text="El correo no se cambia. La contraseña pide la actual, la nueva y la confirmación, y viaja al microservicio de usuarios.",
            bg=CARD,
            fg="#445066",
        ).pack(anchor="w")
        form = tk.Frame(box, bg=CARD)
        form.pack(anchor="w", pady=8)
        self.profile_fields = {
            key: tk.StringVar()
            for key in ("nombre", "paterno", "materno", "email", "current", "new", "confirm")
        }
        rows = [
            ("Nombre", "nombre", False),
            ("Apellido paterno", "paterno", False),
            ("Apellido materno", "materno", False),
            ("Correo (no se cambia)", "email", False),
            ("Contraseña actual", "current", True),
            ("Contraseña nueva", "new", True),
            ("Confirmar contraseña", "confirm", True),
        ]
        for index, (label, key, secret) in enumerate(rows):
            tk.Label(form, text=label, bg=CARD).grid(row=index, column=0, sticky="w", padx=(0, 8), pady=3)
            tk.Entry(form, textvariable=self.profile_fields[key], width=36, show="*" if secret else "").grid(
                row=index, column=1, sticky="w", pady=3
            )
        tk.Button(box, text="Guardar perfil", command=self._save_profile, bg=NAVY, fg="white", relief="flat", padx=10, pady=6).pack(anchor="w", pady=(8, 0))
        self._fill_profile()

    def _fill_profile(self):
        user = self.auth.user or {}
        self.profile_fields["nombre"].set(user.get("first_name") or "")
        self.profile_fields["paterno"].set(user.get("paternal_surname") or "")
        self.profile_fields["materno"].set(user.get("maternal_surname") or "")
        self.profile_fields["email"].set(user.get("email") or "")
        self.profile_fields["current"].set("")
        self.profile_fields["new"].set("")
        self.profile_fields["confirm"].set("")
        verified = "sí" if user.get("emailVerified") else "no"
        self.profile_text.set(
            "\n".join(
                [
                    f"Nombre: {_blank(user.get('full_name'))}",
                    f"Correo: {_blank(user.get('email'))}",
                    f"Rol: {_blank(user.get('role'))}",
                    f"Correo verificado: {verified}",
                    "La cookie de sesión está en este equipo y se vuelve a comprobar con GET /session.",
                ]
            )
        )

    def _extend(self):
        if not self._ensure_session():
            return
        try:
            payload = self.auth.extend()
        except ApiError as exc:
            self._note_http()
            if exc.status == 401:
                self.force_login(str(exc))
                return
            messagebox.showerror("Sesión", str(exc), parent=self)
            return
        self._note_http()
        self._apply_session_warning(payload)
        self._fill_profile()
        messagebox.showinfo("Sesión", "El JWT de acceso se renovó.", parent=self)

    def _save_profile(self):
        if not self._ensure_session():
            return
        user = self.auth.user or {}
        changes = {}
        mapping = (
            ("nombre", "nombre", "first_name"),
            ("paterno", "apellidoPaterno", "paternal_surname"),
            ("materno", "apellidoMaterno", "maternal_surname"),
            ("email", "email", "email"),
        )
        email = self.profile_fields["email"].get().strip()
        if email and email != (user.get("email") or ""):
            messagebox.showerror(
                "Perfil",
                "El correo identifica la cuenta y no se puede cambiar.",
                parent=self,
            )
            return
        for key, remote, source in mapping:
            if key == "email":
                continue
            value = self.profile_fields[key].get().strip()
            current = user.get(source) or ""
            if value and value != current:
                changes[remote] = value
        current_password = self.profile_fields["current"].get()
        new_password = self.profile_fields["new"].get()
        confirm_password = self.profile_fields["confirm"].get()
        changing_password = any((current_password, new_password, confirm_password))
        if not changes and not changing_password:
            messagebox.showinfo("Perfil", "No hay cambios respecto a la sesión actual.", parent=self)
            return
        try:
            if changes:
                self.auth.update_profile(changes)
            if changing_password:
                user_id = (self.auth.user or user).get("id")
                if not user_id:
                    raise ApiError("La sesión no trae el id del usuario.", 400)
                self.users.change_password(user_id, current_password, new_password, confirm_password)
        except ApiError as exc:
            self._note_http()
            text = str(exc).lower()
            if exc.status == 401 and any(word in text for word in ("token", "authorization", "sesión", "sesion")):
                self.force_login(str(exc))
                return
            messagebox.showerror("Perfil", str(exc), parent=self)
            return
        self._note_http()
        self._refresh_user()
        self._fill_profile()
        messagebox.showinfo("Perfil", "Perfil actualizado.", parent=self)

    def _build_catalog(self):
        bar = tk.Frame(self.catalog_tab, bg=BG, pady=8)
        bar.pack(fill="x", padx=8)
        self.filters = {key: tk.StringVar() for key in ("isbn", "title", "year", "min", "max")}
        for label, key, width in (
            ("ISBN", "isbn", 16),
            ("Título", "title", 18),
            ("Año", "year", 6),
            ("Precio mín.", "min", 8),
            ("Precio máx.", "max", 8),
        ):
            tk.Label(bar, text=label, bg=BG).pack(side="left")
            tk.Entry(bar, textvariable=self.filters[key], width=width).pack(side="left", padx=(4, 8))
        tk.Button(bar, text="Buscar", command=self._apply_filter).pack(side="left")
        tk.Button(bar, text="Limpiar", command=self._clear_filter).pack(side="left", padx=4)
        tk.Button(bar, text="Ver detalle", command=self._show_detail).pack(side="left", padx=(12, 0))
        tk.Button(bar, text="Recargar", command=self.reload_catalog).pack(side="right")
        columns = ("isbn", "title", "authors", "genre", "year", "price", "stock", "format", "category", "image")
        self.tree = ttk.Treeview(self.catalog_tab, columns=columns, show="headings", selectmode="browse")
        headings = {
            "isbn": "ISBN",
            "title": "Título",
            "authors": "Autores",
            "genre": "Género",
            "year": "Año",
            "price": "Precio",
            "stock": "Existencia",
            "format": "Formato",
            "category": "Categoría",
            "image": "Imagen",
        }
        widths = {
            "isbn": 130,
            "title": 220,
            "authors": 160,
            "genre": 110,
            "year": 60,
            "price": 70,
            "stock": 80,
            "format": 100,
            "category": 140,
            "image": 80,
        }
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="w")
        scroll = ttk.Scrollbar(self.catalog_tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        scroll.pack(side="left", fill="y", padx=(0, 8), pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _event: self._show_detail())

    def reload_catalog(self):
        try:
            self.catalog = self.books.list_books()
        except ApiError as exc:
            self._note_http()
            self.catalog = []
            self.status_var.set(str(exc))
        else:
            self._note_http()
            self.status_var.set(f"{len(self.catalog)} libros. " + self.status_var.get())
        self._apply_filter()

    def _apply_filter(self):
        if not getattr(self, "tree", None) or not self.tree.winfo_exists():
            return
        try:
            rows = filter_books(
                self.catalog,
                self.filters["isbn"].get(),
                self.filters["title"].get(),
                self.filters["year"].get(),
                self.filters["min"].get(),
                self.filters["max"].get(),
            )
        except ValueError:
            messagebox.showerror("Buscar", "El precio mínimo y el máximo deben ser números.", parent=self)
            return
        self.tree.delete(*self.tree.get_children())
        for book in rows:
            isbn = str(book.get("isbn") or "")
            if not isbn:
                continue
            self.tree.insert(
                "",
                "end",
                iid=isbn,
                values=(
                    isbn,
                    book.get("title") or "",
                    authors_text(book),
                    _blank(book.get("genre")) if book.get("genre") else "No informado",
                    book.get("publicationYear") if book.get("publicationYear") is not None else "",
                    book.get("price") if book.get("price") is not None else "",
                    book.get("stock") if book.get("stock") is not None else "",
                    _blank(book.get("format")) if book.get("format") else "No informado",
                    book.get("category") or "",
                    "Sí" if has_image(book) else "Sin imagen",
                ),
            )

    def _clear_filter(self):
        for var in self.filters.values():
            var.set("")
        self._apply_filter()

    def _selected_isbn(self):
        if not getattr(self, "tree", None) or not self.tree.winfo_exists():
            return ""
        selected = self.tree.selection()
        return selected[0] if selected else ""

    def _show_detail(self):
        isbn = self._selected_isbn()
        if not isbn:
            messagebox.showinfo("Detalle", "Selecciona un libro del catálogo.", parent=self)
            return
        try:
            book = self.books.get_book(isbn)
        except ApiError as exc:
            self._note_http()
            messagebox.showerror("Detalle", str(exc), parent=self)
            return
        self._note_http()
        self._detail_window(book)

    def _detail_window(self, book):
        dialog = tk.Toplevel(self)
        dialog.title(book.get("title") or "Libro")
        dialog.geometry("640x520")
        dialog.transient(self)
        images = list(book.get("images") or [])
        if not images and book.get("coverUrl"):
            images = [{"url": book.get("coverUrl"), "alt": "Portada", "mimeType": "image/svg+xml"}]
        index = {"value": 0}
        preview = tk.Label(dialog, bg="#e8edf2", width=42, height=8, justify="center", relief="groove")
        preview.pack(fill="x", padx=12, pady=(12, 4))

        def paint():
            if not images:
                preview.configure(text="Sin imagen\nEste libro no trae portada.")
                return
            image = images[index["value"] % len(images)]
            mime = image.get("mimeType") or ""
            preview.configure(
                text=(
                    f"Imagen {index['value'] + 1} de {len(images)}\n"
                    f"{image.get('alt') or 'Sin texto alternativo'}\n"
                    f"{image.get('url') or ''}\n"
                    f"{mime or 'tipo no indicado'}\n"
                    "Tk no dibuja SVG; la ficha muestra la referencia sin fallar."
                )
            )

        nav = tk.Frame(dialog)
        nav.pack(pady=4)

        def shift(step):
            if not images:
                return
            index["value"] = (index["value"] + step) % len(images)
            paint()

        tk.Button(nav, text="Imagen anterior", command=lambda: shift(-1)).pack(side="left", padx=4)
        tk.Button(nav, text="Imagen siguiente", command=lambda: shift(1)).pack(side="left", padx=4)
        paint()
        text = tk.Text(dialog, wrap="word", height=16)
        text.pack(fill="both", expand=True, padx=12, pady=8)
        concepts = book.get("concepts") or []
        concept_lines = [
            f"- {item.get('name')}: {item.get('definition')}" for item in concepts if isinstance(item, dict)
        ] or ["Este libro no tiene conceptos asociados."]
        text.insert(
            "1.0",
            "\n".join(
                [
                    f"ISBN: {_blank(book.get('isbn'))}",
                    f"Título: {_blank(book.get('title'))}",
                    f"Autores: {_blank(authors_text(book))}",
                    f"Género: {_blank(book.get('genre'))}",
                    f"Año: {_blank(book.get('publicationYear'))}",
                    f"Precio: {_blank(book.get('price'))}",
                    f"Existencia: {_blank(book.get('stock'))}",
                    f"Formato: {_blank(book.get('format'))}",
                    f"Categoría: {_blank(book.get('category'))}",
                    f"Descripción: {_blank(book.get('description'))}",
                    "",
                    "Conceptos:",
                    *concept_lines,
                ]
            ),
        )
        text.configure(state="disabled")

    def _build_admin(self):
        wrap = tk.Frame(self.admin_tab, bg=BG)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(
            wrap,
            text="PUT envía el libro completo. PATCH envía un solo campo. Eliminar pide confirmación.",
            bg=BG,
            fg="#445066",
        ).pack(anchor="w")
        form = tk.Frame(wrap, bg=CARD, padx=12, pady=10)
        form.pack(fill="x", pady=8)
        self.admin_fields = {
            key: tk.StringVar()
            for key in ("isbn", "title", "authors", "genre", "year", "price", "stock", "format", "category", "description")
        }
        labels = [
            ("ISBN", "isbn"),
            ("Título", "title"),
            ("Autores (coma)", "authors"),
            ("Género", "genre"),
            ("Año", "year"),
            ("Precio", "price"),
            ("Existencia", "stock"),
            ("Formato", "format"),
            ("Categoría", "category"),
            ("Descripción", "description"),
        ]
        for index, (label, key) in enumerate(labels):
            column = 0 if index < 5 else 2
            row = index if index < 5 else index - 5
            tk.Label(form, text=label, bg=CARD).grid(row=row, column=column, sticky="w", padx=(0, 6), pady=3)
            tk.Entry(form, textvariable=self.admin_fields[key], width=28).grid(row=row, column=column + 1, sticky="w", pady=3)
        buttons = tk.Frame(wrap, bg=BG)
        buttons.pack(fill="x")
        tk.Button(buttons, text="Cargar ISBN", command=self._load_admin).pack(side="left")
        tk.Button(buttons, text="Crear POST", command=self._create_book).pack(side="left", padx=6)
        tk.Button(buttons, text="Reemplazar PUT", command=self._put_book).pack(side="left", padx=6)
        self.patch_field = tk.StringVar(value="title")
        ttk.Combobox(
            buttons,
            textvariable=self.patch_field,
            values=("title", "authors", "genre", "publicationYear", "price", "stock", "format", "category", "description"),
            width=16,
            state="readonly",
        ).pack(side="left", padx=(16, 4))
        tk.Button(buttons, text="Cambiar un campo PATCH", command=self._patch_book).pack(side="left")
        tk.Button(buttons, text="Eliminar", command=self._delete_book).pack(side="left", padx=12)

    def _admin_isbn(self):
        return self.admin_fields["isbn"].get().strip() or self._selected_isbn()

    def _load_admin(self):
        isbn = self._admin_isbn()
        if not isbn:
            messagebox.showinfo("Administración", "Escribe o selecciona un ISBN.", parent=self)
            return
        try:
            book = self.books.get_book(isbn)
        except ApiError as exc:
            self._note_http()
            messagebox.showerror("Administración", str(exc), parent=self)
            return
        self._note_http()
        self.admin_fields["isbn"].set(str(book.get("isbn") or isbn))
        self.admin_fields["title"].set(str(book.get("title") or ""))
        self.admin_fields["authors"].set(authors_text(book))
        self.admin_fields["genre"].set(str(book.get("genre") or ""))
        self.admin_fields["year"].set("" if book.get("publicationYear") is None else str(book.get("publicationYear")))
        self.admin_fields["price"].set("" if book.get("price") is None else str(book.get("price")))
        self.admin_fields["stock"].set("" if book.get("stock") is None else str(book.get("stock")))
        self.admin_fields["format"].set(str(book.get("format") or ""))
        self.admin_fields["category"].set(str(book.get("category") or ""))
        self.admin_fields["description"].set(str(book.get("description") or ""))

    def _full_payload(self):
        title = self.admin_fields["title"].get().strip()
        authors = [part.strip() for part in self.admin_fields["authors"].get().split(",") if part.strip()]
        category = self.admin_fields["category"].get().strip()
        year = self.admin_fields["year"].get().strip()
        price = self.admin_fields["price"].get().strip().replace(",", ".")
        missing = [
            name
            for name, value in (("título", title), ("autores", authors), ("categoría", category), ("año", year), ("precio", price))
            if not value
        ]
        if missing:
            raise ValueError("PUT y POST necesitan " + ", ".join(missing) + ".")
        payload = {
            "isbn": self._admin_isbn(),
            "title": title,
            "authors": authors,
            "category": category,
            "publicationYear": int(year),
            "price": float(price),
            "description": self.admin_fields["description"].get().strip(),
            "format": self.admin_fields["format"].get().strip(),
            "genre": self.admin_fields["genre"].get().strip(),
        }
        stock = self.admin_fields["stock"].get().strip()
        if stock:
            payload["stock"] = int(stock)
        return payload

    def _mutate(self, action):
        if not self._ensure_session():
            return False
        try:
            action()
        except ApiError as exc:
            self._note_http()
            if exc.status == 401:
                self.force_login(str(exc))
                return False
            messagebox.showerror("Libros", str(exc), parent=self)
            return False
        except ValueError as exc:
            messagebox.showerror("Libros", str(exc), parent=self)
            return False
        self._note_http()
        self.reload_catalog()
        return True

    def _create_book(self):
        def action():
            payload = self._full_payload()
            if not payload["isbn"]:
                raise ValueError("El ISBN es obligatorio para crear.")
            self.books.create_book(payload)

        if self._mutate(action):
            messagebox.showinfo("Libros", "Libro creado. El catálogo se volvió a consultar.", parent=self)

    def _put_book(self):
        isbn = self._admin_isbn()

        def action():
            if not isbn:
                raise ValueError("Indica el ISBN que vas a reemplazar.")
            self.books.replace_book(isbn, self._full_payload())

        if self._mutate(action):
            messagebox.showinfo(
                "PUT",
                "Se envió el libro completo (título, autores, categoría, año, precio y el resto del formulario).",
                parent=self,
            )

    def _patch_value(self):
        field = self.patch_field.get()
        raw = {
            "title": self.admin_fields["title"].get().strip(),
            "authors": self.admin_fields["authors"].get().strip(),
            "genre": self.admin_fields["genre"].get().strip(),
            "publicationYear": self.admin_fields["year"].get().strip(),
            "price": self.admin_fields["price"].get().strip().replace(",", "."),
            "stock": self.admin_fields["stock"].get().strip(),
            "format": self.admin_fields["format"].get().strip(),
            "category": self.admin_fields["category"].get().strip(),
            "description": self.admin_fields["description"].get().strip(),
        }[field]
        if raw == "":
            raise ValueError("Escribe el valor del campo que vas a cambiar con PATCH.")
        if field == "authors":
            return {"authors": [part.strip() for part in raw.split(",") if part.strip()]}
        if field == "publicationYear":
            return {"publicationYear": int(raw)}
        if field == "price":
            return {"price": float(raw)}
        if field == "stock":
            return {"stock": int(raw)}
        return {field: raw}

    def _patch_book(self):
        isbn = self._admin_isbn()

        def action():
            if not isbn:
                raise ValueError("Indica el ISBN.")
            changes = self._patch_value()
            self.books.patch_book(isbn, changes)

        if self._mutate(action):
            messagebox.showinfo(
                "PATCH",
                f"Solo se envió el campo «{self.patch_field.get()}». El resto no viajó en la petición.",
                parent=self,
            )

    def _delete_book(self):
        isbn = self._admin_isbn()
        if not isbn:
            messagebox.showinfo("Eliminar", "Indica el ISBN.", parent=self)
            return
        if not messagebox.askyesno("Eliminar", f"¿Eliminar el libro {isbn}? Esta acción llama a DELETE /books/{isbn}.", parent=self):
            return

        def action():
            self.books.delete_book(isbn)

        if self._mutate(action):
            messagebox.showinfo("Eliminar", "Libro eliminado. El catálogo se consultó de nuevo.", parent=self)

    def _build_health_tab(self):
        box = tk.Frame(self.health_tab, bg=CARD, padx=16, pady=16)
        box.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(box, text="GET /health de cada microservicio", bg=CARD, fg=NAVY, font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        tk.Label(
            box,
            text="Verde: responde y su base está disponible. Amarillo: responde, pero la dependencia falló. Rojo: no hay conexión. La comprobación se repite sola y también con el botón.",
            bg=CARD,
            fg="#445066",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(6, 10))
        self.health_detail = tk.StringVar(value="")
        tk.Label(box, textvariable=self.health_detail, bg=CARD, justify="left", anchor="w").pack(anchor="w")
        tk.Button(box, text="Comprobar ahora", command=self._check_now).pack(anchor="w", pady=(12, 0))

    def _build_config(self):
        box = tk.Frame(self.config_tab, bg=CARD, padx=16, pady=16)
        box.pack(fill="x", padx=8, pady=8)
        tk.Label(box, text="Servidor", bg=CARD, fg=NAVY, font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        tk.Label(
            box,
            text="Estas URLs se guardan en este equipo. Sirven para localhost y para la IP de la instancia, sin cambiar el código.",
            bg=CARD,
            fg="#445066",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))
        self.scheme_var = tk.StringVar(value=self.scheme if self.scheme in ("http", "https") else "http")
        scheme_row = tk.Frame(box, bg=CARD)
        scheme_row.pack(anchor="w", pady=(0, 8))
        tk.Label(scheme_row, text="Protocolo de las peticiones", bg=CARD).pack(side="left", padx=(0, 8))
        tk.Radiobutton(
            scheme_row, text="HTTP", variable=self.scheme_var, value="http", bg=CARD, command=self._apply_scheme
        ).pack(side="left")
        tk.Radiobutton(
            scheme_row, text="HTTPS", variable=self.scheme_var, value="https", bg=CARD, command=self._apply_scheme
        ).pack(side="left")
        tk.Label(
            box,
            text="HTTP queda seleccionado por defecto y la elección se guarda en este equipo.",
            bg=CARD,
            fg="#445066",
        ).pack(anchor="w", pady=(0, 8))
        self.url_vars = {
            "loginUrl": tk.StringVar(value=self.http.login_url),
            "booksUrl": tk.StringVar(value=self.http.books_url),
            "usersUrl": tk.StringVar(value=self.http.users_url),
            "authorsUrl": tk.StringVar(value=self.http.authors_url),
            "pedidosUrl": tk.StringVar(value=self.http.pedidos_url),
            "pagosUrl": tk.StringVar(value=self.http.pagos_url),
        }
        self.login_url_var = self.url_vars["loginUrl"]
        self.books_url_var = self.url_vars["booksUrl"]
        for label, key in (
            ("Login", "loginUrl"),
            ("Books", "booksUrl"),
            ("Users", "usersUrl"),
            ("Autores", "authorsUrl"),
            ("Pedidos", "pedidosUrl"),
            ("Pagos", "pagosUrl"),
        ):
            tk.Label(box, text=label, bg=CARD).pack(anchor="w")
            tk.Entry(box, textvariable=self.url_vars[key], width=52).pack(anchor="w", pady=(2, 6))
        tk.Label(box, text=str(config_path()), bg=CARD, fg="#667085").pack(anchor="w", pady=(4, 8))
        row = tk.Frame(box, bg=CARD)
        row.pack(anchor="w")
        tk.Button(row, text="Probar", command=self._test_config).pack(side="left")
        tk.Button(row, text="Guardar", command=self._save_config, bg=NAVY, fg="white", relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(row, text="Restaurar predeterminados", command=self._restore_config).pack(side="left")

    def _endpoint_values(self):
        return {key: var.get() for key, var in self.url_vars.items()}

    def _apply_urls(self, stored):
        self.scheme = stored.get("scheme") or "http"
        if getattr(self, "scheme_var", None) is not None:
            self.scheme_var.set(self.scheme)
        self.http.set_endpoints(
            stored["loginUrl"],
            stored["booksUrl"],
            stored.get("usersUrl"),
            stored.get("authorsUrl"),
            stored.get("pedidosUrl"),
            stored.get("pagosUrl"),
        )
        if getattr(self, "url_vars", None):
            self.url_vars["loginUrl"].set(self.http.login_url)
            self.url_vars["booksUrl"].set(self.http.books_url)
            self.url_vars["usersUrl"].set(self.http.users_url)
            self.url_vars["authorsUrl"].set(self.http.authors_url)
            self.url_vars["pedidosUrl"].set(self.http.pedidos_url)
            self.url_vars["pagosUrl"].set(self.http.pagos_url)

    def _apply_scheme(self):
        scheme = self.scheme_var.get()
        for key, var in self.url_vars.items():
            var.set(with_scheme(var.get(), scheme))
        self._save_config(silent=True)

    def _save_config(self, silent=False):
        values = self._endpoint_values()
        stored = save(
            values["loginUrl"],
            values["booksUrl"],
            scheme=self.scheme_var.get(),
            usersUrl=values["usersUrl"],
            authorsUrl=values["authorsUrl"],
            pedidosUrl=values["pedidosUrl"],
            pagosUrl=values["pagosUrl"],
        )
        self._apply_urls(stored)
        if not silent:
            messagebox.showinfo(
                "Configuración",
                "URLs y protocolo guardados. Si cambiaste de máquina, inicia sesión otra vez.",
                parent=self,
            )

    def _restore_config(self):
        stored = restore_defaults()
        self._apply_urls(stored)
        messagebox.showinfo(
            "Configuración",
            "Se restauró HTTP y los puertos locales 5000 a 5005.",
            parent=self,
        )

    def _test_config(self):
        values = self._endpoint_values()
        self.http.set_endpoints(
            values["loginUrl"],
            values["booksUrl"],
            values["usersUrl"],
            values["authorsUrl"],
            values["pedidosUrl"],
            values["pagosUrl"],
        )
        self._check_now()
        messagebox.showinfo(
            "Probar",
            "\n".join(self.state_vars[key].get() for key, _label in self.services) + "\n" + self.checked_var.get(),
            parent=self,
        )

    def _on_tab(self, _event):
        if not self.notebook_alive():
            return
        title = self.notebook.tab(self.notebook.select(), "text")
        if title == "Sesión y perfil":
            try:
                payload = self.auth.session()
            except ApiError as exc:
                self._note_http()
                self.warning_var.set(str(exc))
                return
            self._note_http()
            self._apply_session_warning(payload)
            self._fill_profile()
            self._refresh_user()

    def _renew_token_if_needed(self):
        raw = self.http.token_expires_at
        if not raw or not self.http.refresh_token:
            return
        try:
            expires = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires > datetime.now(timezone.utc) + timedelta(minutes=3):
            return
        try:
            self.auth.refresh()
        except ApiError:
            self._note_http()

    def _check_now(self):
        self._health = self._probe_all()
        self._checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._paint_health()

    def _probe(self, base):
        status, payload = self.http.probe(base)
        return health_api.classify(status, payload)

    def _probe_all(self):
        status = {}
        for key, _label in self.services:
            try:
                status[key] = self._probe(getattr(self.http, f"{key}_url"))
            except Exception:
                status[key] = "down"
        return status

    def _health_loop(self):
        while not self._stop.is_set():
            status = self._probe_all()
            self._health_queue.put((status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            if self._stop.wait(2):
                break

    def _drain_health(self):
        try:
            while True:
                status, stamp = self._health_queue.get_nowait()
                self._health = status
                self._checked_at = stamp
                self._paint_health()
        except queue.Empty:
            pass
        if not self._stop.is_set():
            self.after(200, self._drain_health)

    def _paint_health(self):
        lines = []
        for key, label in self.services:
            state = self._health.get(key, "unknown")
            self.state_vars[key].set(health_api.describe(label, state))
            lines.append(self.state_vars[key].get())
            pair = self._lamps.get(key)
            if pair is not None and pair[0].winfo_exists():
                pair[0].itemconfig(pair[1], fill=STATE_COLOR.get(state, DIM))
        self.checked_var.set("Última comprobación: " + self._checked_at)
        if getattr(self, "health_detail", None) is not None:
            self.health_detail.set(
                "\n".join(
                    lines
                    + [
                        "",
                        self.checked_var.get(),
                        "",
                        "Verde = HTTP 200, base disponible y Redis disponible.",
                        "Amarillo = el proceso contestó, pero PostgreSQL o Redis falló.",
                        "Rojo = conexión rechazada, tiempo agotado o URL incorrecta.",
                        "En books, una lectura pública sigue si Redis no cachea.",
                        "Login, revocación y escrituras se detienen si Redis no responde.",
                    ]
                )
            )

    def _close(self):
        self._stop.set()
        self.destroy()
