import { createHash } from "node:crypto";
import { HttpError } from "./errores.js";

export function leerPaginacion(origen) {
  const page = origen.page === undefined || origen.page === "" ? 1 : Number(origen.page);
  const limit = origen.limit === undefined || origen.limit === "" ? 20 : Number(origen.limit);
  if (!Number.isInteger(page) || page < 1) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", "page debe ser un entero mayor o igual a 1", {
      campo: "page",
    });
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", "limit debe ser un entero entre 1 y 100", {
      campo: "limit",
    });
  }
  return { page, limit, offset: (page - 1) * limit };
}

export function paginar(page, limit, total) {
  return {
    page,
    limit,
    total,
    totalPages: total === 0 ? 0 : Math.ceil(total / limit),
  };
}

export function leerOrden(origen, permitidos, defecto) {
  const sort = origen.sort === undefined || origen.sort === "" ? defecto : String(origen.sort);
  if (!Object.prototype.hasOwnProperty.call(permitidos, sort)) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", "sort no está permitido", {
      campo: "sort",
      permitidos: Object.keys(permitidos),
    });
  }
  const order = origen.order === undefined || origen.order === "" ? "desc" : String(origen.order).toLowerCase();
  if (order !== "asc" && order !== "desc") {
    throw new HttpError(400, "PARAMETRO_INVALIDO", "order debe ser asc o desc", { campo: "order" });
  }
  return { sort, columna: permitidos[sort], order: order.toUpperCase() };
}

export function leerEnumeracion(valor, nombre, permitidos) {
  if (valor === undefined || valor === null || valor === "") return null;
  const texto = String(valor);
  if (!permitidos.includes(texto)) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", `${nombre} no está permitido`, {
      campo: nombre,
      permitidos,
    });
  }
  return texto;
}

export function leerTexto(valor, nombre, max = 120) {
  if (valor === undefined || valor === null || valor === "") return null;
  const texto = String(valor).trim();
  if (texto.length > max) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", `${nombre} supera ${max} caracteres`, { campo: nombre });
  }
  return texto;
}

export function leerId(valor, nombre, { requerido = false } = {}) {
  if (valor === undefined || valor === null || valor === "") {
    if (requerido) {
      throw new HttpError(400, "PARAMETRO_INVALIDO", `${nombre} es obligatorio`, { campo: nombre });
    }
    return null;
  }
  const texto = String(valor);
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/.test(texto)) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", `${nombre} tiene un formato inválido`, { campo: nombre });
  }
  return texto;
}

export function leerEnteroId(valor, nombre) {
  const texto = String(valor ?? "");
  if (!/^\d{1,18}$/.test(texto)) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", `${nombre} debe ser un entero positivo`, { campo: nombre });
  }
  return texto;
}

export function leerFecha(valor, nombre) {
  if (valor === undefined || valor === null || valor === "") return null;
  const texto = String(valor);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(texto) || Number.isNaN(Date.parse(`${texto}T00:00:00Z`))) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", `${nombre} debe tener formato YYYY-MM-DD`, { campo: nombre });
  }
  return texto;
}

export function exigirRango(desde, hasta) {
  if (desde && hasta && desde > hasta) {
    throw new HttpError(422, "RANGO_INVALIDO", "desde no puede ser posterior a hasta", { desde, hasta });
  }
}

export function leerBooleano(valor, nombre) {
  if (valor === undefined || valor === null || valor === "") return null;
  if (valor === true || valor === "true") return true;
  if (valor === false || valor === "false") return false;
  throw new HttpError(400, "PARAMETRO_INVALIDO", `${nombre} debe ser true o false`, { campo: nombre });
}

export function comoPatronLike(texto) {
  return `%${texto.replace(/[\\%_]/g, "\\$&")}%`;
}

export function hashEstable(valor) {
  return createHash("sha256").update(JSON.stringify(valor)).digest("hex").slice(0, 24);
}
