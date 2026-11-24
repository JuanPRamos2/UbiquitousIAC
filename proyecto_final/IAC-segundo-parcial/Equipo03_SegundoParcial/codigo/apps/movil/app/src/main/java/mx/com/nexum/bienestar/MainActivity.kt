package mx.com.nexum.bienestar

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import mx.com.nexum.bienestar.ui.Raiz

class AplicacionBienestar : Application()

class MainActivity : ComponentActivity() {

    private val modelo: AppViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TemaBienestar {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    Raiz(modelo)
                }
            }
        }
    }
}

private val claro = lightColorScheme(
    primary = Color(0xFF1D4ED8),
    secondary = Color(0xFF027A48),
    error = Color(0xFFB42318),
)

private val oscuro = darkColorScheme(
    primary = Color(0xFF93B4FF),
    secondary = Color(0xFF6CE9A6),
    error = Color(0xFFFDA29B),
)

@Composable
fun TemaBienestar(contenido: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) oscuro else claro,
        content = contenido,
    )
}
