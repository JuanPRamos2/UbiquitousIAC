/**
 * Logica de dominio para organizational-service (Puerto 8117).
 *
 * Administra el organigrama empresarial, arboles jerarquicos (CTE) y garantiza
 * que ninguna unidad organizacional opere con plantilla < 5 para blindar
 * contra la inferencia de respuestas individuales.
 */
import { ErrorApi } from "@bienestar/comun/errores.js";
import { consultar, consultarUno, ejecutar } from "@bienestar/comun/postgres.js";
import { traducirErrorPg } from "@bienestar/comun/pg-errores.js";
import { validarAlcanceUnidad, obtenerUnidadesSubordinadas } from "@bienestar/comun/alcance.js";
import { texto, entero, booleano } from "@bienestar/comun/validacion.js";
import { registrarBitacora } from "@bienestar/comun/auditoria.js";

const COLS_UNIDAD = `unidad_organizacional_id, nombre, descripcion, tipo,
  unidad_padre_id, nivel_jerarquico, plantilla_declarada, activa,
  fecha_creacion, fecha_actualizacion`;

export async function listarUnidades({ activa = null, actor = null, dbPg = null }) {
  const queryPg = dbPg || consultar;
  let sql = `SELECT ${COLS_UNIDAD} FROM organizacion.unidad_organizacional WHERE 1=1`;
  const params = [];
  let idx = 1;

  if (activa !== null) {
    sql += ` AND activa = $${idx++}`;
    params.push(booleano(activa, "activa"));
  }

  // Filtrado por alcance jerarquico si el actor es LIDER
  const alcance = actor?.unidad_alcance || actor?.unidad_id;
  if (alcance) {
    const permitidas = await obtenerUnidadesSubordinadas(alcance);
    sql += ` AND unidad_organizacional_id = ANY($${idx++})`;
    params.push(permitidas);
  }

  sql += ` ORDER BY nivel_jerarquico, nombre`;
  const filas = await queryPg(sql, params);
  return filas;
}

export async function obtenerUnidadPorId(id, { actor = null, dbPg = null } = {}) {
  const uId = texto(id, "id");
  if (actor) {
    await validarAlcanceUnidad(actor, uId);
  }

  const queryPg = dbPg || consultarUno;
  const unidad = await queryPg(
    `SELECT ${COLS_UNIDAD} FROM organizacion.unidad_organizacional WHERE unidad_organizacional_id = $1`,
    [uId]
  );
  if (!unidad) {
    throw new ErrorApi("UNIDAD_NO_ENCONTRADA", `No existe la unidad organizacional '${uId}'.`, 404);
  }
  return unidad;
}

export async function obtenerArbolJerarquico(id, { actor = null, dbPg = null } = {}) {
  const uId = texto(id, "id");
  if (actor) {
    await validarAlcanceUnidad(actor, uId);
  }

  const queryPg = dbPg || consultar;
  const filas = await queryPg(
    `WITH RECURSIVE arbol AS (
       SELECT ${COLS_UNIDAD}, 1 AS profundidad
         FROM organizacion.unidad_organizacional
        WHERE unidad_organizacional_id = $1
       UNION ALL
       SELECT u.unidad_organizacional_id, u.nombre, u.descripcion, u.tipo,
              u.unidad_padre_id, u.nivel_jerarquico, u.plantilla_declarada,
              u.activa, u.fecha_creacion, u.fecha_actualizacion,
              a.profundidad + 1
         FROM organizacion.unidad_organizacional u
         JOIN arbol a ON u.unidad_padre_id = a.unidad_organizacional_id
        WHERE u.activa = true
     )
     SELECT * FROM arbol ORDER BY profundidad, nivel_jerarquico, nombre`,
    [uId]
  );

  if (!filas.length) {
    throw new ErrorApi("UNIDAD_NO_ENCONTRADA", `No existe la unidad raíz '${uId}'.`, 404);
  }

  return {
    unidad_raiz_id: uId,
    total_nodos: filas.length,
    nodos: filas,
  };
}

