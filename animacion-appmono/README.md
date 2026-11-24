# LIBRERÍA UDEM - Arquitectura Interactiva (Opción B)

Aplicación web didáctica y animada que explica visualmente la arquitectura técnica del proyecto, estructurada en su formato más simple posible (3 archivos planos en la raíz).

## Requisitos
Solamente un navegador moderno. No requiere compilar, empaquetar ni instalar NPM. No usa WebGL pesado. Utiliza SVG puro y GSAP vía CDN.

## 🚀 Cómo ejecutarlo localmente

1. Extrae el contenido de este archivo ZIP en una carpeta.
2. Abre la carpeta y simplemente da doble click en el archivo `index.html`. 

(Si por alguna razón las políticas locales de tu navegador bloquean la ejecución, puedes levantar un servidor local ligero ejecutando `python -m http.server 8000` en la terminal y abriendo `http://localhost:8000`).

## 🗂 Estructura Plana (Opción B)
Todo el proyecto está condensado sin subcarpetas para facilitar la edición rápida:
*   `index.html`: Define la UI, la estructura del canvas SVG y los botones de simulación.
*   `styles.css`: Contiene todas las variables de color, layout de la interfaz y estilos responsivos.
*   `app.js`: Contiene en la parte superior la constante `archData` (donde puedes modificar los nodos y conexiones) y el motor de dibujo interactivo GSAP en la parte inferior.
