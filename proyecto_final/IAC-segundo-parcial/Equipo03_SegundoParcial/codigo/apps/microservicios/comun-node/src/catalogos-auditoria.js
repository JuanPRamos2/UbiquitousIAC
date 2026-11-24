/**
 * Codigos del modelo RBAC dirigido por datos del primer parcial.
 *
 * Se declaran aqui como constantes para que un error de dedo en el nombre
 * de un permiso falle de inmediato y no en produccion con un 403
 * inexplicable. La fuente de verdad sigue siendo la tabla
 * usuarios.permiso; estas constantes solo le ponen nombre a sus codigos.
 *
 * POR QUE UN PROXY Y NO SOLO Object.freeze
 * ----------------------------------------
 * Object.freeze impide CAMBIAR una clave, pero leer una que no existe
 * devuelve undefined sin decir nada. Eso ya costo un error real: la
 * migracion 004 agrego UNIDAD_ADMIN, APOYO_SOLICITAR y APOYO_ATENDER a la
 * base, aqui no se agregaron, y `autorizar(PERMISOS.APOYO_ATENDER)` quedo
 * llamandose con undefined. El efecto era un 403 para todo el mundo en la
 * ruta de solicitudes de apoyo, incluido el perfil que si tenia el
 * permiso, y nada en los registros apuntaba a la causa.
 *
 * Con el proxy, leer un codigo que no existe lanza en el momento en que se
 * monta la ruta: el servicio no arranca en lugar de arrancar mintiendo.
 */

function conClavesEstrictas(nombre, objeto) {
  return new Proxy(Object.freeze(objeto), {
    get(destino, clave) {
      if (typeof clave === "string" && !(clave in destino)) {
        throw new Error(
          `${nombre}.${clave} no existe. Codigos validos: ` +
          `${Object.keys(destino).sort().join(", ")}. Si el codigo es nuevo en ` +
          `la base de datos, agregalo tambien a comun-node/src/catalogos-auditoria.js.`);
      }
      return destino[clave];
    },
  });
}

export const PERFILES = conClavesEstrictas("PERFILES", {
  COLABORADOR: "COLABORADOR",
  LIDER: "LIDER",
  ESPECIALISTA: "ESPECIALISTA",
  AUDITOR: "AUDITOR",
  ADMINISTRADOR: "ADMINISTRADOR",
});

export const PERMISOS = conClavesEstrictas("PERMISOS", {
  AVISO_CONSULTAR: "AVISO_CONSULTAR",
  CONSENT_OTORGAR: "CONSENT_OTORGAR",
  CONSENT_REVOCAR: "CONSENT_REVOCAR",
  CONSENT_HISTORIAL_PROPIO: "CONSENT_HISTORIAL_PROPIO",
  CONSENT_EVIDENCIA_AUDIT: "CONSENT_EVIDENCIA_AUDIT",
  AUTOREPORTE_RESPONDER: "AUTOREPORTE_RESPONDER",
  PARTICIPACION_PROPIA: "PARTICIPACION_PROPIA",
  AGREGADO_UNIDAD: "AGREGADO_UNIDAD",
  AGREGADO_GLOBAL: "AGREGADO_GLOBAL",
  TENDENCIA_CONSULTAR: "TENDENCIA_CONSULTAR",
  RECOMENDACION_CONSULTAR: "RECOMENDACION_CONSULTAR",
  INSTRUMENTO_ADMIN: "INSTRUMENTO_ADMIN",
  CAMPANIA_ADMIN: "CAMPANIA_ADMIN",
  INTERVENCION_PROPONER: "INTERVENCION_PROPONER",
  INTERVENCION_APROBAR: "INTERVENCION_APROBAR",
  INTERVENCION_SEGUIMIENTO: "INTERVENCION_SEGUIMIENTO",
  BITACORA_CONSULTAR: "BITACORA_CONSULTAR",
  USUARIO_ADMIN: "USUARIO_ADMIN",
  PARAMETRO_ADMIN: "PARAMETRO_ADMIN",
  // Agregados por la migracion 004.
  UNIDAD_ADMIN: "UNIDAD_ADMIN",
  APOYO_SOLICITAR: "APOYO_SOLICITAR",
  APOYO_ATENDER: "APOYO_ATENDER",
});

/** Acciones de auditoria.tipo_accion que emiten los microservicios. */
export const ACCIONES = conClavesEstrictas("ACCIONES", {
  ACCESO_DENEGADO: "ACCESO_DENEGADO",
  CATALOGO_MODIFICADO: "CATALOGO_MODIFICADO",
  AUTOREPORTE_ENVIADO: "AUTOREPORTE_ENVIADO",
  // Agregadas por la migracion 005.
  REPORTE_GENERADO: "REPORTE_GENERADO",
  REPORTE_DESCARGADO: "REPORTE_DESCARGADO",
  REPORTE_VERIFICADO: "REPORTE_VERIFICADO",
  EVIDENCIA_CARGADA: "EVIDENCIA_CARGADA",
  EVIDENCIA_DESCARGADA: "EVIDENCIA_DESCARGADA",
  NOTIFICACION_LEIDA: "NOTIFICACION_LEIDA",
});
