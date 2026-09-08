# Preguntas para reflexionar (respuestas individuales)

1. **Campo obligatorio nuevo en RegistrarClasificacion.** Los clientes viejos dejarían de validar contra el XSD y fallarían al serializar. SOAP es estricto porque el WSDL es un contrato compilable, no un JSON “si viene el campo, lo uso”.

2. **Superficie del WSDL.** Expone operaciones, tipos y el endpoint. Un atacante no ve SQL ni hashes, pero sí cómo invocar el servicio. En producción ocultaría el WSDL público, exigiría TLS y autenticaría más operaciones.

3. **XSD en vez de texto plano.** `xsd:int` y el enum CloudModelo rechazan “abc” o “XaaS” antes de tocar la BD. El texto plano aplaza el error al código de cada cliente.

4. **Boilerplate vs operación.** Envelope, Header, namespaces SOAP y `Body` se repiten. Cambia el elemento hijo (`RegistrarClasificacion` vs `ObtenerProgresoUsuario`) y sus campos. Spyne ahorraría ese boilerplate y generaría el WSDL; se perdería visibilidad pedagógica.

5. **Overhead XML vs JSON.** 623 B frente a 164 B en el ejemplo de registro (~74 % estructura). Vale la pena en banca, SAP, partners con contrato legal. No vale la pena en un API interno de un solo frontend.

6. **Fault en el Body.** SOAP puede viajar por HTTP, SMTP u otros. El error es del mensaje, no del transporte. REST acopla el error al status HTTP porque el transporte *es* el contrato.

7. **GUI ante Fault 400 vs 500.** 409/400: el usuario puede corregir (otro concepto, otro modelo). 500: no culpamos al usuario; mensaje genérico y reintento. No es lo mismo.

8. **Tabla clasificadores vs users.** `users` exige password_hash y roles del monolito. Insertar ahí crearía cuentas web sin consentimiento, chocaría con el único admin y mezclaría autenticación. Por eso hay tabla propia.

9. **Si el monolito renombra isbn.** El módulo se rompe en la vista y en las FK. Protección: vista anti-corrupción, o dejar de compartir BD y hablar por un contrato estable.

10. **Quién llama a RegistrarClasificacion.** Hoy cualquiera en la red del laboratorio puede clasificar. WS-Security encaja en el Header de operaciones sensibles (ya en estadísticas; en producción, en todas).

11. **Confiar en el correo.** No es suficiente en producción (spoofing). En el ejercicio sí: identifica al clasificador sin montar un IdP. Queda documentado como limitación.

12. **Por qué SOAP y no un POST JSON.** Porque hay contrato WSDL/XSD, generación de clientes, Faults tipados y herramientas de integración empresarial. El JSON es más simple; SOAP es más formal.

13. **SOAP en 2026.** Bancos, gobierno, ERPs, telcos y partners B2B que ya tienen WSDL firmados. Un startup verde no lo elegiría como primer API.

14. **Dolor XML a mano vs REST.** 8 / 10. Construir namespaces y Faults a mano es tedioso frente a `res.json`. El número se comparará en la siguiente sesión.

15. **Complejidad vs valor.** Complejidad innecesaria en este laboratorio: el Envelope verboso y los namespaces duplicados. Valor real: el contrato, los Faults y la interoperabilidad.
