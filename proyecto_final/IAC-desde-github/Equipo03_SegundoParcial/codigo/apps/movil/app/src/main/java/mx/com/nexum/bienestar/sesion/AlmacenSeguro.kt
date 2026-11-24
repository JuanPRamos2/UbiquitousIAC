package mx.com.nexum.bienestar.sesion

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Almacenamiento local cifrado. Es una de las dos capacidades del
 * dispositivo que usa esta aplicación (la otra es la cámara).
 *
 * POR QUÉ CIFRADO Y NO SharedPreferences A SECAS
 * -----------------------------------------------
 * Aquí viven dos cosas: el token de sesión y el borrador de la encuesta.
 *
 * El token habla con los nueve componentes del sistema. Las preferencias
 * normales se guardan en un XML en claro dentro del almacenamiento de la
 * aplicación: en un teléfono con acceso de superusuario, o con una copia de
 * seguridad mal configurada, ese archivo se lee tal cual.
 *
 * El borrador pesa todavía más. Son las respuestas de una encuesta de clima
 * laboral ANTES de enviarse, y van asociadas a la cuenta de quien las
 * escribió. Todo el sistema está construido para que esas respuestas solo
 * existan bajo seudónimo y nunca se puedan atribuir a una persona; dejarlas
 * en claro en el teléfono abriría por la puerta de atrás exactamente lo que
 * el servidor cierra por la de enfrente.
 *
 * La clave maestra vive en el almacén de claves de Android y, en los
 * equipos que lo tienen, respaldada por hardware: no se puede extraer
 * copiando archivos.
 *
 * SOBRE EL RESPALDO DEL FABRICANTE: no basta con cifrar. El manifiesto
 * declara allowBackup="false" y reglas de extracción vacías, porque un
 * respaldo automático sacaría estos datos del teléfono.
 */
class AlmacenSeguro(contexto: Context) {

    private val preferencias: SharedPreferences = run {
        val clave = MasterKey.Builder(contexto)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            contexto,
            "bienestar_sesion",
            clave,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var tokenAcceso: String?
        get() = preferencias.getString(CLAVE_ACCESO, null)
        set(valor) = preferencias.edit().putString(CLAVE_ACCESO, valor).apply()

    var tokenRenovacion: String?
        get() = preferencias.getString(CLAVE_RENOVACION, null)
        set(valor) = preferencias.edit().putString(CLAVE_RENOVACION, valor).apply()

    var usuarioId: String?
        get() = preferencias.getString(CLAVE_USUARIO, null)
        set(valor) = preferencias.edit().putString(CLAVE_USUARIO, valor).apply()

    var perfil: String?
        get() = preferencias.getString(CLAVE_PERFIL, null)
        set(valor) = preferencias.edit().putString(CLAVE_PERFIL, valor).apply()

    var nombre: String?
        get() = preferencias.getString(CLAVE_NOMBRE, null)
        set(valor) = preferencias.edit().putString(CLAVE_NOMBRE, valor).apply()

    /**
     * Permisos del perfil, consultados al servicio.
     *
     * Se guardan SOLO para decidir qué muestra el menú mientras no hay red.
     * La autorización de verdad la hace cada servicio consultando
     * usuarios.perfil_permiso en cada petición: una aplicación que
     * escondiera botones no estaría protegiendo nada, y estos permisos
     * guardados pueden estar viejos.
     */
    var permisos: Set<String>
        get() = preferencias.getStringSet(CLAVE_PERMISOS, emptySet()) ?: emptySet()
        set(valor) = preferencias.edit().putStringSet(CLAVE_PERMISOS, valor).apply()

    /** Borrador de la encuesta en curso, como JSON. */
    var borradorEncuesta: String?
        get() = preferencias.getString(CLAVE_BORRADOR, null)
        set(valor) = preferencias.edit().putString(CLAVE_BORRADOR, valor).apply()

    fun haySesion(): Boolean = !tokenAcceso.isNullOrBlank()

    /**
     * Borra las credenciales. El borrador NO se toca aquí.
     *
     * Son dos cosas distintas y conviene que se borren por separado: a
     * quien se le cerró la sesión por inactividad mientras contestaba la
     * encuesta no hay por qué tirarle lo que ya había escrito. El borrador
     * se borra cuando la encuesta se envía (ver [limpiarBorrador]) o cuando
     * el usuario cierra sesión a propósito (ver [borrarTodo]).
     */
    fun borrarCredenciales() {
        preferencias.edit()
            .remove(CLAVE_ACCESO)
            .remove(CLAVE_RENOVACION)
            .remove(CLAVE_USUARIO)
            .remove(CLAVE_PERFIL)
            .remove(CLAVE_NOMBRE)
            .remove(CLAVE_PERMISOS)
            .apply()
    }

    fun limpiarBorrador() {
        preferencias.edit().remove(CLAVE_BORRADOR).apply()
    }

    /** Cierre de sesión a propósito: no queda nada de esta persona. */
    fun borrarTodo() {
        preferencias.edit().clear().apply()
    }

    private companion object {
        const val CLAVE_ACCESO = "token_acceso"
        const val CLAVE_RENOVACION = "token_renovacion"
        const val CLAVE_USUARIO = "usuario_id"
        const val CLAVE_PERFIL = "perfil"
        const val CLAVE_NOMBRE = "nombre"
        const val CLAVE_PERMISOS = "permisos"
        const val CLAVE_BORRADOR = "borrador_encuesta"
    }
}
