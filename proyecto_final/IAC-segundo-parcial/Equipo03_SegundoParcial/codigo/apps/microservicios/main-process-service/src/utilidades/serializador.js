/**
 * Serializacion dual JSON/XML de main-process-service.
 * Delega en comun para que las reglas sean las mismas que en los otros
 * siete microservicios y un solo XSD las describa.
 */
import { responder } from "@bienestar/comun/servicio.js";
export { quiereXml as solicitaXml } from "@bienestar/comun/errores.js";
export { aXml as generarXml } from "@bienestar/comun/xmlizar.js";

export function responderProceso(req, res, datos, { rootTag = "proceso", status = 200 } = {}) {
  return responder(req, res, datos, { http: status, raiz: rootTag });
}
