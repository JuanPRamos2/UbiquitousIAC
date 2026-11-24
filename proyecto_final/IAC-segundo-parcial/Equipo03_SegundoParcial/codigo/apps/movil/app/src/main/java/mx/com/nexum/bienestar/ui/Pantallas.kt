package mx.com.nexum.bienestar.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import mx.com.nexum.bienestar.AppViewModel
import mx.com.nexum.bienestar.Conexion
import mx.com.nexum.bienestar.EstadoApp
import mx.com.nexum.bienestar.Pantalla

/**
 * Interfaz de la aplicación móvil.
 *
 * El menú muestra solo lo que el perfil puede hacer, pero eso es cortesía:
 * la autorización de verdad la hace cada servicio consultando
 * usuarios.perfil_permiso en cada petición. Una aplicación que solo
 * escondiera botones no estaría protegiendo nada, porque cualquiera puede
 * hablarle al servicio sin pasar por la aplicación.
 */
@Composable
fun Raiz(modelo: AppViewModel) {
    val estado by modelo.estado.collectAsState()

    Column(Modifier.fillMaxSize()) {
        BarraSuperior(estado)
        if (estado.cargando) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
        }
        Mensajes(estado, modelo)

        Box(Modifier.weight(1f)) {
            when (estado.pantalla) {
                Pantalla.LOGIN -> PantallaLogin(modelo, estado)
                Pantalla.MENU -> PantallaMenu(modelo, estado)
                Pantalla.ENCUESTA -> PantallaEncuesta(modelo, estado)
                Pantalla.PARTICIPACION -> PantallaParticipacion(modelo, estado)
                Pantalla.APOYO -> PantallaApoyo(modelo, estado)
                Pantalla.AVISOS -> PantallaAvisos(modelo, estado)
            }
        }
    }
}

/**
 * Barra con el indicador de conexión.
 *
 * Tiene CUATRO estados y no dos, porque «degradado» es información
 * distinta: el servicio contesta y una dependencia suya no. Con un
 * indicador de dos estados, una caída de MongoDB se vería igual que estar
 * sin internet, y el usuario apagaría y prendería el wifi sin que eso
 * arreglara nada.
 */
@Composable
private fun BarraSuperior(estado: EstadoApp) {
    val (color, texto) = when (estado.conexion) {
        Conexion.CONECTADO -> MaterialTheme.colorScheme.secondary to "conectado"
        Conexion.DEGRADADO -> Color(0xFFB54708) to
            "servicio limitado${if (estado.detalleConexion.isNotBlank())
                ": ${estado.detalleConexion}" else ""}"
        Conexion.SIN_CONEXION -> MaterialTheme.colorScheme.error to "sin conexión"
        Conexion.SIN_PROBAR -> MaterialTheme.colorScheme.outline to "sin probar"
    }
    Surface(tonalElevation = 3.dp) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("Bienestar Nexum", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                if (estado.nombre.isNotBlank()) {
                    Text("${estado.nombre} · ${estado.perfil}",
                         fontSize = 12.sp,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Box(Modifier.size(10.dp).clip(CircleShape)
                .then(Modifier)) {
                Surface(color = color, modifier = Modifier.fillMaxSize(),
                        shape = CircleShape) {}
            }
            Spacer(Modifier.size(6.dp))
            Text(texto, fontSize = 11.sp, color = color)
        }
    }
}

@Composable
private fun Mensajes(estado: EstadoApp, modelo: AppViewModel) {
    estado.error?.let { mensaje ->
        Card(
            Modifier.fillMaxWidth().padding(12.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer),
        ) {
            Column(Modifier.padding(12.dp)) {
                estado.errorCodigo?.let {
                    // El código se muestra: es lo que permite buscar el
                    // problema y lo que quien da soporte necesita oír.
                    Text(it, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                }
                Text(mensaje, fontSize = 13.sp)
                TextButton(onClick = { modelo.limpiarMensajes() }) { Text("Entendido") }
            }
        }
    }
    estado.aviso?.let { mensaje ->
        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(12.dp)) {
                Text(mensaje, fontSize = 13.sp)
                TextButton(onClick = { modelo.limpiarMensajes() }) { Text("Cerrar") }
            }
        }
    }
}

