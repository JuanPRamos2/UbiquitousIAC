# Plan de pruebas

Cada prueba: entrada → esperado → obtenido → evidencia → conclusión.

| ID | Prueba | Entrada | Esperado | Obtenido | Estado |
| --- | --- | --- | --- | --- | --- |
| P01 | Conceptos pendientes | Correo válido | Lista con ISBN, título, concepto, categoría | Lista desde `v_catalogo_conceptos` | Diseño listo; ejecutar con Flask + BD |
| P02 | Registrar IaaS/PaaS/SaaS/FaaS | Conceptos reales de varios libros | Insert en `clasificaciones_cloud` | SP `sp_registrar_clasificacion` | Diseño listo |
| P03 | Progreso de usuario | Mismo correo | clasificados + pendientes | `sp_obtener_progreso_usuario` | Diseño listo |
| P04 | Estadísticas autenticadas | UsernameToken correcto | Conteos por modelo | Operación protegida | Diseño listo |
| N01 | Duplicado | Misma pareja usuario+concepto | SOAP Fault 409 | `DuplicadoFault` + GUI clara | Cubierto en código y XML de evidencia |
| N02 | Concepto inexistente | conceptId=999999 | SOAP Fault de cliente | `CONCEPTO_INEXISTENTE` → 404 | Cubierto en repositorio |
| N03 | Modelo inválido | modelo=XaaS | SOAP Fault de validación | Enum + CHECK + validación Python | Cubierto |
| N04 | XML inválido | `<not-xml` | Fault de cliente; sin SQL | `parse_envelope` lanza ValueError | Test unitario |
| N05 | WS-Security incorrecto | password distinta | Fault 401 | PBKDF2 compare | Cubierto |
| N06 | Falla de PostgreSQL | BD caída | Fault de servidor genérico | log técnico, XML limpio | Cubierto en `server_fault` |

Pruebas unitarias locales (sin BD):

```bash
cd library_soap_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -q
```
