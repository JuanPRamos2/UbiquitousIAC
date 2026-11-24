/**
 * Serializacion dual JSON/XML de catalog-service.
 *
 * Delega en comun/servicio.js para que las reglas de conversion sean las
 * MISMAS que usan los servicios en Python: lista envuelta en plural con
 * hijos en singular, null con xsi:nil y el namespace
 * http://nexum.com.mx/bienestar/v1.
 *
 * POR QUE HAY UNA CAPA DE ADAPTACION AQUI
 * ---------------------------------------
 * La capa de datos de este servicio devuelve { rows, total, page, limit,
 * totalPages }. El resto del proyecto responde { <plural>: [...],
 * paginacion: { pagina, tamano, total, total_paginas, tiene_siguiente,
 * tiene_anterior } }. Dejar las dos formas conviviendo tendria dos costos
 * concretos: ningun XSD podria describir las respuestas de los ocho
 * servicios a la vez, y el cliente del sistema web necesitaria dos
 * lectores de paginacion segun a quien le pregunte.
 *
 * Se adapta aqui, en la frontera, y no en la capa de datos: asi el modelo
 * y los servicios se quedan como los entrego el Integrante 2 y la forma
 * publica es la del equipo.
 */
import { responder } from "@bienestar/comun/servicio.js";
export { quiereXml as solicitaXml } from "@bienestar/comun/errores.js";
export { aXml as generarXml } from "@bienestar/comun/xmlizar.js";

/** Forma de paginacion del proyecto, a partir de la que devuelve la capa de datos. */
function paginacionDe(resultado) {
  const pagina = Number(resultado.page) || 1;
  const tamano = Number(resultado.limit) || 10;
  const total = Number(resultado.total) || 0;
  const totalPaginas = Number(resultado.totalPages) || Math.max(1, Math.ceil(total / tamano));
  return {
    pagina,
    tamano,
    total,
    total_paginas: totalPaginas,
    tiene_siguiente: pagina < totalPaginas,
    tiene_anterior: pagina > 1,
  };
}

/**
 * Respuesta de un listado.
 *
 * `plural` nombra la coleccion ("unidades") y da el elemento raiz
 * ("unidades_respuesta"), que es el que declara contratos/xml/catalogos.xsd.
 */
export function responderLista(req, res, plural, resultado,
                               { status = 200, raiz = null } = {}) {
  const cuerpo = {
    [plural]: resultado.rows || resultado[plural] || [],
    paginacion: paginacionDe(resultado),
  };
  // Se informa si la respuesta salio de Redis. Es lo que permite demostrar
  // la cache en la revision sin entrar al servidor.
  if (resultado._cache) {
    cuerpo.desde_cache = resultado._cache === "HIT";
    res.set("X-Cache", resultado._cache === "HIT" ? "ACIERTO" : "FALLO");
  }
  return responder(req, res, cuerpo,
                   { http: status, raiz: raiz || `${plural}_respuesta` });
}

/** Respuesta de una entidad sola: alta, consulta por id, cambio o baja logica. */
export function responderUno(req, res, singular, entidad, { status = 200, extra = {} } = {}) {
  return responder(req, res, { [singular]: entidad, ...extra },
                   { http: status, raiz: `${singular}_respuesta` });
}

/** Respuesta libre, para los catalogos de apoyo que no son ni lista paginada ni entidad. */
export function responderCatalogo(req, res, datos, { rootTag = "catalogo", status = 200 } = {}) {
  return responder(req, res, datos, { http: status, raiz: rootTag });
}
