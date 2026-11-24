/**
 * Fabrica comun de microservicios en Node, equivalente a comun/servicio.py.
 *
 * Todo servicio obtiene de aqui, sin volver a escribirlo: correlacion,
 * registro de actividad, los tres endpoints de salud que pide la rubrica,
 * manejo estandarizado de errores, respuesta dual JSON/XML, paginacion
 * validada y limite de consumo apoyado en Redis.
 *
 * Lo que NO esta aqui es la logica de negocio: cada servicio tiene una
 * sola responsabilidad y la implementa en su propio archivo.
 */
import cors from "cors";
import express from "express";
import helmet from "helmet";

import { correlacion } from "./correlacion.js";
import { cuerpoXml } from "./cuerpoXml.js";
import { ErrorApi, quiereXml, registrarManejadores } from "./errores.js";
import { ambiente, nivelBitacora } from "./entorno.js";
import { obtenerRedis } from "./redis.js";
import { aXml } from "./xmlizar.js";

export const VERSION_API = "v1";

const NIVELES = { DEBUG: 10, INFO: 20, WARN: 30, ERROR: 40 };

function crearBitacora(nombre) {
  const minimo = NIVELES[nivelBitacora] ?? NIVELES.INFO;
  const emitir = (nivel, ...a) => {
    if (NIVELES[nivel] < minimo) return;
    const linea = `${new Date().toISOString()} ${nivel} [${nombre}/${ambiente}]`;
    (nivel === "ERROR" ? console.error : console.log)(linea, ...a);
  };
  return {
    debug: (...a) => emitir("DEBUG", ...a),
    info: (...a) => emitir("INFO", ...a),
    warn: (...a) => emitir("WARN", ...a),
    error: (...a) => emitir("ERROR", ...a),
  };
}

/** Devuelve el mismo contenido en JSON o en XML, segun lo pedido. */
export function responder(req, res, datos, { http = 200, raiz = "respuesta" } = {}) {
  if (quiereXml(req)) {
    res.status(http).type("application/xml; charset=utf-8");
    return res.send(aXml(datos, raiz));
  }
  return res.status(http).json(datos);
}

/**
 * Lee y valida los parametros de paginacion.
 * El tope de 100 por pagina no es decorativo: sin el, un cliente podria
 * pedir un millon de registros y tumbar el servicio con una sola peticion.
 */
export function pagina(req) {
  const crudoP = req.query.pagina ?? req.query.page ?? 1;
  const crudoT = req.query.tamano ?? req.query.limit ?? 20;
  const p = Number(crudoP);
  const t = Number(crudoT);
  if (!Number.isInteger(p) || !Number.isInteger(t)) {
    throw new ErrorApi("PARAMETRO_INVALIDO",
      "Los parametros 'pagina' y 'tamano' deben ser enteros.", 400);
  }
  if (p < 1) throw new ErrorApi("PARAMETRO_INVALIDO", "'pagina' empieza en 1.", 400);
  if (t < 1 || t > 100) {
    throw new ErrorApi("PARAMETRO_INVALIDO", "'tamano' debe estar entre 1 y 100.", 400);
  }
  return { p, t };
}

/** Sobre de paginacion comun a todos los listados de los ocho servicios. */
export function sobrePagina(elementos, total, p, t, clave = "elementos") {
  const totalPaginas = Math.max(1, Math.ceil(total / t));
  return {
    [clave]: elementos,
    paginacion: {
      pagina: p, tamano: t, total,
      total_paginas: totalPaginas,
      tiene_siguiente: p < totalPaginas,
      tiene_anterior: p > 1,
    },
  };
}

/**
 * Limite de peticiones por token y minuto, con contador en Redis.
 * Si Redis no responde se deja pasar: el limite protege de un abuso, no de
 * un ataque, y perder el limite es preferible a negar servicio a todos los
 * clientes legitimos por una caida de la cache.
 */
export function limiteConsumo(maximo = 120, ventana = 60) {
  return async function (req, res, next) {
    try {
      const actor = req.actor?.jti || req.ip;
      const clave = `limite:${req.baseUrl || "api"}:${actor}`;
      const r = obtenerRedis();
      const n = await r.incr(clave);
      if (n === 1) await r.expire(clave, ventana);
      if (n > maximo) {
        return next(new ErrorApi("LIMITE_EXCEDIDO",
          `Mas de ${maximo} peticiones por ${ventana} segundos.`, 429));
      }
    } catch { /* cache caida: se deja pasar a proposito */ }
    next();
  };
}

/** Envuelve un controlador async para que sus rechazos lleguen al manejador. */
export function asinc(fn) {
  return (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
}

/**
 * crearServicio(nombre, descripcion, comprobaciones)
 *   comprobaciones: objeto etiqueta -> funcion async que lanza si falla.
 * Devuelve { app, bitacora, montar } donde montar(ruta, router) registra
 * las rutas ANTES de los manejadores de error, en el orden que Express exige.
 */
export function crearServicio(nombre, descripcion, comprobaciones = {}) {
  const app = express();
  const bitacora = crearBitacora(nombre);
  app.disable("x-powered-by");
  app.set("etag", false);

  app.use(helmet());
  app.use(cors());
  // El lector de XML va ANTES del de JSON y solo actua cuando el
  // Content-Type es XML: sin el, una peticion en XML llegaba con req.body
  // vacio y el servicio respondia 422 por campos obligatorios que el
  // cliente SI habia mandado.
  app.use(cuerpoXml(262144));
  app.use(express.json({ limit: "256kb" }));
  app.use(correlacion);

  app.use((req, res, next) => {
    const inicio = process.hrtime.bigint();
    res.setHeader("X-Servicio", nombre);
    res.setHeader("X-Version-Api", VERSION_API);
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.on("finish", () => {
      if (req.path.startsWith("/health")) return;
      const ms = Number(process.hrtime.bigint() - inicio) / 1e6;
      bitacora.info(
        `${req.method} ${req.originalUrl} -> ${res.statusCode} en ${ms.toFixed(1)} ms ` +
        `[corr=${req.correlacionId}]`);
    });
    next();
  });

  // ----------------------------------------------- endpoints de salud
  app.get("/health/live", (req, res) => {
    res.json({ servicio: nombre, estado: "vivo", version: VERSION_API });
  });

  app.get("/health/ready", async (req, res) => {
    const detalle = {};
    let ok = true;
    for (const [etiqueta, fn] of Object.entries(comprobaciones)) {
      const t = process.hrtime.bigint();
      try {
        await fn();
        detalle[etiqueta] = { ok: true, ms: Number(process.hrtime.bigint() - t) / 1e6 };
      } catch (e) {
        ok = false;
        detalle[etiqueta] = { ok: false, error: String(e?.message || e).slice(0, 200) };
      }
    }
    res.status(ok ? 200 : 503).json({
      servicio: nombre, estado: ok ? "listo" : "no_listo", dependencias: detalle,
    });
  });

  app.get("/health", (req, res) => {
    res.json({ servicio: nombre, descripcion, version: VERSION_API, ambiente });
  });

  const montar = (ruta, router) => app.use(ruta, router);
  const finalizar = () => registrarManejadores(app, bitacora);

  return { app, bitacora, montar, finalizar };
}
