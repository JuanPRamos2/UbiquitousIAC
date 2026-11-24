"""
Aplicación de escritorio de Bienestar Nexum. Consume EXCLUSIVAMENTE XML.

QUÉ PROCESO ATIENDE, Y POR QUÉ ESTE Y NO OTRO
---------------------------------------------
Atiende el proceso de **atención de solicitudes de apoyo y lectura del
tablero protegido**: el trabajo del especialista de bienestar y del jefe de
unidad cuando están sentados frente a una computadora, con varias
solicitudes abiertas y el tablero al lado para decidir a cuál atender
primero.

Es un proceso DISTINTO del que atiende la aplicación móvil, que es el de
responder la encuesta y levantar una solicitud desde el teléfono. La
separación no es un reparto arbitrario para cumplir un requisito: son dos
situaciones de uso con necesidades opuestas. Quien responde la encuesta lo
hace una vez cada campaña, en dos minutos, de pie, y necesita una pantalla
por pregunta. Quien atiende solicitudes pasa media hora revisando una tabla
de treinta filas, la ordena, la filtra, la exporta y escribe notas largas;
eso necesita teclado, ventana grande y una tabla de verdad.

POR QUÉ LA LÓGICA DE RED ESTÁ EN OTRO ARCHIVO
---------------------------------------------
Todo lo que habla con los servicios vive en cliente.py, que no importa
Tkinter. Así la parte que se puede equivocar —armar el XML, validarlo
contra el XSD, interpretar un xsi:nil— se prueba sin abrir una ventana y
sin que exista un servidor gráfico. Este archivo es la ventana y nada más.

ESTRUCTURA DE LA VENTANA
------------------------
  Sesión        inicio de sesión, estado del token, renovar, cerrar sesión
  Solicitudes   tabla, filtro por estado, cambio de estado (escritura)
  Tablero       agregados protegidos de una unidad, con sus supresiones
  Riesgo        detecciones del motor de reglas, con su explicación
  Reportes      generar, descargar y verificar el sello
  Diagnóstico   qué servicio respondió, cuánto tardó, y el XML en crudo

Las pestañas que el perfil no puede usar se deshabilitan, pero eso es
cortesía de interfaz: la autorización de verdad la hace cada servicio
consultando usuarios.perfil_permiso en cada petición. Una aplicación que
solo escondiera botones no estaría protegiendo nada.
"""
import os
import sys
import threading
import traceback

# La aplicación debe poder correr desde su propia carpeta sin instalación.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cliente import ClienteXml, ErrorCliente, exportar_csv  # noqa: E402

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as e:  # pragma: no cover - depende del sistema
    print("Esta aplicacion necesita Tkinter.\n"
          "  Debian/Ubuntu: sudo apt-get install python3-tk\n"
          "  Windows y macOS: viene con el instalador oficial de Python\n"
          f"Detalle: {e}", file=sys.stderr)
    raise SystemExit(2)


COLOR_FONDO = "#f4f6f8"
COLOR_TEXTO = "#1f2933"
COLOR_TENUE = "#616e7c"
COLOR_ALTO = "#b42318"
COLOR_MEDIO = "#b54708"
COLOR_BAJO = "#027a48"
COLOR_LIGA = "#1d4ed8"

ESTADOS_SOLICITUD = ("ABIERTA", "EN_PROCESO", "CERRADA")


