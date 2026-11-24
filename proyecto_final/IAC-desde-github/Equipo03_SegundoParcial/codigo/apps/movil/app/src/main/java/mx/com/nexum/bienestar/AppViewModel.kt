package mx.com.nexum.bienestar

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.com.nexum.bienestar.datos.ApoyoRepositorio
import mx.com.nexum.bienestar.datos.Aviso
import mx.com.nexum.bienestar.datos.AvisosRepositorio
import mx.com.nexum.bienestar.datos.Campania
import mx.com.nexum.bienestar.datos.CatalogoRepositorio
import mx.com.nexum.bienestar.datos.EncuestaRepositorio
import mx.com.nexum.bienestar.datos.EvidenciaRepositorio
import mx.com.nexum.bienestar.datos.Reactivo
import mx.com.nexum.bienestar.red.ClienteApi
import mx.com.nexum.bienestar.red.ErrorApi
import mx.com.nexum.bienestar.sesion.AlmacenSeguro
import mx.com.nexum.bienestar.sesion.SesionRepositorio
import org.json.JSONObject
import java.io.File

enum class Pantalla { LOGIN, MENU, ENCUESTA, PARTICIPACION, APOYO, AVISOS }

enum class Conexion { SIN_PROBAR, CONECTADO, DEGRADADO, SIN_CONEXION }

data class EstadoApp(
    val pantalla: Pantalla = Pantalla.LOGIN,
    val cargando: Boolean = false,
    val conexion: Conexion = Conexion.SIN_PROBAR,
    val detalleConexion: String = "",
    val nombre: String = "",
    val perfil: String = "",
    val permisos: Set<String> = emptySet(),
    val error: String? = null,
    val errorCodigo: String? = null,
    val aviso: String? = null,
    val campania: Campania? = null,
    val reactivos: List<Reactivo> = emptyList(),
    val respuestas: Map<String, Int> = emptyMap(),
    val indiceReactivo: Int = 0,
    val participacion: String = "",
    val avisos: List<Aviso> = emptyList(),
    val fotoTomada: Boolean = false,
    val metadatosQuitados: Int = 0,
)

/**
 * Estado de la aplicación y órdenes contra los microservicios.
 *
 * TODO error llega aquí convertido en [ErrorApi] con su código estable, y
 * aquí se decide qué hacer con él en un solo lugar:
 *
 *   · el que exige sesión nueva  -> se intenta renovar una vez y, si no, se
 *                                   manda al login en lugar de dejar la
 *                                   pantalla fallando sin explicación;
 *   · el que vale la pena reintentar -> se le ofrece reintentar al usuario;
 *   · los demás -> se muestran con su código, que es lo que permite
 *                  buscarlos.
 *
 * Tener esa decisión en un solo sitio es lo que evita que cada pantalla
 * invente su propio manejo y que una de ellas se olvide del caso de la
 * sesión revocada.
 */
class AppViewModel(aplicacion: Application) : AndroidViewModel(aplicacion) {

    private val almacen = AlmacenSeguro(aplicacion)
    private val api = ClienteApi({ almacen.tokenAcceso })
    private val sesion = SesionRepositorio(almacen, api)
    private val catalogo = CatalogoRepositorio(api)
    private val encuestas = EncuestaRepositorio(api)
    private val apoyo = ApoyoRepositorio(api)
    private val avisos = AvisosRepositorio(api)
    val evidencias = EvidenciaRepositorio(aplicacion, api)

    private val _estado = MutableStateFlow(EstadoApp())
    val estado: StateFlow<EstadoApp> = _estado.asStateFlow()

    private var archivoEvidencia: File? = null

