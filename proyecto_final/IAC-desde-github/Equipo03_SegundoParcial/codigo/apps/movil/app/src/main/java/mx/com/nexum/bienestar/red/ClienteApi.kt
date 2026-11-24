package mx.com.nexum.bienestar.red

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.SocketTimeoutException
import java.util.UUID
import java.util.concurrent.TimeUnit

/**
 * Cliente HTTP de la aplicación móvil. Habla EXCLUSIVAMENTE JSON.
 *
 * Es el reverso de la aplicación de escritorio, que habla solo XML contra
 * los mismos servicios. Que las dos funcionen contra el mismo backend es la
 * prueba de que la negociación de formato existe de verdad y no es una
 * bandera que nadie ejercita.
 *
 * TRES DECISIONES QUE VALE LA PENA EXPLICAR
 * -----------------------------------------
 * 1. El error del servicio se convierte en [ErrorApi] con su CÓDIGO, no en
 *    una cadena. El código es estable; el mensaje puede cambiar de
 *    redacción. La interfaz decide qué hacer mirando el código —reintentar,
 *    pedir sesión de nuevo, avisar— y muestra el mensaje tal cual.
 *
 * 2. Cada petición lleva un X-Correlacion-Id. Una solicitud de apoyo pasa
 *    por tres servicios; sin ese identificador, seguir una operación en las
 *    bitácoras significa adivinar por marca de tiempo.
 *
 * 3. El token NO se guarda aquí. Lo entrega un proveedor en cada petición,
 *    de modo que al renovarlo no haya que reconstruir el cliente ni quede
 *    una copia vieja viva en algún lado.
 */
class ClienteApi(
    private val proveedorToken: () -> String?,
    tiempoLimiteSegundos: Long = 15,
) {
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(tiempoLimiteSegundos, TimeUnit.SECONDS)
        .readTimeout(tiempoLimiteSegundos, TimeUnit.SECONDS)
        .addInterceptor(EncabezadosComunes(proveedorToken))
        .build()

    private class EncabezadosComunes(
        private val proveedorToken: () -> String?,
    ) : Interceptor {
        override fun intercept(cadena: Interceptor.Chain): okhttp3.Response {
            val constructor = cadena.request().newBuilder()
                .header("Accept", "application/json")
                .header("X-Correlacion-Id", UUID.randomUUID().toString().take(16))
            proveedorToken()?.let { constructor.header("Authorization", "Bearer $it") }
            return cadena.proceed(constructor.build())
        }
    }

    suspend fun obtener(url: String): JSONObject = ejecutar(
        Request.Builder().url(url).get().build()
    )

    suspend fun publicar(url: String, cuerpo: JSONObject): JSONObject = ejecutar(
        Request.Builder().url(url)
            .post(cuerpo.toString().toRequestBody(JSON)).build()
    )

    suspend fun parchar(url: String, cuerpo: JSONObject): JSONObject = ejecutar(
        Request.Builder().url(url)
            .patch(cuerpo.toString().toRequestBody(JSON)).build()
    )

    private suspend fun ejecutar(peticion: Request): JSONObject =
        withContext(Dispatchers.IO) {
            val respuesta = try {
                http.newCall(peticion).execute()
            } catch (e: SocketTimeoutException) {
                throw ErrorApi(
                    "TIEMPO_AGOTADO",
                    "El servicio no respondió a tiempo. Puede ser tu conexión " +
                        "o el servicio; vuelve a intentar en unos momentos.",
                    http = 0,
                )
            } catch (e: IOException) {
                throw ErrorApi(
                    "SIN_CONEXION",
                    "No se pudo contactar al servicio. Revisa tu conexión a " +
                        "internet.",
                    http = 0,
                )
            }

            respuesta.use {
                val texto = it.body?.string().orEmpty()
                val codigoHttp = it.code

                if (texto.isBlank()) {
                    if (codigoHttp in 200..299) return@withContext JSONObject()
                    throw ErrorApi(
                        "RESPUESTA_VACIA",
                        "El servicio respondió $codigoHttp sin contenido.",
                        codigoHttp,
                    )
                }

                val json = try {
                    JSONObject(texto)
                } catch (e: Exception) {
                    // Pasa cuando algo intermedio —un portal cautivo de red
                    // wifi, un proxy— devuelve HTML. Decirlo así evita que
                    // el usuario busque el problema en la aplicación.
                    throw ErrorApi(
                        "RESPUESTA_NO_JSON",
                        "La respuesta no es JSON. Suele significar que algo " +
                            "en la red está interceptando la conexión.",
                        codigoHttp,
                    )
                }

                if (json.has("error")) {
                    val error = json.getJSONObject("error")
                    throw ErrorApi(
                        codigo = error.optString("codigo", "ERROR"),
                        mensaje = error.optString("mensaje", "Error del servicio."),
                        http = codigoHttp,
                        detalles = error.optJSONArray("detalles").aListaDeDetalles(),
                        correlacionId = error.optString("correlacion_id", ""),
                    )
                }
                if (codigoHttp !in 200..299) {
                    throw ErrorApi(
                        "RESPUESTA_INESPERADA",
                        "El servicio respondió $codigoHttp con un documento " +
                            "que no es un sobre de error.",
                        codigoHttp,
                    )
                }
                json
            }
        }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}

/** Error del servicio, con el código estable del contrato. */
class ErrorApi(
    val codigo: String,
    override val message: String,
    val http: Int,
    val detalles: List<Pair<String, String>> = emptyList(),
    val correlacionId: String = "",
) : Exception(message) {

    val mensaje: String get() = message

    /**
     * Si conviene que la aplicación reintente sola.
     *
     * 503 ALMACEN_NO_DISPONIBLE es el caso que importa: el servicio está
     * arriba y su dependencia no. Ahí reintentar tiene sentido. Ante un
     * 403 SIN_PERMISO, reintentar nunca va a funcionar y solo gasta batería
     * y cuota.
     */
    val valeReintentar: Boolean
        get() = http == 0 || http == 503 || http == 429 ||
            codigo == "ALMACEN_NO_DISPONIBLE"

    /** Si hay que mandar al usuario a iniciar sesión otra vez. */
    val exigeNuevaSesion: Boolean
        get() = codigo in setOf(
            "SESION_REVOCADA", "TOKEN_INVALIDO", "TOKEN_EXPIRADO",
            "SIN_TOKEN", "NO_AUTENTICADO",
        )

    fun descripcionCompleta(): String = buildString {
        append(mensaje)
        detalles.forEach { (campo, problema) -> append("\n· $campo: $problema") }
    }
}

private fun JSONArray?.aListaDeDetalles(): List<Pair<String, String>> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { i ->
        val d = optJSONObject(i) ?: return@mapNotNull null
        d.optString("campo") to d.optString("problema")
    }
}

/** Recorre un arreglo de objetos sin escribir el bucle cada vez. */
fun JSONArray?.objetos(): List<JSONObject> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { optJSONObject(it) }
}
