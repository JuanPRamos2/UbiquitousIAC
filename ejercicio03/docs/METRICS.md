# Métricas para comparar después con REST

Registradas el 4 de septiembre de 2026. Conservar para la sesión SOAP vs REST.

| Métrica | Valor |
| --- | --- |
| Tiempo aproximado de desarrollo del módulo SOAP | 10 horas (diseño de contrato, SQL, Flask, GUI, evidencias) |
| LOC servicio Python (sin tests) | 629 |
| LOC cliente SOAP Java (`cloudclassifier/soap`) | 350 |
| LOC GUI Swing (incluye modo local + SOAP) | 499 |
| LOC cliente zeep | 74 |
| LOC tests XML/seguridad | 56 |
| Solicitud `RegistrarClasificacion` (SOAP/XML) | 623 bytes |
| Respuesta de registro (SOAP/XML) | 521 bytes |
| Equivalente JSON de la misma solicitud | 164 bytes |
| Porcentaje aproximado de estructura XML frente a datos | ~74 % estructura / ~26 % negocio |
| Operaciones en el WSDL | 4 |

El overhead de XML se justifica cuando hay contrato XSD, Faults tipados, generación de clientes e integraciones heterogéneas. No se justifica para un CRUD interno de un solo equipo que ya habla JSON.