// ============================================================== login
@Composable
private fun PantallaLogin(modelo: AppViewModel, estado: EstadoApp) {
    var correo by remember { mutableStateOf("") }
    var contrasena by remember { mutableStateOf("") }
    var problema by remember { mutableStateOf<String?>(null) }

    Column(
        Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Entrar", fontSize = 26.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(
            "Tus respuestas a la encuesta se guardan bajo seudónimo. Esta " +
                "aplicación nunca manda tu número de empleado al servidor, y " +
                "el servidor lo rechazaría si lo hiciera.",
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(20.dp))

        OutlinedTextField(
            value = correo,
            onValueChange = { correo = it; problema = null },
            label = { Text("Correo") },
            singleLine = true,
            isError = problema != null && correo.isBlank(),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = contrasena,
            onValueChange = { contrasena = it; problema = null },
            label = { Text("Contraseña") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        problema?.let {
            Spacer(Modifier.height(6.dp))
            Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
        }
        Spacer(Modifier.height(18.dp))
        Button(
            onClick = {
                problema = modelo.validarCredenciales(correo, contrasena)
                if (problema == null) modelo.entrar(correo, contrasena)
            },
            enabled = !estado.cargando,
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (estado.cargando) "Entrando…" else "Entrar") }
    }
}

// =============================================================== menú
@Composable
private fun PantallaMenu(modelo: AppViewModel, estado: EstadoApp) {
    Column(Modifier.fillMaxSize().padding(20.dp)
        .verticalScroll(rememberScrollState())) {
        Text("¿Qué quieres hacer?", fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text(
            "El menú muestra lo que tu perfil (${estado.perfil}) puede hacer. " +
                "Quien decide de verdad es cada servicio, en cada petición.",
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(18.dp))

        if (modelo.puede("AUTOREPORTE_RESPONDER")) {
            Opcion("Responder la encuesta",
                   "Una pregunta a la vez. Se guarda sola mientras avanzas.",
                   modelo::abrirEncuesta)
        }
        if (modelo.puede("PARTICIPACION_PROPIA")) {
            Opcion("Mi participación",
                   "En cuántas campañas has participado. No qué contestaste.",
                   modelo::verParticipacion)
        }
        if (modelo.puede("APOYO_SOLICITAR")) {
            Opcion("Pedir apoyo",
                   "Levanta una solicitud. Puedes adjuntar una foto.",
                   { modelo.ir(Pantalla.APOYO) })
        }
        if (modelo.puede("AVISO_CONSULTAR")) {
            Opcion("Avisos", "Lo que el programa te ha comunicado.",
                   modelo::verAvisos)
        }

        Spacer(Modifier.height(24.dp))
        Divider()
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = modelo::salir, modifier = Modifier.fillMaxWidth()) {
            Text("Cerrar sesión")
        }
        Spacer(Modifier.height(6.dp))
        Text(
            "Al cerrar sesión se revoca el token en el servidor y se borran " +
                "del teléfono el token, el borrador y tus datos.",
            fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun Opcion(titulo: String, descripcion: String, alTocar: () -> Unit) {
    Card(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text(titulo, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            Spacer(Modifier.height(2.dp))
            Text(descripcion, fontSize = 12.sp,
                 color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(10.dp))
            Button(onClick = alTocar) { Text("Abrir") }
        }
    }
}

// ============================================================ encuesta
@Composable
private fun PantallaEncuesta(modelo: AppViewModel, estado: EstadoApp) {
    val total = estado.reactivos.size
    val indice = estado.indiceReactivo

    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text(estado.campania?.nombre ?: "Encuesta",
             fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text("${estado.respuestas.size} de $total respondidas",
             fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(8.dp))
        LinearProgressIndicator(
            progress = { if (total == 0) 0f else estado.respuestas.size.toFloat() / total },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(24.dp))

        if (indice >= total) {
            // Última pantalla: revisar y enviar.
            Text("Listo para enviar", fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text(
                "Al enviar, tus respuestas viajan asociadas a un seudónimo. " +
                    "Ni quien administra el sistema puede ver qué contestaste: " +
                    "lo que se publica son promedios por unidad, con ruido, y " +
                    "solo cuando el grupo es lo bastante grande.",
                fontSize = 13.sp,
            )
            Spacer(Modifier.height(20.dp))
            Button(onClick = modelo::enviarEncuesta, enabled = !estado.cargando,
                   modifier = Modifier.fillMaxWidth()) { Text("Enviar") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = modelo::retroceder,
                           modifier = Modifier.fillMaxWidth()) {
                Text("Revisar la anterior")
            }
        } else {
            val reactivo = estado.reactivos[indice]
            Text("Pregunta ${indice + 1} de $total", fontSize = 12.sp,
                 color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(10.dp))
            Text(reactivo.texto, fontSize = 19.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(24.dp))

            // Escala de 1 a 5. Una pregunta por pantalla con botones grandes:
            // esta encuesta se contesta de pie, con una mano y en dos
            // minutos, y una lista de 24 preguntas en una sola pantalla se
            // contesta a la mitad.
            ETIQUETAS_ESCALA.forEachIndexed { i, etiqueta ->
                val valor = i + 1
                val elegido = estado.respuestas[reactivo.reactivoId] == valor
                Button(
                    onClick = { modelo.responder(reactivo.reactivoId, valor) },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    colors = if (elegido) CardDefaults.buttonColors()
                             else CardDefaults.outlinedButtonColors(),
                ) { Text("$valor — $etiqueta") }
            }

            Spacer(Modifier.height(16.dp))
            if (indice > 0) {
                TextButton(onClick = modelo::retroceder) { Text("← Anterior") }
            }
        }
    }
}

private val ETIQUETAS_ESCALA = listOf(
    "Nunca", "Rara vez", "A veces", "Con frecuencia", "Siempre",
)

// ======================================================= participación
@Composable
private fun PantallaParticipacion(modelo: AppViewModel, estado: EstadoApp) {
    Column(Modifier.fillMaxSize().padding(20.dp)
        .verticalScroll(rememberScrollState())) {
        Text("Mi participación", fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(12.dp))
        Text(estado.participacion, fontSize = 14.sp)
        Spacer(Modifier.height(24.dp))
        OutlinedButton(onClick = { modelo.ir(Pantalla.MENU) }) { Text("Volver") }
    }
}

// ============================================================== apoyo
@Composable
private fun PantallaApoyo(modelo: AppViewModel, estado: EstadoApp) {
    var mensaje by remember { mutableStateOf("") }
    var problema by remember { mutableStateOf<String?>(null) }

    val tomarFoto = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { exito -> modelo.fotoTomada(exito) }

    Column(Modifier.fillMaxSize().padding(20.dp)
        .verticalScroll(rememberScrollState())) {
        Text("Pedir apoyo", fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(
            "Quien atienda tu solicitud verá el caso bajo tu seudónimo, no tu " +
                "nombre.",
            fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(16.dp))

        OutlinedTextField(
            value = mensaje,
            onValueChange = { mensaje = it; problema = null },
            label = { Text("¿De qué se trata?") },
            minLines = 4,
            isError = problema != null,
            modifier = Modifier.fillMaxWidth(),
        )
        problema?.let {
            Spacer(Modifier.height(6.dp))
            Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
        }

        Spacer(Modifier.height(16.dp))
        if (estado.fotoTomada) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text("Foto adjunta", fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Se quitaron ${estado.metadatosQuitados} datos del " +
                            "archivo (ubicación, fecha exacta y modelo del " +
                            "equipo) antes de que salga del teléfono. Unas " +
                            "coordenadas GPS en el piso de una planta " +
                            "identifican a una persona sin necesidad de su " +
                            "nombre.",
                        fontSize = 12.sp,
                    )
                    Spacer(Modifier.height(8.dp))
                    TextButton(onClick = modelo::descartarFoto) { Text("Quitar la foto") }
                }
            }
        } else {
            OutlinedButton(
                onClick = { tomarFoto.launch(modelo.prepararFoto()) },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Tomar una foto (opcional)") }
        }

        Spacer(Modifier.height(20.dp))
        Button(
            onClick = {
                problema = modelo.validarMensajeApoyo(mensaje)
                if (problema == null) modelo.pedirApoyo(mensaje, estado.fotoTomada)
            },
            enabled = !estado.cargando,
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (estado.cargando) "Enviando…" else "Enviar solicitud") }

        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = { modelo.ir(Pantalla.MENU) },
                       modifier = Modifier.fillMaxWidth()) { Text("Cancelar") }
    }
}

// ============================================================= avisos
@Composable
private fun PantallaAvisos(modelo: AppViewModel, estado: EstadoApp) {
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text("Avisos", fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(12.dp))
        if (estado.avisos.isEmpty()) {
            Text("No tienes avisos.", fontSize = 14.sp,
                 color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            LazyColumn(Modifier.weight(1f)) {
                items(estado.avisos) { aviso ->
                    Card(Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
                        Column(Modifier.padding(14.dp)) {
                            Text(aviso.titulo, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(4.dp))
                            Text(aviso.cuerpo, fontSize = 13.sp)
                            Spacer(Modifier.height(4.dp))
                            Text(aviso.fecha, fontSize = 11.sp,
                                 color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = { modelo.ir(Pantalla.MENU) }) { Text("Volver") }
    }
}
