# Base de datos — Plataforma de Bienestar Laboral (v2)

Script relacional que responde punto por punto a la retroalimentación recibida.
**Verificado**: ejecutado completo en PostgreSQL 16 sin errores, con batería de pruebas.

---

## 1. Cómo levantarla

```bash
createdb bienestar_nexum
psql -d bienestar_nexum -f bienestar_nexum_v2.sql
```

Con Docker:
```bash
docker run --name nexum-pg -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=bienestar_nexum -p 5432:5432 -d postgres:16
docker cp bienestar_nexum_v2.sql nexum-pg:/tmp/
docker exec -it nexum-pg psql -U postgres -d bienestar_nexum -f /tmp/bienestar_nexum_v2.sql
```

---

## 2. Qué cambió respecto a la versión anterior

| Observación del profesor | Qué se hizo |
|---|---|
| **«No hay privacidad diferencial. TACHE»** | Mecanismo de Laplace real: ε, presupuesto, sensibilidad, clipping y composición secuencial. Ver sección 4. |
| «Un umbral k no es privacidad diferencial» | Ahora conviven los **dos** controles. El umbral suprime grupos pequeños; el ruido acota lo que se aprende aunque se repitan consultas. |
| «MongoDB, contenedores y pruebas debían analizarse, no implementarse» | Las respuestas viven en **PostgreSQL**. MongoDB queda como análisis. |
| «Seudonimización ≠ anonimización» | El comentario de `consentimiento.seudonimo` lo dice explícitamente, y la sección de transparencia TR-05 lo explica al usuario. |
| «Falta cerrar el ciclo completo» | Las 22 etapas están implementadas, de consentimiento a evaluación de la intervención. |
| «La pantalla de consentimiento debe explicar…» | `consentimiento.aviso_privacidad` tiene **una columna por cada elemento** que el profesor pidió. |
| «Falta matriz de minimización» | `gobernanza.minimizacion_dato`: 13 datos, 8 de ellos documentados como **excluidos a propósito**. |
| «Concepto formal de fuente autorizada» | `catalogo.fuente_autorizada`: 6 permitidas y **5 prohibidas** (correo, chat, GPS, teclado, navegación). |
| «Falta tendencia longitudinal» | Vista `agregado.v_tendencia` con 4 campañas y lectura metodológica. |
| «No debe existir score individual» | Garantía G3 verificable: los esquemas de riesgo y agregación **no pueden** referirse a una persona. |
| «Intervenciones organizacionales, nunca a una persona» | `intervencion.plan` no tiene columna de empleado objetivo. Garantía G1 lo verifica. |
| «Motor de reglas transparente, no IA» | `riesgo.regla` con condición legible, y cada detección guarda su explicación. |
| «Transparencia funcional, no solo documental» | `transparencia.seccion`: las 12 secciones viven en la base de datos. |
| «Cinco roles recomendados» | Se pasó de 7 a **5 perfiles**: COLABORADOR, LÍDER, ESPECIALISTA, AUDITOR, ADMINISTRADOR. |
| «El administrador no debería ver respuestas individuales» | Ningún perfil tiene ese permiso — **no existe en el catálogo de permisos**. |

---

## 3. Credenciales de prueba

Contraseña para todas: **`demo123`** (bcrypt vía pgcrypto).

| usuario_id | Perfil | Correo |
|---|---|---|
| USR-00001 | Colaborador | ana.perez@nexum.com.mx |
| USR-00005 | Líder (Turno B) | lucia.hernandez@nexum.com.mx |
| USR-00003 | Especialista de bienestar | mariana.solis@nexum.com.mx |
| USR-00004 | Auditor | roberto.garcia@nexum.com.mx |
| USR-00002 | Administrador | carlos.ramirez@nexum.com.mx |

---

## 4. Privacidad diferencial: cómo está implementada

**Flujo exacto que pidió el profesor:**

```
Respuestas → Validación → Clipping → Verificación n ≥ k → Cálculo agregado
          → Sensibilidad → Mecanismo Laplace → Resultado protegido → Publicación
```

Todo ocurre dentro de `agregado.fn_calcular_agregado_protegido()`.

**Parámetros y su justificación** (`agregado.parametro_privacidad`):

