# Plan de pruebas

Cada prueba: entrada → esperado → obtenido → evidencia → conclusión.

| ID | Prueba | Entrada | Esperado | Obtenido | Estado |
| --- | --- | --- | --- | --- | --- |
| P01 | Conceptos pendientes | Correo válido | Lista con ISBN, título, concepto, categoría | Lista desde el catálogo | OK en modo demostración y con el catálogo real |
| P02 | Registrar IaaS/PaaS/SaaS/FaaS | Conceptos reales de varios libros | Insert en clasificaciones_cloud | Response con clasificacionId | OK |
| P03 | Progreso de usuario | Mismo correo | clasificados + pendientes | Totales coherentes | OK |
| P04 | Estadísticas autenticadas | UsernameToken correcto | Conteos por modelo | Operación protegida | OK |
| N01 | Duplicado | Misma pareja usuario+concepto | SOAP Fault 409 | DuplicadoFault + mensaje claro | Cubierto |
| N02 | Concepto inexistente | conceptId=999999 | SOAP Fault de cliente | NotFoundFault 404 | Cubierto |
| N03 | Modelo inválido | modelo=XaaS | SOAP Fault de validación | ValidationFault | Cubierto |
| N04 | XML inválido | `<not-xml` | Fault de cliente; sin registro | parse_envelope lanza ValueError | Test unitario |
| N05 | WS-Security incorrecto | password distinta | Fault 401 | SecurityFault | Cubierto |
| N06 | Falla interna | servicio caído | Fault de servidor genérico | XML limpio | Cubierto en server_fault |

Pruebas unitarias locales (sin BD):

```bash
cd library_soap_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -q
```
