package mx.com.nexum.bienestar.datos

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import androidx.exifinterface.media.ExifInterface
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import mx.com.nexum.bienestar.BuildConfig
import mx.com.nexum.bienestar.red.ClienteApi
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Base64
import java.util.Date
import java.util.Locale

/**
 * Evidencia fotográfica de una solicitud de apoyo: la cámara del teléfono.
 *
 * Es la segunda capacidad del dispositivo que usa esta aplicación (la otra
 * es el almacenamiento cifrado).
 *
 * POR QUÉ SE BORRAN LOS METADATOS EXIF ANTES DE SUBIR
 * ---------------------------------------------------
 * Una foto tomada con un teléfono trae, dentro del archivo, las coordenadas
 * GPS de dónde se tomó, la fecha exacta y el modelo del equipo. En una
 * aplicación cualquiera eso es inofensivo. Aquí no: la foto se adjunta a
 * una solicitud de apoyo que el sistema promete tratar bajo seudónimo, y
 * unas coordenadas GPS en el piso de una planta identifican a la persona
 * sin necesidad de su nombre. El servidor no puede quitar lo que ya le
 * llegó —quedaría en sus bitácoras de todos modos—, así que se quita aquí,
 * antes de que salga del teléfono.
 *
 * POR QUÉ LA FOTO VA AL ALMACENAMIENTO PRIVADO Y NO A LA GALERÍA
 * --------------------------------------------------------------
 * La cámara escribe en una carpeta de la caché de esta aplicación, que
 * ninguna otra puede leer, y se le da acceso puntual con un FileProvider.
 * Si fuera a la galería, la foto quedaría a la vista de cualquiera que tome
 * el teléfono y de cualquier aplicación con permiso de fotos.
 */
class EvidenciaRepositorio(
    private val contexto: Context,
    private val api: ClienteApi,
    private val url: String = BuildConfig.URL_DOCUMENTOS,
) {
    /** Crea el archivo destino y su URI para pasárselo a la cámara. */
    fun prepararArchivo(): Pair<File, Uri> {
        val carpeta = File(contexto.cacheDir, "evidencias").apply { mkdirs() }
        val sello = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val archivo = File(carpeta, "evidencia_$sello.jpg")
        val uri = FileProvider.getUriForFile(
            contexto, "${contexto.packageName}.archivos", archivo
        )
        return archivo to uri
    }

    /**
     * Quita los metadatos que identifican. Devuelve cuántos encontró.
     *
     * Se devuelve la cuenta para poder decírselo al usuario: «se quitaron 3
     * datos de ubicación de la foto» es información que merece ver, y es
     * también lo que hace comprobable que esto se hizo.
     */
    suspend fun limpiarMetadatos(archivo: File): Int = withContext(Dispatchers.IO) {
        if (!archivo.exists()) return@withContext 0
        val exif = ExifInterface(archivo.absolutePath)
        val sensibles = listOf(
            ExifInterface.TAG_GPS_LATITUDE,
            ExifInterface.TAG_GPS_LATITUDE_REF,
            ExifInterface.TAG_GPS_LONGITUDE,
            ExifInterface.TAG_GPS_LONGITUDE_REF,
            ExifInterface.TAG_GPS_ALTITUDE,
            ExifInterface.TAG_GPS_ALTITUDE_REF,
            ExifInterface.TAG_GPS_TIMESTAMP,
            ExifInterface.TAG_GPS_DATESTAMP,
            ExifInterface.TAG_GPS_PROCESSING_METHOD,
            ExifInterface.TAG_DATETIME,
            ExifInterface.TAG_DATETIME_ORIGINAL,
            ExifInterface.TAG_MAKE,
            ExifInterface.TAG_MODEL,
            ExifInterface.TAG_SOFTWARE,
        )
        var quitados = 0
        sensibles.forEach { etiqueta ->
            if (exif.getAttribute(etiqueta) != null) {
                exif.setAttribute(etiqueta, null)
                quitados++
            }
        }
        // La orientación NO se borra: sin ella la foto se ve de lado, y la
        // orientación no identifica a nadie.
        exif.saveAttributes()
        quitados
    }

    /**
     * Sube la evidencia ya limpia y la asocia a la solicitud.
     *
     * El archivo local se borra después: dejarlo en la caché haría que la
     * foto siguiera en el teléfono mucho después de haberla mandado, y el
     * usuario no tiene cómo saber que sigue ahí.
     */
    suspend fun subir(
        archivo: File,
        solicitudId: String,
        descripcion: String,
    ): JSONObject = withContext(Dispatchers.IO) {
        val bytes = archivo.readBytes()
        val cuerpo = JSONObject()
            .put("referencia", solicitudId)
            .put("nombre_archivo", archivo.name)
            .put("tipo_mime", "image/jpeg")
            .put("descripcion", descripcion)
            .put("contenido_base64", Base64.getEncoder().encodeToString(bytes))
        // Se usa /documentos/evidencia-apoyo y NO /documentos. El endpoint
        // general exige permisos de administración que un colaborador no
        // tiene ni debe tener; este exige APOYO_SOLICITAR, fija el tipo y
        // pone el seudónimo del lado del servidor. Mandar el tipo o el
        // seudónimo desde aquí no serviría de nada: el servicio los ignora
        // a propósito, porque un cliente no puede decidir a nombre de quién
        // se adjunta una evidencia.
        try {
            api.publicar("$url/api/v1/documentos/evidencia-apoyo", cuerpo)
        } finally {
            archivo.delete()
        }
    }

    fun descartar(archivo: File?) {
        archivo?.takeIf { it.exists() }?.delete()
    }
}