    init {
        // Si hay sesión guardada, se CONFIRMA con el servicio antes de
        // dejar entrar. Confiar en el token guardado dejaría pasar a alguien
        // cuya sesión ya se revocó desde el portal.
        if (almacen.haySesion()) {
            viewModelScope.launch {
                _estado.update { it.copy(cargando = true) }
                val vale = try { sesion.validar() } catch (e: ErrorApi) { false }
                if (vale) {
                    _estado.update {
                        it.copy(
                            pantalla = Pantalla.MENU,
                            cargando = false,
                            conexion = Conexion.CONECTADO,
                            nombre = almacen.nombre.orEmpty(),
                            perfil = almacen.perfil.orEmpty(),
                            permisos = almacen.permisos,
                        )
                    }
                } else {
                    almacen.borrarCredenciales()
                    _estado.update {
                        it.copy(pantalla = Pantalla.LOGIN, cargando = false,
                                aviso = "Tu sesión anterior ya no es válida. " +
                                        "Vuelve a entrar.")
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------- errores
    private fun manejar(e: Throwable) {
        val error = e as? ErrorApi
        if (error?.exigeNuevaSesion == true) {
            viewModelScope.launch {
                if (sesion.renovar()) {
                    _estado.update {
                        it.copy(cargando = false,
                                aviso = "Se renovó la sesión. Vuelve a intentar.")
                    }
                } else {
                    almacen.borrarCredenciales()
                    _estado.update {
                        EstadoApp(pantalla = Pantalla.LOGIN,
                                  aviso = "Tu sesión terminó. Entra de nuevo.")
                    }
                }
            }
            return
        }
        _estado.update {
            it.copy(
                cargando = false,
                error = error?.descripcionCompleta() ?: (e.message ?: "Error inesperado."),
                errorCodigo = error?.codigo,
                conexion = when {
                    error == null -> it.conexion
                    error.http == 0 -> Conexion.SIN_CONEXION
                    error.codigo == "ALMACEN_NO_DISPONIBLE" -> Conexion.DEGRADADO
                    else -> Conexion.CONECTADO
                },
                detalleConexion = when {
                    error?.codigo == "ALMACEN_NO_DISPONIBLE" ->
                        "el almacén de documentos no responde"
                    else -> it.detalleConexion
                },
            )
        }
    }

    fun limpiarMensajes() =
        _estado.update { it.copy(error = null, errorCodigo = null, aviso = null) }

    private fun lanzar(bloque: suspend () -> Unit) {
        viewModelScope.launch {
            _estado.update { it.copy(cargando = true, error = null, errorCodigo = null) }
            try {
                bloque()
            } catch (e: Throwable) {
                manejar(e)
            }
        }
    }

    // -------------------------------------------------------------- sesión
    /** Validación en el cliente: ahorra una ida y vuelta, no sustituye nada. */
    fun validarCredenciales(correo: String, contrasena: String): String? = when {
        correo.isBlank() -> "Escribe tu correo."
        !correo.contains("@") || !correo.contains(".") ->
            "Ese correo no tiene forma de correo."
        contrasena.isBlank() -> "Escribe tu contraseña."
        contrasena.length < 6 -> "La contraseña tiene al menos 6 caracteres."
        else -> null
    }

    fun entrar(correo: String, contrasena: String) = lanzar {
        val usuario = sesion.iniciarSesion(correo, contrasena)
        _estado.update {
            it.copy(
                pantalla = Pantalla.MENU, cargando = false,
                conexion = Conexion.CONECTADO, detalleConexion = "",
                nombre = usuario.nombre, perfil = usuario.perfil,
                permisos = almacen.permisos,
            )
        }
    }

    fun salir() = lanzar {
        sesion.cerrarSesion()
        // El estado se reconstruye desde cero: así no queda en memoria una
        // lista de avisos o un borrador de la persona anterior.
        _estado.value = EstadoApp(
            pantalla = Pantalla.LOGIN,
            aviso = "Sesión cerrada. Se borraron el token y los datos locales.",
        )
    }

    fun ir(pantalla: Pantalla) =
        _estado.update { it.copy(pantalla = pantalla, error = null, aviso = null) }

    fun puede(vararg codigos: String) = _estado.value.permisos.any { it in codigos }

    // ------------------------------------------------------------ encuesta
    fun abrirEncuesta() = lanzar {
        val campania = catalogo.campaniaAbierta()
        if (campania == null) {
            _estado.update {
                it.copy(cargando = false, pantalla = Pantalla.MENU,
                        aviso = "No hay ninguna campaña abierta en este momento.")
            }
            return@lanzar
        }
        val reactivos = catalogo.reactivosDe(campania)
        val guardadas = leerBorrador(campania.campaniaId)
        _estado.update {
            it.copy(
                pantalla = Pantalla.ENCUESTA, cargando = false,
                conexion = Conexion.CONECTADO,
                campania = campania, reactivos = reactivos,
                respuestas = guardadas,
                indiceReactivo = guardadas.size.coerceAtMost(
                    (reactivos.size - 1).coerceAtLeast(0)),
                aviso = if (guardadas.isNotEmpty())
                    "Se recuperó tu borrador: llevabas ${guardadas.size} de " +
                        "${reactivos.size} respuestas." else null,
            )
        }
    }

    fun responder(reactivoId: String, valor: Int) {
        _estado.update { actual ->
            val nuevas = actual.respuestas + (reactivoId to valor)
            guardarBorrador(actual.campania?.campaniaId, nuevas)
            actual.copy(
                respuestas = nuevas,
                indiceReactivo = (actual.indiceReactivo + 1)
                    .coerceAtMost(actual.reactivos.size),
            )
        }
    }

    fun retroceder() = _estado.update {
        it.copy(indiceReactivo = (it.indiceReactivo - 1).coerceAtLeast(0))
    }

    fun enviarEncuesta() = lanzar {
        val actual = _estado.value
        val campania = actual.campania ?: return@lanzar
        val faltan = actual.reactivos.count { it.reactivoId !in actual.respuestas }
        if (faltan > 0) {
            _estado.update {
                it.copy(cargando = false,
                        error = "Faltan $faltan preguntas por responder. " +
                                "Una encuesta incompleta distorsionaría el " +
                                "agregado de tu unidad.",
                        errorCodigo = "ENCUESTA_INCOMPLETA")
            }
            return@lanzar
        }
        encuestas.enviarRespuestas(campania.campaniaId, actual.respuestas)
        // El borrador se borra SOLO después de que el servicio confirmó.
        // Borrarlo antes y perder la conexión dejaría al usuario sin lo que
        // escribió y sin haberlo enviado.
        almacen.limpiarBorrador()
        _estado.update {
            it.copy(
                pantalla = Pantalla.MENU, cargando = false,
                respuestas = emptyMap(), indiceReactivo = 0,
                aviso = "Gracias. Tus respuestas se registraron bajo seudónimo: " +
                    "ni quien administra el sistema puede ver qué contestaste.",
            )
        }
    }

    private fun guardarBorrador(campaniaId: String?, respuestas: Map<String, Int>) {
        if (campaniaId == null) return
        val json = JSONObject().put("campania_id", campaniaId)
        val datos = JSONObject()
        respuestas.forEach { (k, v) -> datos.put(k, v) }
        json.put("respuestas", datos)
        almacen.borradorEncuesta = json.toString()
    }

    private fun leerBorrador(campaniaId: String): Map<String, Int> {
        val crudo = almacen.borradorEncuesta ?: return emptyMap()
        return try {
            val json = JSONObject(crudo)
            // El borrador de OTRA campaña no se reutiliza: las preguntas
            // pudieron cambiar entre versiones del instrumento, y mezclarlas
            // produciría respuestas asociadas a reactivos que ya no existen.
            if (json.optString("campania_id") != campaniaId) return emptyMap()
            val datos = json.getJSONObject("respuestas")
            datos.keys().asSequence().associateWith { datos.getInt(it) }
        } catch (e: Exception) {
            emptyMap()
        }
    }

    // -------------------------------------------------------- participación
    fun verParticipacion() = lanzar {
        val datos = encuestas.participacionPropia()
        val total = datos.optInt("total", datos.optJSONArray("respuestas")?.length() ?: 0)
        _estado.update {
            it.copy(
                pantalla = Pantalla.PARTICIPACION, cargando = false,
                conexion = Conexion.CONECTADO,
                participacion = "Has participado en $total campañas.\n\n" +
                    "Lo que ves es QUE participaste y cuándo, no qué " +
                    "contestaste. No es que la pantalla lo esconda: el " +
                    "servidor no puede recuperarlo. Tus respuestas se " +
                    "guardan bajo seudónimo, y esa relación no se puede " +
                    "recorrer de vuelta.",
            )
        }
    }

    // --------------------------------------------------------------- apoyo
    fun validarMensajeApoyo(mensaje: String): String? = when {
        mensaje.isBlank() -> "Escribe de qué se trata."
        mensaje.trim().length < 8 ->
            "Escribe un poco más: con menos de 8 caracteres, quien lo atienda " +
                "no tiene con qué empezar."
        mensaje.length > 2000 -> "El mensaje es demasiado largo (máximo 2000)."
        else -> null
    }

    fun pedirApoyo(mensaje: String, conFoto: Boolean) = lanzar {
        val respuesta = apoyo.pedirApoyo(mensaje)
        val solicitudId = respuesta.optJSONObject("solicitud")?.optString("id")
            ?: respuesta.optString("id", "")

        var nota = "Tu solicitud quedó registrada. Quien la atienda verá el " +
            "caso bajo tu seudónimo, no tu nombre."
        val archivo = archivoEvidencia
        if (conFoto && archivo != null && archivo.exists() && solicitudId.isNotBlank()) {
            try {
                evidencias.subir(archivo, solicitudId, "Evidencia de la solicitud")
                nota += "\n\nSe adjuntó la foto, sin sus datos de ubicación."
            } catch (e: ErrorApi) {
                // La solicitud YA se creó. Perderla por un fallo al subir la
                // foto sería lo peor posible, así que se informa y se sigue.
                nota += "\n\nLa solicitud se registró, pero la foto no se " +
                    "pudo subir (${e.codigo}). Puedes adjuntarla después."
            }
            archivoEvidencia = null
        }
        _estado.update {
            it.copy(pantalla = Pantalla.MENU, cargando = false,
                    conexion = Conexion.CONECTADO,
                    fotoTomada = false, metadatosQuitados = 0, aviso = nota)
        }
    }

    // ------------------------------------------------------------- cámara
    fun prepararFoto(): android.net.Uri {
        val (archivo, uri) = evidencias.prepararArchivo()
        archivoEvidencia = archivo
        return uri
    }

    fun fotoTomada(exito: Boolean) {
        if (!exito) {
            evidencias.descartar(archivoEvidencia)
            archivoEvidencia = null
            _estado.update { it.copy(fotoTomada = false, metadatosQuitados = 0) }
            return
        }
        viewModelScope.launch {
            val quitados = archivoEvidencia?.let { evidencias.limpiarMetadatos(it) } ?: 0
            _estado.update { it.copy(fotoTomada = true, metadatosQuitados = quitados) }
        }
    }

    fun descartarFoto() {
        evidencias.descartar(archivoEvidencia)
        archivoEvidencia = null
        _estado.update { it.copy(fotoTomada = false, metadatosQuitados = 0) }
    }

    // -------------------------------------------------------------- avisos
    fun verAvisos() = lanzar {
        val lista = avisos.mios()
        _estado.update {
            it.copy(pantalla = Pantalla.AVISOS, cargando = false,
                    conexion = Conexion.CONECTADO, avisos = lista)
        }
    }
}