def _hilo(fn):
    """Corre fn en un hilo aparte.

    Sin esto, cada petición congela la ventana mientras el servicio
    responde: con un tiempo límite de 15 s, un servicio caído deja la
    aplicación sin repintar durante quince segundos y el sistema operativo
    la marca como «no responde». El resultado se entrega de vuelta al hilo
    de la interfaz con `after`, porque Tkinter no admite que otro hilo
    toque los widgets.
    """
    def envoltura(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs,
                         daemon=True).start()
    return envoltura


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bienestar Nexum — Escritorio (XML)")
        self.geometry("1180x740")
        self.minsize(960, 620)
        self.configure(bg=COLOR_FONDO)

        self.cliente = ClienteXml()
        self.ultimo_xml = ""
        self.filas_actuales = []
        self.columnas_actuales = []

        self._estilos()
        self._barra_superior()
        self._cuaderno()
        self._barra_estado()
        self._aplicar_sesion(None)

        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    # ------------------------------------------------------------- estilo
    def _estilos(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=COLOR_FONDO, foreground=COLOR_TEXTO,
                    font=("TkDefaultFont", 10))
        s.configure("TNotebook", background=COLOR_FONDO, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(14, 8))
        s.configure("Titulo.TLabel", font=("TkDefaultFont", 15, "bold"))
        s.configure("Tenue.TLabel", foreground=COLOR_TENUE)
        s.configure("Alto.TLabel", foreground=COLOR_ALTO)
        s.configure("Treeview", rowheight=24, fieldbackground="white")
        s.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"))

    def _barra_superior(self):
        barra = ttk.Frame(self, padding=(14, 10))
        barra.pack(fill="x")
        ttk.Label(barra, text="Bienestar Nexum", style="Titulo.TLabel").pack(side="left")
        ttk.Label(barra, text="  ·  aplicación de escritorio, solo XML",
                  style="Tenue.TLabel").pack(side="left")

        self.lbl_sesion = ttk.Label(barra, text="sin sesión", style="Tenue.TLabel")
        self.lbl_sesion.pack(side="right")
        # El indicador de conexión es un requisito y también una decisión:
        # al lado del perfil, no en una esquina. Es el primer lugar donde se
        # mira cuando algo no carga.
        self.lbl_conexion = ttk.Label(barra, text="●  sin probar", style="Tenue.TLabel")
        self.lbl_conexion.pack(side="right", padx=(0, 16))

    def _barra_estado(self):
        pie = ttk.Frame(self, padding=(14, 6))
        pie.pack(fill="x", side="bottom")
        self.lbl_estado = ttk.Label(pie, text="Listo.", style="Tenue.TLabel")
        self.lbl_estado.pack(side="left")
        self.progreso = ttk.Progressbar(pie, mode="indeterminate", length=120)
        self.progreso.pack(side="right")

    def _cuaderno(self):
        self.cuaderno = ttk.Notebook(self)
        self.cuaderno.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        self.pestanas = {}
        for clave, titulo, constructor in (
            ("sesion", "Sesión", self._pestana_sesion),
            ("solicitudes", "Solicitudes de apoyo", self._pestana_solicitudes),
            ("tablero", "Tablero protegido", self._pestana_tablero),
            ("riesgo", "Riesgo", self._pestana_riesgo),
            ("reportes", "Reportes", self._pestana_reportes),
            ("diagnostico", "Diagnóstico", self._pestana_diagnostico),
        ):
            marco = ttk.Frame(self.cuaderno, padding=12)
            self.cuaderno.add(marco, text=titulo)
            self.pestanas[clave] = marco
            constructor(marco)

    # ------------------------------------------------------- utilitarios
    def _ocupado(self, texto):
        self.lbl_estado.configure(text=texto)
        self.progreso.start(12)

    def _libre(self, texto="Listo."):
        self.lbl_estado.configure(text=texto)
        self.progreso.stop()

    def _conexion(self, ok, detalle=""):
        if ok:
            self.lbl_conexion.configure(text=f"●  conectado{detalle}",
                                        foreground=COLOR_BAJO)
        else:
            self.lbl_conexion.configure(text=f"●  sin conexión{detalle}",
                                        foreground=COLOR_ALTO)

    def _error(self, e):
        """Muestra el error con su código y su detalle, no un «falló».

        Un ErrorCliente ya trae el código estable del contrato; eso es lo
        que permite buscarlo. Para cualquier otra excepción se muestra el
        rastro en Diagnóstico, porque esconderlo no la arregla.
        """
        self.progreso.stop()
        if isinstance(e, ErrorCliente):
            self.lbl_estado.configure(text=str(e))
            if e.codigo == "SIN_CONEXION":
                self._conexion(False)
            # str(e) YA incluye los detalles: agregarlos otra vez los
            # mostraba duplicados en el cuadro de dialogo.
            messagebox.showerror(e.codigo, str(e))
        else:
            self.lbl_estado.configure(text=f"Error inesperado: {e}")
            self.txt_diagnostico.configure(state="normal")
            self.txt_diagnostico.insert("1.0", traceback.format_exc() + "\n\n")
            self.txt_diagnostico.configure(state="disabled")
            messagebox.showerror("Error inesperado", str(e))

    def _llenar_tabla(self, tabla, filas, columnas, etiquetas=None):
        for i in tabla.get_children():
            tabla.delete(i)
        tabla["columns"] = columnas
        tabla["show"] = "headings"
        for c in columnas:
            tabla.heading(c, text=(etiquetas or {}).get(c, c.replace("_", " ")))
            ancho = 150 if c in ("explicacion", "nombre", "unidad",
                                 "condicion_legible", "motivo") else 110
            tabla.column(c, width=ancho, anchor="w", stretch=True)
        for fila in filas:
            valores = []
            for c in columnas:
                v = fila.get(c)
                # Un nulo se muestra como «—» y NUNCA como 0 ni como vacío.
                # En este sistema la diferencia es el punto entero: un
                # agregado suprimido no vale cero, no se puede saber.
                valores.append("—" if v is None else
                               (", ".join(map(str, v)) if isinstance(v, list)
                                else str(v)))
            etiqueta = ""
            nivel = (fila.get("nivel") or "").upper()
            if nivel == "PRIORITARIO":
                etiqueta = "alto"
            elif nivel == "ATENCION":
                etiqueta = "medio"
            elif fila.get("estado_publicacion") in (
                    "GRUPO_INSUFICIENTE", "PRESUPUESTO_PRIVACIDAD_AGOTADO"):
                etiqueta = "suprimido"
            tabla.insert("", "end", values=valores, tags=(etiqueta,))
        tabla.tag_configure("alto", foreground=COLOR_ALTO)
        tabla.tag_configure("medio", foreground=COLOR_MEDIO)
        tabla.tag_configure("suprimido", foreground=COLOR_TENUE)
        self.filas_actuales = filas
        self.columnas_actuales = columnas

    def _tabla_con_barras(self, padre):
        marco = ttk.Frame(padre)
        tabla = ttk.Treeview(marco, selectmode="browse")
        vert = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        hori = ttk.Scrollbar(marco, orient="horizontal", command=tabla.xview)
        tabla.configure(yscrollcommand=vert.set, xscrollcommand=hori.set)
        tabla.grid(row=0, column=0, sticky="nsew")
        vert.grid(row=0, column=1, sticky="ns")
        hori.grid(row=1, column=0, sticky="ew")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        return marco, tabla

    def _exportar(self, filas, columnas):
        if not filas:
            messagebox.showinfo("Exportar", "No hay filas que exportar.")
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="bienestar_export.csv")
        if not ruta:
            return
        exportar_csv(filas, columnas, ruta)
        # Se dice cuántas filas y cuántas van sin valor: un archivo con
        # treinta filas de las cuales doce están suprimidas se lee distinto
        # que uno con treinta filas completas, y quien lo reciba no lo sabrá
        # si no se le dice.
        sin_valor = sum(1 for f in filas if f.get("valor_protegido") is None
                        and "valor_protegido" in f)
        extra = (f" {sin_valor} de ellas sin valor por supresión."
                 if sin_valor else "")
        messagebox.showinfo("Exportado",
                            f"Se guardaron {len(filas)} filas en:\n{ruta}\n{extra}")

    # ========================================================== Sesión
    def _pestana_sesion(self, m):
        ttk.Label(m, text="Iniciar sesión", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Tenue.TLabel", wraplength=900, justify="left",
                  text=("El token vive en memoria mientras la ventana esté "
                        "abierta: no se escribe en disco. Guardarlo en un "
                        "archivo lo dejaría legible para cualquier programa "
                        "de la máquina, y ese token habla con los nueve "
                        "componentes del sistema.")
                  ).pack(anchor="w", pady=(2, 14))

        formulario = ttk.Frame(m)
        formulario.pack(anchor="w")
        ttk.Label(formulario, text="Correo").grid(row=0, column=0, sticky="w", pady=4)
        self.ent_correo = ttk.Entry(formulario, width=38)
        self.ent_correo.grid(row=0, column=1, padx=8, pady=4)
        self.ent_correo.insert(0, os.environ.get("ESCRITORIO_CORREO", ""))
        ttk.Label(formulario, text="Contraseña").grid(row=1, column=0, sticky="w", pady=4)
        self.ent_clave = ttk.Entry(formulario, width=38, show="•")
        self.ent_clave.grid(row=1, column=1, padx=8, pady=4)
        self.ent_clave.bind("<Return>", lambda _e: self.entrar())

        botones = ttk.Frame(m)
        botones.pack(anchor="w", pady=12)
        self.btn_entrar = ttk.Button(botones, text="Entrar", command=self.entrar)
        self.btn_entrar.pack(side="left")
        self.btn_validar = ttk.Button(botones, text="Validar token",
                                      command=self.validar)
        self.btn_validar.pack(side="left", padx=6)
        self.btn_renovar = ttk.Button(botones, text="Renovar", command=self.renovar)
        self.btn_renovar.pack(side="left", padx=6)
        self.btn_salir = ttk.Button(botones, text="Cerrar sesión", command=self.salir)
        self.btn_salir.pack(side="left", padx=6)

        self.txt_sesion = tk.Text(m, height=14, wrap="word", relief="flat",
                                  background="white", foreground=COLOR_TEXTO)
        self.txt_sesion.pack(fill="both", expand=True, pady=(8, 0))
        self.txt_sesion.configure(state="disabled")

    def _escribir_sesion(self, texto):
        self.txt_sesion.configure(state="normal")
        self.txt_sesion.delete("1.0", "end")
        self.txt_sesion.insert("1.0", texto)
        self.txt_sesion.configure(state="disabled")

    def entrar(self):
        correo = self.ent_correo.get().strip()
        clave = self.ent_clave.get()
        # Validación en el cliente: no sustituye la del servicio, evita una
        # ida y vuelta para un error que se ve desde aquí.
        if not correo or "@" not in correo:
            messagebox.showwarning("Datos incompletos",
                                   "Escribe un correo con forma de correo.")
            return
        if not clave:
            messagebox.showwarning("Datos incompletos", "Falta la contraseña.")
            return
        self._ocupado("Iniciando sesión…")
        self._entrar_async(correo, clave)

    @_hilo
    def _entrar_async(self, correo, clave):
        try:
            datos = self.cliente.iniciar_sesion(correo, clave)
        except Exception as e:  # noqa: BLE001
            # `e` se amarra como argumento por omision a proposito:
            # Python BORRA el nombre `e` al salir del except, asi que
            # un lambda que lo capturara por cierre fallaba con
            # NameError justo cuando habia que mostrar el error --
            # es decir, el manejador de errores se rompia solo en el
            # caso en que hacia falta.
            self.after(0, lambda err=e: self._error(err))
            return
        self.after(0, lambda: self._tras_entrar(datos))

    def _tras_entrar(self, datos):
        self._libre("Sesión iniciada.")
        self._conexion(True)
        self.ent_clave.delete(0, "end")
        self._aplicar_sesion(datos)
        self._escribir_sesion(
            f"Usuario:  {datos['usuario_id']}  ({datos.get('nombre') or '—'})\n"
            f"Perfil:   {datos['perfil']}\n"
            f"Alcance:  {datos.get('unidad_alcance') or 'toda la organización'}\n\n"
            f"Permisos vigentes ({len(datos['permisos'])}):\n  "
            + "\n  ".join(datos["permisos"]) +
            "\n\nLos permisos NO viajan dentro del token: se consultaron "
            "contra el servicio, que los lee de usuarios.perfil_permiso. Si "
            "viajaran en el token, quitarle un permiso a este perfil no "
            "tendría efecto hasta que el token expirara.")
        self.cuaderno.select(self.pestanas["solicitudes"])

    def _aplicar_sesion(self, datos):
        """Habilita las pestañas según los permisos. Cortesía, no seguridad."""
        hay = datos is not None
        self.lbl_sesion.configure(
            text=(f"{datos['perfil']} · {datos['usuario_id']}" if hay
                  else "sin sesión"))
        for b, activo in ((self.btn_entrar, not hay),
                          (self.btn_validar, hay),
                          (self.btn_renovar, hay),
                          (self.btn_salir, hay)):
            b.configure(state=("normal" if activo else "disabled"))

        permisos_por_pestana = {
            "solicitudes": ("APOYO_ATENDER",),
            "tablero": ("AGREGADO_UNIDAD", "AGREGADO_GLOBAL"),
            "riesgo": ("RECOMENDACION_CONSULTAR", "AGREGADO_GLOBAL",
                       "PARAMETRO_ADMIN", "BITACORA_CONSULTAR"),
            "reportes": ("AGREGADO_UNIDAD", "AGREGADO_GLOBAL",
                         "BITACORA_CONSULTAR", "PARAMETRO_ADMIN",
                         "RECOMENDACION_CONSULTAR", "INTERVENCION_APROBAR",
                         "INTERVENCION_SEGUIMIENTO"),
        }
        for clave, codigos in permisos_por_pestana.items():
            puede = hay and self.cliente.puede(*codigos)
            self.cuaderno.tab(self.pestanas[clave],
                              state=("normal" if puede else "disabled"))

    def validar(self):
        self._ocupado("Validando el token contra el servicio…")
        self._validar_async()

    @_hilo
    def _validar_async(self):
        try:
            datos = self.cliente.validar_sesion()
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._libre("Token válido según el servicio.")
            self._conexion(True)
            self._escribir_sesion(
                "\n".join(f"{k}: {v if v is not None else '—'}"
                          for k, v in datos.items()) +
                "\n\nNo basta con que el JWT no haya expirado: la sesión pudo "
                "revocarse desde el portal, y la lista de revocados vive en "
                "Redis. Esta pantalla pregunta al servicio, no mira la fecha "
                "del token.")
        self.after(0, mostrar)

    def renovar(self):
        self._ocupado("Renovando…")
        self._renovar_async()

    @_hilo
    def _renovar_async(self):
        try:
            self.cliente.renovar()
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return
        self.after(0, lambda: (
            self._libre("Token renovado. El de renovación anterior ya no sirve."),
            self._escribir_sesion(
                "Token de acceso renovado.\n\nEl token de renovación se ROTA: "
                "el anterior quedó revocado en el mismo momento. Si alguien "
                "hubiera copiado el viejo, dejó de servirle; y si el viejo se "
                "usa, el servicio sabe que hubo una copia.")))

    def salir(self):
        self._ocupado("Cerrando sesión…")
        self._salir_async()

    @_hilo
    def _salir_async(self):
        self.cliente.cerrar_sesion()   # borra credenciales aun si falla la red
        self.after(0, lambda: (
            self._libre("Sesión cerrada y credenciales borradas de memoria."),
            self._aplicar_sesion(None),
            self._escribir_sesion(
                "Sesión cerrada.\n\nLas credenciales locales se borraron "
                "incluso si el servicio no respondió: dejarlas en memoria "
                "tras un cierre de sesión sería peor que no poder avisarle "
                "al servidor."),
            self.cuaderno.select(self.pestanas["sesion"])))

    # ================================================= Solicitudes de apoyo
    def _pestana_solicitudes(self, m):
        ttk.Label(m, text="Solicitudes de apoyo", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Tenue.TLabel", wraplength=980, justify="left",
                  text=("Las solicitudes llegan por seudónimo, no por nombre: "
                        "quien atiende ve el caso y su historial, no la "
                        "identidad. Cambiar el estado es la operación de "
                        "escritura de esta aplicación y se manda en XML.")
                  ).pack(anchor="w", pady=(2, 10))

        barra = ttk.Frame(m)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Estado").pack(side="left")
        self.cmb_estado_filtro = ttk.Combobox(
            barra, values=("todos",) + ESTADOS_SOLICITUD, width=14,
            state="readonly")
        self.cmb_estado_filtro.set("todos")
        self.cmb_estado_filtro.pack(side="left", padx=6)
        ttk.Button(barra, text="Cargar",
                   command=self.cargar_solicitudes).pack(side="left", padx=6)
        ttk.Label(barra, text="Buscar").pack(side="left", padx=(16, 4))
        self.ent_buscar_sol = ttk.Entry(barra, width=26)
        self.ent_buscar_sol.pack(side="left")
        self.ent_buscar_sol.bind("<KeyRelease>", lambda _e: self._filtrar_solicitudes())
        ttk.Button(barra, text="Exportar CSV",
                   command=lambda: self._exportar(self._sol_visibles,
                                                  self._sol_columnas)
                   ).pack(side="right")

        marco, self.tbl_solicitudes = self._tabla_con_barras(m)
        marco.pack(fill="both", expand=True)
        self._sol_todas, self._sol_visibles, self._sol_columnas = [], [], []

        accion = ttk.Frame(m)
        accion.pack(fill="x", pady=(10, 0))
        ttk.Label(accion, text="Nuevo estado").pack(side="left")
        self.cmb_estado_nuevo = ttk.Combobox(accion, values=ESTADOS_SOLICITUD,
                                             width=14, state="readonly")
        self.cmb_estado_nuevo.pack(side="left", padx=6)
        ttk.Label(accion, text="Nota").pack(side="left", padx=(12, 4))
        self.ent_nota = ttk.Entry(accion, width=52)
        self.ent_nota.pack(side="left")
        ttk.Button(accion, text="Cambiar estado (XML)",
                   command=self.cambiar_estado).pack(side="left", padx=10)

    def cargar_solicitudes(self):
        estado = self.cmb_estado_filtro.get()
        self._ocupado("Pidiendo solicitudes…")
        self._cargar_solicitudes_async(None if estado == "todos" else estado)

    @_hilo
    def _cargar_solicitudes_async(self, estado):
        try:
            filas, _pag = self.cliente.solicitudes_apoyo(estado=estado)
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._libre(f"{len(filas)} solicitudes.")
            self._conexion(True)
            self._sol_todas = filas
            prefer = ["solicitud_apoyo_id", "estado", "fecha", "seudonimo_id",
                      "mensaje", "nota"]
            columnas = ([c for c in prefer if filas and c in filas[0]] or
                        (sorted(filas[0]) if filas else ["sin_datos"]))
            self._sol_columnas = columnas
            self._filtrar_solicitudes()
        self.after(0, mostrar)

    def _filtrar_solicitudes(self):
        texto = self.ent_buscar_sol.get().strip().lower()
        if texto:
            self._sol_visibles = [
                f for f in self._sol_todas
                if any(texto in str(v).lower() for v in f.values())]
        else:
            self._sol_visibles = list(self._sol_todas)
        self._llenar_tabla(self.tbl_solicitudes, self._sol_visibles,
                           self._sol_columnas)
        self.lbl_estado.configure(
            text=f"{len(self._sol_visibles)} de {len(self._sol_todas)} solicitudes.")

    def cambiar_estado(self):
        sel = self.tbl_solicitudes.selection()
        if not sel:
            messagebox.showwarning("Sin selección",
                                   "Elige la solicitud en la tabla.")
            return
        estado = self.cmb_estado_nuevo.get()
        if estado not in ESTADOS_SOLICITUD:
            messagebox.showwarning("Falta el estado",
                                   "Elige a qué estado pasa la solicitud.")
            return
        indice = self.tbl_solicitudes.index(sel[0])
        fila = self._sol_visibles[indice]
        identificador = (fila.get("solicitud_apoyo_id") or fila.get("id") or "")
        if not identificador:
            messagebox.showerror(
                "Sin identificador",
                "La fila no trae identificador de solicitud, así que no hay "
                "qué modificar. Esto significaría que el servicio cambió su "
                "contrato.")
            return
        if not messagebox.askyesno(
                "Confirmar",
                f"¿Pasar la solicitud {identificador} a {estado}?\n\n"
                "El cambio queda en el historial de la solicitud y en la "
                "bitácora, con el actor de esta sesión."):
            return
        self._ocupado("Enviando el cambio en XML…")
        self._cambiar_estado_async(identificador, estado, self.ent_nota.get().strip())

    @_hilo
    def _cambiar_estado_async(self, identificador, estado, nota):
        try:
            self.cliente.cambiar_estado_solicitud(identificador, estado, nota or None)
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return
        self.after(0, lambda: (
            self._libre(f"Solicitud {identificador} → {estado}."),
            self.ent_nota.delete(0, "end"),
            self.cargar_solicitudes()))

    # ======================================================== Tablero
    def _pestana_tablero(self, m):
        ttk.Label(m, text="Tablero protegido", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Tenue.TLabel", wraplength=980, justify="left",
                  text=("Cada valor sale de la base con ruido de Laplace y "
                        "solo si el grupo alcanza el umbral k. Las filas "
                        "suprimidas SE MUESTRAN, en gris y con «—»: "
                        "esconderlas haría creer que la unidad no tiene "
                        "problema, cuando lo que pasa es que no se puede "
                        "saber sin señalar a personas.")
                  ).pack(anchor="w", pady=(2, 10))

        barra = ttk.Frame(m)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Unidad").pack(side="left")
        self.cmb_unidad = ttk.Combobox(barra, width=42, state="readonly")
        self.cmb_unidad.pack(side="left", padx=6)
        ttk.Button(barra, text="Cargar unidades",
                   command=self.cargar_unidades).pack(side="left", padx=6)
        ttk.Button(barra, text="Ver tablero",
                   command=self.cargar_tablero).pack(side="left", padx=6)
        ttk.Button(barra, text="Exportar CSV",
                   command=lambda: self._exportar(self._tab_filas,
                                                  self._tab_columnas)
                   ).pack(side="right")

        marco, self.tbl_tablero = self._tabla_con_barras(m)
        marco.pack(fill="both", expand=True)
        self._tab_filas, self._tab_columnas = [], []
        self._unidades = []

        self.lbl_resumen_tablero = ttk.Label(m, style="Tenue.TLabel",
                                             wraplength=980, justify="left")
        self.lbl_resumen_tablero.pack(anchor="w", pady=(8, 0))

    def cargar_unidades(self):
        self._ocupado("Pidiendo el catálogo de unidades…")
        self._cargar_unidades_async()

    @_hilo
    def _cargar_unidades_async(self):
        try:
            unidades = self.cliente.unidades()
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._libre(f"{len(unidades)} unidades.")
            self._conexion(True)
            self._unidades = unidades
            self.cmb_unidad["values"] = [
                f"{u.get('unidad_organizacional_id')} — {u.get('nombre')}"
                for u in unidades]
            if unidades:
                self.cmb_unidad.current(0)
        self.after(0, mostrar)

    def cargar_tablero(self):
        seleccion = self.cmb_unidad.get()
        if not seleccion:
            messagebox.showwarning("Sin unidad",
                                   "Carga las unidades y elige una.")
            return
        unidad_id = seleccion.split(" — ")[0]
        self._ocupado(f"Pidiendo el tablero de {unidad_id}…")
        self._cargar_tablero_async(unidad_id)

    @_hilo
    def _cargar_tablero_async(self, unidad_id):
        try:
            filas = self.cliente.tablero(unidad_id)
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._conexion(True)
            self._tab_filas = filas
            prefer = ["campania_id", "secuencia", "dimension",
                      "estado_publicacion", "valor_protegido",
                      "participacion_protegida", "precision_advertencia",
                      "epsilon_aplicado", "mecanismo"]
            self._tab_columnas = ([c for c in prefer if filas and c in filas[0]]
                                  or (sorted(filas[0]) if filas else ["sin_datos"]))
            self._llenar_tabla(self.tbl_tablero, filas, self._tab_columnas)
            suprimidas = sum(1 for f in filas
                             if f.get("estado_publicacion") != "PUBLICADO")
            # El campo NO es booleano: la vista entrega
            # PRECISION_SUFICIENTE, PRECISION_LIMITADA o nada (la fila
            # suprimida, que no tiene valor sobre cuya precision advertir).
            advertidas = sum(1 for f in filas
                             if f.get("precision_advertencia") == "PRECISION_LIMITADA")
            self._libre(f"{len(filas)} filas, {suprimidas} suprimidas.")
            self.lbl_resumen_tablero.configure(text=(
                f"{len(filas)} filas · {len(filas) - suprimidas} con valor "
                f"publicado · {suprimidas} suprimidas · {advertidas} con "
                f"advertencia de precisión.\n"
                "Una advertencia de precisión significa que el ruido es "
                "grande en relación al valor: el dato se publica, pero no "
                "soporta una decisión fina. Las suprimidas no valen cero."))
        self.after(0, mostrar)

    # ========================================================== Riesgo
    def _pestana_riesgo(self, m):
        ttk.Label(m, text="Detecciones del motor de reglas",
                  style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Tenue.TLabel", wraplength=980, justify="left",
                  text=("El motor evalúa agregados YA PUBLICADOS, así que "
                        "evaluar no gasta presupuesto de privacidad: "
                        "epsilon_consumido sale en cero. Cada detección trae "
                        "su explicación; el esquema la exige, de modo que una "
                        "detección sin explicación no es un XML válido.")
                  ).pack(anchor="w", pady=(2, 10))

        barra = ttk.Frame(m)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Nivel").pack(side="left")
        self.cmb_nivel = ttk.Combobox(
            barra, width=16, state="readonly",
            values=("todos", "PRIORITARIO", "ATENCION", "INFORMATIVO"))
        self.cmb_nivel.set("todos")
        self.cmb_nivel.pack(side="left", padx=6)
        ttk.Button(barra, text="Ver detecciones",
                   command=self.cargar_detecciones).pack(side="left", padx=6)
        ttk.Button(barra, text="Ver reglas",
                   command=self.cargar_reglas).pack(side="left", padx=6)
        ttk.Button(barra, text="Exportar CSV",
                   command=lambda: self._exportar(self._rie_filas,
                                                  self._rie_columnas)
                   ).pack(side="right")

        marco, self.tbl_riesgo = self._tabla_con_barras(m)
        marco.pack(fill="both", expand=True)
        self._rie_filas, self._rie_columnas = [], []

        self.txt_explicacion = tk.Text(m, height=5, wrap="word", relief="flat",
                                       background="white")
        self.txt_explicacion.pack(fill="x", pady=(8, 0))
        self.txt_explicacion.configure(state="disabled")
        self.tbl_riesgo.bind("<<TreeviewSelect>>", self._mostrar_explicacion)

    def _mostrar_explicacion(self, _evento=None):
        sel = self.tbl_riesgo.selection()
        if not sel:
            return
        fila = self._rie_filas[self.tbl_riesgo.index(sel[0])]
        texto = (fila.get("explicacion") or fila.get("condicion_legible")
                 or "Esta fila no trae explicación.")
        if fila.get("intervencion_sugerida"):
            texto += (f"\n\nIntervención sugerida: "
                      f"{fila['intervencion_sugerida']}")
            if fila.get("descripcion"):
                texto += f"\n{fila['descripcion']}"
            texto += ("\n\nLa intervención es ORGANIZACIONAL —turno, carga, "
                      "staffing—, nunca sobre una persona: el sistema no "
                      "produce resultados individuales de los que una acción "
                      "así pudiera derivarse.")
        self.txt_explicacion.configure(state="normal")
        self.txt_explicacion.delete("1.0", "end")
        self.txt_explicacion.insert("1.0", texto)
        self.txt_explicacion.configure(state="disabled")

    def cargar_detecciones(self):
        nivel = self.cmb_nivel.get()
        self._ocupado("Pidiendo detecciones…")
        self._cargar_detecciones_async(None if nivel == "todos" else nivel)

    @_hilo
    def _cargar_detecciones_async(self, nivel):
        try:
            filas = self.cliente.detecciones(nivel=nivel)
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._libre(f"{len(filas)} detecciones.")
            self._conexion(True)
            self._rie_filas = filas
            prefer = ["unidad", "campania_id", "regla_id", "nivel",
                      "tipo_intervencion", "explicacion"]
            self._rie_columnas = ([c for c in prefer if filas and c in filas[0]]
                                  or (sorted(filas[0]) if filas else ["sin_datos"]))
            self._llenar_tabla(self.tbl_riesgo, filas, self._rie_columnas)
        self.after(0, mostrar)

    def cargar_reglas(self):
        self._ocupado("Pidiendo el catálogo de reglas…")
        self._cargar_reglas_async()

    @_hilo
    def _cargar_reglas_async(self):
        try:
            filas = self.cliente.reglas()
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._libre(f"{len(filas)} reglas.")
            self._conexion(True)
            self._rie_filas = filas
            prefer = ["regla_id", "nombre", "dimension", "umbral_valor",
                      "comparador", "campanias_consecutivas", "nivel",
                      "activa", "condicion_legible"]
            self._rie_columnas = ([c for c in prefer if filas and c in filas[0]]
                                  or (sorted(filas[0]) if filas else ["sin_datos"]))
            self._llenar_tabla(self.tbl_riesgo, filas, self._rie_columnas)
        self.after(0, mostrar)

    # ======================================================== Reportes
    def _pestana_reportes(self, m):
        ttk.Label(m, text="Reportes", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Tenue.TLabel", wraplength=980, justify="left",
                  text=("Generar un reporte lee resultados ya publicados: no "
                        "consume épsilon. Cada reporte se sella con SHA-256, "
                        "y el sello permite confrontar después un archivo que "
                        "llegó por otro medio contra el que salió del sistema.")
                  ).pack(anchor="w", pady=(2, 10))

        barra = ttk.Frame(m)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Button(barra, text="Cargar catálogo",
                   command=self.cargar_catalogo_reportes).pack(side="left")
        ttk.Label(barra, text="Tipo").pack(side="left", padx=(12, 4))
        self.cmb_tipo_reporte = ttk.Combobox(barra, width=34, state="readonly")
        self.cmb_tipo_reporte.pack(side="left")
        ttk.Label(barra, text="Parámetro").pack(side="left", padx=(12, 4))
        self.ent_parametro = ttk.Entry(barra, width=22)
        self.ent_parametro.pack(side="left")
        ttk.Button(barra, text="Generar",
                   command=self.generar_reporte).pack(side="left", padx=10)

        marco, self.tbl_reportes = self._tabla_con_barras(m)
        marco.pack(fill="both", expand=True)
        self._rep_filas, self._rep_columnas = [], []

        self.txt_reporte = tk.Text(m, height=8, wrap="word", relief="flat",
                                   background="white")
        self.txt_reporte.pack(fill="x", pady=(8, 0))
        self.txt_reporte.configure(state="disabled")

    def cargar_catalogo_reportes(self):
        self._ocupado("Pidiendo el catálogo de reportes…")
        self._cargar_catalogo_async()

    @_hilo
    def _cargar_catalogo_async(self):
        try:
            filas = self.cliente.catalogo_reportes()
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._libre(f"{len(filas)} tipos de reporte disponibles para tu perfil.")
            self._conexion(True)
            self._rep_filas = filas
            prefer = ["tipo", "titulo", "parametro", "parametro_obligatorio",
                      "formatos", "nota"]
            self._rep_columnas = ([c for c in prefer if filas and c in filas[0]]
                                  or (sorted(filas[0]) if filas else ["sin_datos"]))
            self._llenar_tabla(self.tbl_reportes, filas, self._rep_columnas)
            self.cmb_tipo_reporte["values"] = [
                f"{f.get('tipo')} — {f.get('titulo')}" for f in filas]
            if filas:
                self.cmb_tipo_reporte.current(0)
        self.after(0, mostrar)

    def generar_reporte(self):
        seleccion = self.cmb_tipo_reporte.get()
        if not seleccion:
            messagebox.showwarning("Sin tipo", "Carga el catálogo y elige un tipo.")
            return
        tipo = seleccion.split(" — ")[0]
        self._ocupado("Generando el reporte…")
        self._generar_reporte_async(tipo, self.ent_parametro.get().strip() or None)

    @_hilo
    def _generar_reporte_async(self, tipo, parametro):
        try:
            datos = self.cliente.generar_reporte(tipo, parametro)
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda err=e: self._error(err))
            return

        def mostrar():
            self._libre(f"Reporte {datos.get('reporte_id')} generado.")
            self._conexion(True)
            self.txt_reporte.configure(state="normal")
            self.txt_reporte.delete("1.0", "end")
            self.txt_reporte.insert("1.0", (
                f"Reporte:   {datos.get('reporte_id')}\n"
                f"Título:    {datos.get('titulo')}\n"
                f"Filas:     {datos.get('total_filas')} "
                f"({datos.get('filas_suprimidas')} sin valor por supresión)\n"
                f"Épsilon:   {datos.get('epsilon_consumido')}\n"
                f"Sello:     {datos.get('sello_sha256')}\n\n"
                "Las filas suprimidas van EN el archivo, con su motivo y sin "
                "valor. Un reporte que las omitiera haría creer que la "
                "campaña tuvo menos unidades de las que tuvo.\n"
                "El épsilon en cero no es un detalle: confirma que el reporte "
                "leyó resultados ya publicados y no volvió a calcular sobre "
                "los datos crudos."))
            self.txt_reporte.configure(state="disabled")
        self.after(0, mostrar)

    # ===================================================== Diagnóstico
    def _pestana_diagnostico(self, m):
        ttk.Label(m, text="Diagnóstico", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Tenue.TLabel", wraplength=980, justify="left",
                  text=("Esta pestaña existe para la demostración y para "
                        "depurar: muestra a qué servicio se habló, qué "
                        "respondió y el XML en crudo de la última respuesta. "
                        "Sin ella, «no cargó» es todo lo que se sabe.")
                  ).pack(anchor="w", pady=(2, 10))

        barra = ttk.Frame(m)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Button(barra, text="Probar los servicios",
                   command=self.probar_servicios).pack(side="left")
        ttk.Button(barra, text="Ver último XML",
                   command=self.ver_ultimo_xml).pack(side="left", padx=8)

        self.txt_diagnostico = tk.Text(m, wrap="none", relief="flat",
                                       background="white",
                                       font=("TkFixedFont", 9))
        self.txt_diagnostico.pack(fill="both", expand=True)
        self.txt_diagnostico.configure(state="disabled")
        self._escribir_diagnostico(
            "Direcciones configuradas:\n" +
            "\n".join(f"  {k:12s} {v}" for k, v in
                      sorted(self.cliente.servicios.items())) +
            "\n\nSe cambian con variables de entorno: AUTH_SERVICE_URL, "
            "CATALOG_SERVICE_URL, MAIN_PROCESS_SERVICE_URL, "
            "QUERIES_SERVICE_URL, REPORTS_SERVICE_URL, "
            "ALGORITHMS_SERVICE_URL.\n")

    def _escribir_diagnostico(self, texto):
        self.txt_diagnostico.configure(state="normal")
        self.txt_diagnostico.delete("1.0", "end")
        self.txt_diagnostico.insert("1.0", texto)
        self.txt_diagnostico.configure(state="disabled")

    def probar_servicios(self):
        self._ocupado("Sondeando los servicios…")
        self._probar_servicios_async()

    @_hilo
    def _probar_servicios_async(self):
        import json
        import time
        import urllib.error
        import urllib.request
        lineas = []
        alcanzables = 0
        for nombre, base in sorted(self.cliente.servicios.items()):
            inicio = time.perf_counter()
            try:
                peticion = urllib.request.Request(base.rstrip("/") + "/health/ready")
                with urllib.request.urlopen(peticion, timeout=4) as r:
                    cuerpo, codigo = r.read(), r.status
            except urllib.error.HTTPError as e:
                cuerpo, codigo = e.read(), e.code
            except Exception as e:  # noqa: BLE001
                lineas.append(f"  {nombre:12s} SIN RESPUESTA   {base}\n"
                              f"               {e}")
                continue
            ms = (time.perf_counter() - inicio) * 1000
            alcanzables += 1
            try:
                salud = json.loads(cuerpo)
                estado = salud.get("estado", "?")
                falta = (salud.get("degradado_por") or salud.get("falta") or [])
                detalle = f" (sin: {', '.join(falta)})" if falta else ""
            except Exception:  # noqa: BLE001
                estado, detalle = f"http {codigo}", ""
            lineas.append(f"  {nombre:12s} {estado:10s} {ms:6.0f} ms{detalle}")
        texto = ("Sondas /health/ready:\n" + "\n".join(lineas) +
                 "\n\n«degradado» con código 200 es deliberado: el servicio "
                 "SÍ puede atender y está informando qué dependencia "
                 "opcional no responde. Devolver 503 ahí sacaría de rotación "
                 "a una pieza sana; devolver 200 sin decir nada esconderia "
                 "la falla.")

        def mostrar():
            self._libre(f"{alcanzables} de {len(self.cliente.servicios)} "
                        f"servicios respondieron.")
            self._conexion(alcanzables > 0,
                           f" · {alcanzables}/{len(self.cliente.servicios)}")
            self._escribir_diagnostico(texto)
        self.after(0, mostrar)

    def ver_ultimo_xml(self):
        crudo = getattr(self.cliente, "ultimo_xml", "")
        self._escribir_diagnostico(
            crudo or "Todavía no hay respuesta que mostrar. Haz una consulta "
                     "en cualquier pestaña y vuelve aquí.")

    # --------------------------------------------------------------- cierre
    def _al_cerrar(self):
        """Cerrar la ventana cierra la sesión en el servidor.

        Una ventana cerrada sin avisar deja el token vivo hasta que expire.
        Son quince minutos en los que un token válido ya no tiene dueño.
        """
        try:
            if self.cliente.token:
                self.cliente.cerrar_sesion()
        finally:
            self.destroy()


def main():
    Aplicacion().mainloop()


if __name__ == "__main__":
    main()