| Parámetro | Valor | Por qué |
|---|---|---|
| `k_umbral_minimo` | 5 | Suprime grupos donde la sola pertenencia identifica. |
| `epsilon_por_consulta` | **1.0** | Ver análisis abajo. |
| `presupuesto_campania` | 8.0 | Cubre las 6 consultas de un tablero (global + 5 dimensiones) más margen. |
| `error_tolerado` | 0.30 | Media escala de respuesta. |

**Por qué ε = 1.0 y no 0.2.** El error esperado del mecanismo es `b = (hi−lo)/(n·ε)`.
Con el ejemplo de ε = 0.2 y las unidades del caso (n = 8), el error esperado
es **2.5 puntos sobre una escala de 1 a 5**: el ruido supera al dato y publicar
ese valor sería engañoso. La condición de utilidad `n·ε ≥ (hi−lo)/error_tolerado`
exige n ≥ 67 para ε = 0.2, tamaño que ninguna unidad alcanza.
Con ε = 1.0 se exige n ≥ 14 y el error baja a 0.5 puntos.

Esto se puede demostrar en vivo:
```sql
SELECT * FROM agregado.fn_analisis_utilidad(8, 0.2);   -- ruido domina
SELECT * FROM agregado.fn_analisis_utilidad(8, 1.0);   -- utilizable
SELECT * FROM agregado.fn_analisis_utilidad(30, 1.0);  -- precisión suficiente
```

**Honestidad metodológica.** Cada resultado declara su precisión
(`PRECISION_SUFICIENTE` / `PRECISION_LIMITADA` / `RUIDO_DOMINANTE`) y la vista
de tendencia marca cada variación como `VARIACION_INTERPRETABLE` o
`DENTRO_DEL_RUIDO`. Con n = 8 el sistema **admite** que un valor puntual no es
confiable. Esa es la respuesta correcta, no ocultar la limitación.

**Presupuesto.** Cada consulta consume ε y se registra en
`agregado.consulta_privada`. Al agotarse, el sistema responde
`PRESUPUESTO_PRIVACIDAD_AGOTADO` y deja de publicar.

---

## 5. Garantías verificables

```sql
SELECT * FROM gobernanza.fn_verificar_garantias();
```

| Garantía | Qué comprueba |
|---|---|
| G1 | Ninguna tabla de intervención admite persona objetivo |
| G2 | El esquema de autoreporte no contiene `empleado_id` |
| G3 | Riesgo y agregación no pueden referirse a una persona |
| G4 | Ningún resultado publicado carece de ε aplicado |
| G5 | Ningún resultado publicado viene de un grupo menor que k |
| G6 | Ningún instrumento se alimenta de una fuente de vigilancia |

Estas garantías se comprueban **contra el catálogo del sistema**, no contra la
interfaz: se sostienen aunque alguien consulte la base directamente.

---

## 6. Datos de prueba

- **Call Center Turno B**: 8 colaboradores → supera k, publica con ruido
- **Logística Turno A**: 3 colaboradores, 1 con consentimiento revocado → 2 elegibles, **siempre suprimido**
- **4 campañas consecutivas** → permiten construir tendencia
- **1 consentimiento revocado** → demuestra que revocar no borra el historial

---

## 7. Lo que el modelo hace imposible

- No existe tabla de puntaje individual de burnout.
- No existe permiso de lectura de respuestas individuales — para ningún perfil.
- `intervencion.tipo_intervencion` tiene `CHECK (ambito = 'ORGANIZACIONAL')`.
- El tablero del líder **no muestra n exacto**, para no facilitar inferencia por diferencia.
- El esquema `portal` separa las vistas de datos propios del esquema de respuestas.

---

## 8. Pendientes declarados

1. **Presupuesto por consultante.** Hoy el presupuesto es por campaña y unidad. Un atacante con varias cuentas podría sumar consultas. Corresponde al segundo parcial.
2. **Consultas por subgrupo.** El ataque por diferencia entre subgrupos no está mitigado más allá de k y ε.
3. **Auditor y seudónimo.** El auditor verifica consentimiento por seudónimo. Es mínimo privilegio, pero conviene evaluar si basta un identificador de evidencia sin el seudónimo.
