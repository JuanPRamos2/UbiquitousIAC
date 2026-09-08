# Sitio web del curso (carpeta `web/`)

Página personal para ubiquitous, dentro del mismo proyecto de code-oss.

## Cómo se usa en ubiquitous

Sube la carpeta `web/` a `public_html`. El clasificador corre en el navegador: en Ejercicio guiado 1 pulsa **Correr clasificador**.

No se puede ejecutar Java Swing desde el servidor SSH. La página replica las mismas reglas (Regex y NLP) en `js/clasificador.js`.

Desde code-oss: clic derecho en `web/index.html` → Open with Live Server, o en Kitty:

```bash
xdg-open /home/bold/Documents/IAC/cloud_models_classifier/web/index.html
```

## Archivos

| Archivo | Qué es |
| --- | --- |
| `index.html` | Inicio: foto, nombre, UDEM, matrícula y materia |
| `ejercicios.html` | Lista de ejercicios guiados |
| `ejercicios/eg01.html` | Ejercicio guiado 1 |
| `css/estilos.css` | Estilos (gris, naranja y acentos) |
| `js/app.js` | Menú, pie de página y lista de ejercicios |
| `img/foto.jpg` | Tu fotografía (colócala con ese nombre) |

Si no hay `foto.jpg`, se muestra el avatar `img/foto.svg`. Copia tu foto a `web/img/foto.jpg`.
