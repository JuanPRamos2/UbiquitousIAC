package mx.com.nexum.bienestar.sesion

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import mx.com.nexum.bienestar.BuildConfig
import mx.com.nexum.bienestar.red.ClienteApi
import mx.com.nexum.bienestar.red.ErrorApi
import org.json.JSONArray
import org.json.JSONObject

data class Usuario(
    val usuarioId: String,
    val nombre: String,
    val correo: String,
    val perfil: String,
    val perfilId: Int,
    val unidadAlcance: String?,
)

/**
 * Sesión contra auth-service: entrar, validar, renovar y salir.
 *
 * EL TOKEN DE RENOVACIÓN SE ROTA
 * ------------------------------
 * Cada renovación devuelve un token de renovación nuevo y revoca el
 * anterior. Hay que guardar el nuevo: si se guardara el viejo, la siguiente
 * renovación fallaría y el usuario vería cerrarse la sesión sin motivo
 * aparente. La rotación además deja una señal útil del lado del servidor:
 * si alguien usa un token de renovación ya rotado, es que hubo una copia.
 *
 * LOS PERMISOS NO VIAJAN EN EL TOKEN
 * ----------------------------------
 * Se consultan aparte, contra /auth/permisos, que los lee de
 * usuarios.perfil_permiso. Si viajaran dentro del JWT, quitarle un permiso
 * a un perfil no tendría efecto hasta que el token expirara, y un token de
 * quince minutos significa quince minutos de permiso ya revocado.
 */
class SesionRepositorio(
    private val almacen: AlmacenSeguro,
    private val api: ClienteApi = ClienteApi({ almacen.tokenAcceso }),
    private val urlAuth: String = BuildConfig.URL_AUTH,
) {
    // Si dos pantallas reciben 401 al mismo tiempo, sin este candado las dos
    // renovarían. La segunda llegaría con el token de renovación que la
    // primera acaba de rotar, el servicio lo rechazaría con razón, y la
    // sesión se cerraría sola.
    private val candadoRenovacion = Mutex()

    suspend fun iniciarSesion(correo: String, contrasena: String): Usuario {
        val cuerpo = JSONObject()
            .put("correo", correo.trim())
            .put("contrasena", contrasena)
        val respuesta = api.publicar("$urlAuth/api/v1/auth/login", cuerpo)

        almacen.tokenAcceso = respuesta.getString("token_acceso")
        almacen.tokenRenovacion = respuesta.optString("token_renovacion", null)

        val u = respuesta.getJSONObject("usuario")
        val usuario = Usuario(
            usuarioId = u.getString("usuario_id"),
            nombre = u.optString("nombre", ""),
            correo = u.optString("correo", ""),
            perfil = u.optString("perfil", ""),
            perfilId = u.optInt("perfil_id", 0),
            unidadAlcance = if (u.isNull("unidad_alcance")) null
                            else u.optString("unidad_alcance"),
        )
        almacen.usuarioId = usuario.usuarioId
        almacen.nombre = usuario.nombre
        almacen.perfil = usuario.perfil
        almacen.permisos = consultarPermisos()
        return usuario
    }

    suspend fun consultarPermisos(): Set<String> {
        val respuesta = api.obtener("$urlAuth/api/v1/auth/permisos")
        val arreglo: JSONArray = respuesta.optJSONArray("permisos") ?: JSONArray()
        val codigos = (0 until arreglo.length()).map { arreglo.getString(it) }.toSet()
        almacen.permisos = codigos
        return codigos
    }

    /**
     * Confirma con el servicio que la sesión sigue viva.
     *
     * No basta con que el JWT no haya expirado: la sesión pudo revocarse
     * desde el portal web, y la lista de revocados vive en Redis, compartida
     * por los nueve componentes. Una aplicación que solo mirara la fecha del
     * token seguiría trabajando con una sesión cerrada.
     */
    suspend fun validar(): Boolean = try {
        api.obtener("$urlAuth/api/v1/auth/validar").optBoolean("valido", false)
    } catch (e: ErrorApi) {
        if (e.exigeNuevaSesion) false else throw e
    }

    /** Renueva el token de acceso. Devuelve false si ya no se puede. */
    suspend fun renovar(): Boolean = candadoRenovacion.withLock {
        val renovacion = almacen.tokenRenovacion ?: return@withLock false
        return@withLock try {
            val respuesta = api.publicar(
                "$urlAuth/api/v1/auth/renovar",
                JSONObject().put("token_renovacion", renovacion),
            )
            almacen.tokenAcceso = respuesta.getString("token_acceso")
            // El de renovación SE ROTA: guardar el nuevo no es opcional.
            respuesta.optString("token_renovacion", null)
                ?.takeIf { it.isNotBlank() }
                ?.let { almacen.tokenRenovacion = it }
            true
        } catch (e: ErrorApi) {
            false
        }
    }

    /**
     * Cierra sesión en el servidor y borra TODO lo local.
     *
     * Las credenciales se borran aunque el servicio no conteste. Dejarlas en
     * el teléfono tras un cierre de sesión sería peor que no poder avisarle
     * al servidor: el usuario cree que salió, y el token sigue ahí.
     */
    suspend fun cerrarSesion() {
        try {
            if (almacen.haySesion()) {
                api.publicar("$urlAuth/api/v1/auth/logout", JSONObject())
            }
        } catch (_: Exception) {
            // Se ignora a propósito: ver arriba.
        } finally {
            almacen.borrarTodo()
        }
    }

    fun puede(vararg codigos: String): Boolean =
        almacen.permisos.any { it in codigos }
}
