# Cómo explicar el clasificador en clase

El profesor pide **no copiar código de IA sin entenderlo**. Esta nota resume las decisiones para que puedas defender el programa.

## Idea general

El programa no “adivina” con un LLM. Lee el texto, busca evidencia de cada modelo Cloud y elige el que suma más puntos.

- **IaaS**: el cliente administra máquinas, redes, discos, sistema operativo.
- **PaaS**: despliega la aplicación y el proveedor se encarga de servidores y SO.
- **SaaS**: usa software listo (correo, docs) desde el navegador, casi siempre con suscripción.
- **FaaS**: corre una función pequeña cuando ocurre un evento (subir un archivo, un HTTP, un timer).

## Piezas de la solución

1. **GUI (`ClassifierWindow`)**  
   Pide nombre, apellido y descripción. Tiene dos motores (Regex y NLP). Al pulsar Clasificar llama a `ClassifierService`. Si algo falla, muestra un diálogo; no deja que Swing se caiga.

2. **CLI (`CloudClassifier`)**  
   Mismo servicio. Por eso `java CloudClassifier "máquinas virtuales..."` y la ventana coinciden.

3. **Validación (`InputValidator`)**  
   Nombre/apellido: no vacíos, solo letras (con acentos), espacios o guiones.  
   Descripción: mínimo 8 caracteres.  
   Si no se cumple, lanza `InvalidInputException`.

4. **RegexClassifier (versión 1)**  
   Cada categoría tiene patrones. Ejemplo: `maquinas?\\s+virtuales?` detecta “máquina virtual” y “máquinas virtuales”.  
   Decisión importante: si el texto dice **“sin administrar servidores”**, eso es típico de **PaaS**. Sin ese filtro, la palabra “servidores” empujaría mal hacia IaaS (pasa en el ejemplo B del PDF).

5. **TextPreprocessor + NlpClassifier (versión 2)**  
   Flujo de la Parte 5:

   ```
   texto original
     → minúsculas
     → quitar acentos (normalización)
     → quitar signos
     → tokenizar por espacios
     → quitar stopwords (el, la, de, para, the, ...)
     → stemming simple (virtuales → virtual, funciones → funcion)
     → sumar puntos si el stem o la frase pertenece a una categoría
   ```

   El stemming no es un motor lingüístico profesional; es un recorte de sufijos para que plurales y verbos coincidan. Eso es suficiente para el ejercicio y se puede explicar.

6. **Puntuación y empate**  
   Gana quien tenga más puntos. Si todos quedan en 0, o hay empate, el resultado es **Indeterminado**. Es más honesto que forzar una etiqueta.

## Por qué hay dos motores

El enunciado pide empezar con Regex y luego evolucionar a NLP **sin usar un LLM para dar la categoría**. En la GUI puedes cambiar el radio button y comparar. En CLI:

```bash
java -cp bin CloudClassifier --regex --verbose "..."
java -cp bin CloudClassifier --nlp --verbose "..."
```

`--verbose` muestra tokens, stems y puntajes: sirve para screenshots y para el reporte.

## Limitaciones (útil en conclusiones)

- No entiende ironía ni textos muy ambiguos.
- Un servicio real puede mezclar modelos (por ejemplo almacenamiento IaaS + función FaaS).
- El stemming es básico y está pensado para español.
- Las reglas se pueden ampliar con más proveedores (OCI, IBM Cloud, etc.).

Si el profesor pregunta “¿qué modificarías?”, una respuesta sólida es: ampliar el léxico con servicios reales (EC2, App Engine, Gmail, Lambda), y en una etapa posterior usar un modelo de embeddings, no un LLM que responda la etiqueta a ciegas.
