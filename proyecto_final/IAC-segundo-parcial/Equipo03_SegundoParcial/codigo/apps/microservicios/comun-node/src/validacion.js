/**
 * Helpers de coercion y validacion estricta para peticiones HTTP (JSON o XML).
 *
 * En XML (via fast-xml-parser o cuerpoXml.js), todos los valores llegan como
 * cadenas de texto ("true", "4", "2026-01-01"). Estas funciones convierten
 * con seguridad al tipo esperado o lanzan ErrorApi 400 con el nombre exacto
 * del campo infractor, respetando el contrato de la API.
 */
import { ErrorApi } from "./errores.js";

export function entero(valor, campo, { requerido = true, min = undefined, max = undefined, defecto = undefined } = {}) {
  if (valor === undefined || valor === null || valor === "") {
    if (defecto !== undefined) return defecto;
    if (requerido) {
      throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' es obligatorio.`, 400, [
        { campo, problema: "campo_requerido" },
      ]);
    }
    return null;
  }
  const n = Number(valor);
  if (!Number.isInteger(n)) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe ser un numero entero.`, 400, [
      { campo, problema: "entero_invalido", valor_recibido: valor },
    ]);
  }
  if (min !== undefined && n < min) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe ser mayor o igual a ${min}.`, 400, [
      { campo, problema: "minimo_no_alcanzado", min, valor_recibido: n },
    ]);
  }
  if (max !== undefined && n > max) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe ser menor o igual a ${max}.`, 400, [
      { campo, problema: "maximo_excedido", max, valor_recibido: n },
    ]);
  }
  return n;
}

export function numero(valor, campo, { requerido = true, min = undefined, max = undefined, defecto = undefined } = {}) {
  if (valor === undefined || valor === null || valor === "") {
    if (defecto !== undefined) return defecto;
    if (requerido) {
      throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' es obligatorio.`, 400, [
        { campo, problema: "campo_requerido" },
      ]);
    }
    return null;
  }
  const n = Number(valor);
  if (!Number.isFinite(n)) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe ser un numero valido.`, 400, [
      { campo, problema: "numero_invalido", valor_recibido: valor },
    ]);
  }
  if (min !== undefined && n < min) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe ser mayor o igual a ${min}.`, 400, [
      { campo, problema: "minimo_no_alcanzado", min, valor_recibido: n },
    ]);
  }
  if (max !== undefined && n > max) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe ser menor o igual a ${max}.`, 400, [
      { campo, problema: "maximo_excedido", max, valor_recibido: n },
    ]);
  }
  return n;
}

export function booleano(valor, campo, { requerido = false, defecto = undefined } = {}) {
  if (valor === undefined || valor === null || valor === "") {
    if (defecto !== undefined) return defecto;
    if (requerido) {
      throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' es obligatorio.`, 400, [
        { campo, problema: "campo_requerido" },
      ]);
    }
    return false;
  }
  if (valor === true || valor === "true" || valor === 1 || valor === "1") return true;
  if (valor === false || valor === "false" || valor === 0 || valor === "0") return false;
  throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe ser booleano (true o false).`, 400, [
    { campo, problema: "booleano_invalido", valor_recibido: valor },
  ]);
}

export function texto(valor, campo, { requerido = true, minLong = 1, maxLong = 255, patron = null, defecto = undefined } = {}) {
  if (valor === undefined || valor === null || String(valor).trim() === "") {
    if (defecto !== undefined) return defecto;
    if (requerido) {
      throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' es obligatorio.`, 400, [
        { campo, problema: "campo_requerido" },
      ]);
    }
    return "";
  }
  const s = String(valor).trim();
  if (s.length < minLong) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe tener al menos ${minLong} caracter(es).`, 400, [
      { campo, problema: "longitud_minima", minLong, longitud: s.length },
    ]);
  }
  if (maxLong !== undefined && s.length > maxLong) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' excede el maximo de ${maxLong} caracteres.`, 400, [
      { campo, problema: "longitud_maxima", maxLong, longitud: s.length },
    ]);
  }
  if (patron && !patron.test(s)) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' no cumple el formato esperado.`, 400, [
      { campo, problema: "formato_invalido", valor_recibido: s },
    ]);
  }
  return s;
}

export function arreglo(valor, campo, { requerido = true, minElementos = 0 } = {}) {
  if (valor === undefined || valor === null) {
    if (requerido) {
      throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' es obligatorio.`, 400, [
        { campo, problema: "campo_requerido" },
      ]);
    }
    return [];
  }
  // En XML, un solo hijo suele parsearse como objeto en vez de arreglo
  const arr = Array.isArray(valor) ? valor : [valor];
  if (arr.length < minElementos) {
    throw new ErrorApi("PETICION_INVALIDA", `El campo '${campo}' debe contener al menos ${minElementos} elemento(s).`, 400, [
      { campo, problema: "elementos_insuficientes", minElementos, total: arr.length },
    ]);
  }
  return arr;
}
