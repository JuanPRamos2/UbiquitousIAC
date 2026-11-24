/**
 * Variables de ambiente, con los MISMOS nombres que usan el sistema web y
 * los microservicios en Python.
 *
 * Esto no es un detalle cosmetico: los ocho microservicios se levantan con
 * un solo archivo de ambiente (infra/ambientes/<ambiente>.env). Si cada
 * servicio inventara sus propios nombres de variable, ese archivo tendria
 * que declarar la misma contrasena cuatro veces con cuatro nombres
 * distintos, y bastaria con olvidar uno para que un servicio se conectara
 * a la base equivocada.
 */

export const ambiente = process.env.APP_AMBIENTE || "developer";
export const esDeveloper = ambiente === "developer";

export const postgres = {
  host: process.env.PG_HOST || "datos",
  port: Number(process.env.PG_PUERTO || 5432),
  database: process.env.PG_BASE || "bienestar",
  // El rol de aplicacion, NUNCA el superusuario: el principio de privilegio
  // minimo del primer parcial sigue vigente en el segundo.
  user: process.env.PG_USUARIO || "bienestar_app",
  password: process.env.PG_CLAVE || "",
  max: Number(process.env.PG_POOL_MAX || 5),
};

export const redis = {
  host: process.env.REDIS_HOST || "cache",
  port: Number(process.env.REDIS_PUERTO || 6379),
};

export const mongo = {
  uri: process.env.MONGO_URI || "mongodb://documentos:27017",
  base: process.env.MONGO_BASE || "bienestar",
};

export const jwt = {
  // El mismo secreto que el sistema web y que auth-service: por eso un
  // token emitido en cualquiera de ellos sirve en los demas.
  secreto: process.env.JWT_SECRETO || (esDeveloper ? "secreto-solo-para-developer" : null),
  algoritmo: "HS256",
};

export const nivelBitacora = (process.env.NIVEL_BITACORA || "INFO").toUpperCase();
export const mostrarErrores = process.env.MOSTRAR_ERRORES === "true";
export const cacheTtlSeg = Number(process.env.CATALOGO_CACHE_TTL_SEG || 300);
