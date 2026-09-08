# Clasificador de escritorio con modo SOAP

SC3705 · Juan Pablo Ramos Salazar · 610248

Esta es la aplicación Swing del ejercicio 1, extendida con un **modo cliente SOAP**.
No se conecta a PostgreSQL: habla con `library_soap_service` por HTTP/XML.

## Compilar y ejecutar

```bash
cd ejercicio03/desktop_classifier
javac cloudclassifier/*.java cloudclassifier/*/*.java
java cloudclassifier.CloudClassifierApp
```

1. Elige **Cliente SOAP**.
2. Escribe nombre, apellidos y correo.
3. Endpoint por defecto: `http://localhost:5000/soap`.
4. **Cargar pendientes** → lista de conceptos del catálogo real.
5. **Clasificar** usa el motor local (Regex o NLP) sobre la definición.
6. **Registrar en SOAP** envía `RegistrarClasificacion`.
7. Si el concepto ya está clasificado, la GUI muestra el Fault 409 en lenguaje claro.

Modo **Local** conserva el comportamiento del ejercicio 1.
