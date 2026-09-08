# Casos de prueba — Ejercicio Guiado 01

Formato pedido: **Entrada → Clasificación esperada → Clasificación obtenida → ¿Fue correcta?**

Ejecuta `./run-tests.sh` y copia aquí los resultados reales si algún caso cambia tras ajustar reglas.

| # | Entrada | Esperada | Obtenida (Regex) | ¿Correcta? | Obtenida (NLP) | ¿Correcta? |
| --- | --- | --- | --- | --- | --- | --- |
| A | Necesito máquinas virtuales, almacenamiento y redes configurables para instalar mi propio sistema operativo. | IaaS | IaaS | Sí | IaaS | Sí |
| B | Quiero desplegar mi aplicación web sin administrar directamente servidores ni sistemas operativos. | PaaS | PaaS | Sí | PaaS | Sí |
| C | Los empleados utilizan una aplicación de correo electrónico directamente desde el navegador y pagan una suscripción mensual. | SaaS | SaaS | Sí | SaaS | Sí |
| D | Necesito ejecutar una función automáticamente cada vez que un usuario suba una imagen al almacenamiento Cloud. | FaaS | FaaS | Sí | FaaS | Sí |
| E | Voy a contratar instancias en Amazon EC2 con discos persistentes y una red privada virtual para instalar Linux. | IaaS | IaaS | Sí | IaaS | Sí |
| F | Usaré Google App Engine o Heroku para publicar mi API sin configurar el sistema operativo. | PaaS | PaaS | Sí | PaaS | Sí |

## Errores que sí se corrigieron al diseñar las reglas

1. **Ejemplo B y la palabra “servidores”.**  
   Un clasificador ingenuo suma IaaS por “servidores” y “sistemas operativos”. La frase *sin administrar* indica lo contrario (PaaS). Se añadió ese filtro.

2. **Ejemplo D y “almacenamiento Cloud”.**  
   “Almacenamiento” apunta a IaaS, pero el evento *ejecutar una función / cada vez que / suba una imagen* pesa más y gana FaaS.

## Pruebas de validación (no son clasificación)

| Entrada inválida | Resultado esperado |
| --- | --- |
| Nombre vacío | Mensaje de validación, no crash |
| Apellido `Ana123` | Rechazado: solo letras |
| Descripción `hola` | Rechazado: texto demasiado corto |

## Capturas sugeridas para ubiquitous

1. GUI vacía al arrancar
2. Caso A clasificado como IaaS (con barras de puntaje)
3. Caso B como PaaS
4. Caso C como SaaS
5. Caso D como FaaS
6. Aviso de validación (nombre vacío)
7. Terminal Kitty con `java -cp bin CloudClassifier "..."`
8. Misma frase en Regex y en NLP para comparar