export async function crearUnidad({
  unidad_id,
  nombre,
  descripcion = null,
  tipo = "DEPARTAMENTO",
  padre_id = null,
  nivel = 1,
  plantilla_declarada,
  activa = true,
  req = null,
  dbPg = null,
}) {
  const nom = texto(nombre, "nombre", { minLong: 3, maxLong: 100 });
  const tip = texto(tipo, "tipo", { minLong: 2, maxLong: 30 });
  const niv = entero(nivel, "nivel", { min: 1, max: 10 });
  
  // Regla estricta de no identificacion: plantilla declarada >= 5
  const plantilla = entero(plantilla_declarada, "plantilla_declarada", {
    min: 5,
    requerido: true,
  });

  const id = unidad_id ? texto(unidad_id, "unidad_id") : `UNID-${Math.random().toString(36).slice(2, 7).toUpperCase()}`;

  try {
    const queryPg = dbPg || consultarUno;
    const creada = await queryPg(
      `INSERT INTO organizacion.unidad_organizacional
          (unidad_organizacional_id, nombre, descripcion, tipo, unidad_padre_id,
           nivel_jerarquico, plantilla_declarada, activa)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       RETURNING ${COLS_UNIDAD}`,
      [id, nom, descripcion ? String(descripcion).trim() : null, tip, padre_id || null, niv, plantilla, booleano(activa, "activa")]
    );

    if (req) {
      await registrarBitacora(req, "CATALOGO_MODIFICADO", "EXITO", {
        tipo_recurso: "unidad_organizacional",
        recurso_id: id,
      });
    }

    return creada;
  } catch (err) {
    throw traducirErrorPg(err, "No se pudo crear la unidad organizacional.");
  }
}

export async function actualizarUnidad(id, datos = {}, { req = null, dbPg = null } = {}) {
  const uId = texto(id, "id");
  const existentes = await obtenerUnidadPorId(uId, { dbPg });

  const campos = [];
  const valores = [uId];
  let idx = 2;

  if (datos.nombre !== undefined) {
    campos.push(`nombre = $${idx++}`);
    valores.push(texto(datos.nombre, "nombre", { minLong: 3, maxLong: 100 }));
  }
  if (datos.descripcion !== undefined) {
    campos.push(`descripcion = $${idx++}`);
    valores.push(datos.descripcion ? String(datos.descripcion).trim() : null);
  }
  if (datos.tipo !== undefined) {
    campos.push(`tipo = $${idx++}`);
    valores.push(texto(datos.tipo, "tipo"));
  }
  if (datos.padre_id !== undefined) {
    campos.push(`unidad_padre_id = $${idx++}`);
    valores.push(datos.padre_id ? texto(datos.padre_id, "padre_id") : null);
  }
  if (datos.nivel !== undefined) {
    campos.push(`nivel_jerarquico = $${idx++}`);
    valores.push(entero(datos.nivel, "nivel", { min: 1 }));
  }
  if (datos.plantilla_declarada !== undefined) {
    campos.push(`plantilla_declarada = $${idx++}`);
    valores.push(entero(datos.plantilla_declarada, "plantilla_declarada", { min: 5 }));
  }
  if (datos.activa !== undefined) {
    campos.push(`activa = $${idx++}`);
    valores.push(booleano(datos.activa, "activa"));
  }

  if (!campos.length) return existentes;

  campos.push("fecha_actualizacion = NOW()");

  try {
    const queryPg = dbPg || consultarUno;
    const actualizada = await queryPg(
      `UPDATE organizacion.unidad_organizacional
          SET ${campos.join(", ")}
        WHERE unidad_organizacional_id = $1
        RETURNING ${COLS_UNIDAD}`,
      valores
    );

    if (req) {
      await registrarBitacora(req, "CATALOGO_MODIFICADO", "EXITO", {
        tipo_recurso: "unidad_organizacional",
        recurso_id: uId,
      });
    }

    return actualizada;
  } catch (err) {
    throw traducirErrorPg(err, "No se pudo actualizar la unidad organizacional.");
  }
}

export async function eliminarUnidadLogica(id, { req = null, dbPg = null } = {}) {
  const uId = texto(id, "id");
  const queryPg = dbPg || consultarUno;

  // Verificar dependencias subordinadas activas
  const hijas = await (dbPg || consultar)(
    `SELECT COUNT(*)::int AS total FROM organizacion.unidad_organizacional WHERE unidad_padre_id = $1 AND activa = true`,
    [uId]
  );
  if (hijas[0]?.total > 0) {
    throw new ErrorApi(
      "DEPENDENCIAS_ACTIVAS",
      `No se puede dar de baja la unidad '${uId}' porque tiene ${hijas[0].total} sub-area(s) activa(s) asignadas.`,
      409
    );
  }

  const desactivada = await queryPg(
    `UPDATE organizacion.unidad_organizacional
        SET activa = false, fecha_actualizacion = NOW()
      WHERE unidad_organizacional_id = $1
      RETURNING ${COLS_UNIDAD}`,
    [uId]
  );

  if (!desactivada) {
    throw new ErrorApi("UNIDAD_NO_ENCONTRADA", `No existe la unidad '${uId}'.`, 404);
  }

  if (req) {
    await registrarBitacora(req, "CATALOGO_MODIFICADO", "EXITO", {
      tipo_recurso: "unidad_organizacional",
      recurso_id: uId,
    });
  }

  return desactivada;
}
