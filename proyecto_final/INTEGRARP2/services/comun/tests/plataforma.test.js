import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import jwt from "jsonwebtoken";
import { crearCache, crearContador } from "../src/cache.js";
import { CATALOGO_CLAVES } from "../src/claves-redis.js";
import { envelopeError, HttpError } from "../src/errores.js";
import { crearAutenticacion } from "../src/jwt.js";
import { crearLogger } from "../src/logger.js";
import { leerOrden, leerPaginacion, paginar } from "../src/paginacion.js";
import { alcanceUnidad } from "../src/perfiles.js";
import { crearRateLimit } from "../src/rate-limit.js";
import { aXml } from "../src/xml.js";
import { directorioXsd, validarXmlContraXsd } from "../src/xsd.js";
import { crearRedisFalso } from "./fake-redis.js";

const cfg = {
  jwtSecret: "secreto-de-prueba",
  jwtAlgorithm: "HS256",
  jwtIssuer: "",
  jwtAudience: "",
  jwtPublicKey: "",
  requireSession: true,
  contextoTtl: 60,
  cacheTtl: 30,
  lockTtl: 5,
  rateLimit: 2,
  rateWindow: 60,
  serviceName: "queries-service",
};

function token(extra = {}, opciones = {}) {
  return jwt.sign(
    { sub: "USR-00003", perfil: "ESPECIALISTA", jti: "jti-prueba", ...extra },
    cfg.jwtSecret,
    { expiresIn: 60, ...opciones }
  );
}

test("la paginación rechaza page y limit inválidos y calcula el total de páginas", () => {
  assert.throws(() => leerPaginacion({ page: "0" }), (err) => err.status === 400);
  assert.throws(() => leerPaginacion({ limit: "101" }), (err) => err.status === 400);
  assert.throws(() => leerPaginacion({ page: "abc" }), (err) => err.status === 400);
  const ok = leerPaginacion({ page: "2", limit: "20" });
  assert.deepEqual(ok, { page: 2, limit: 20, offset: 20 });
  assert.deepEqual(paginar(1, 20, 0), { page: 1, limit: 20, total: 0, totalPages: 0 });
  assert.equal(paginar(1, 20, 41).totalPages, 3);
  assert.throws(() => leerOrden({ sort: "drop table" }, { nombre: "c.nombre" }, "nombre"), (err) => err.status === 400);
});

test("el alcance del líder no permite otra unidad", () => {
  const lider = { perfil: "LIDER", unidad_organizacional_id: "UO-CC-TURNO-B" };
  assert.equal(alcanceUnidad(lider, null, HttpError), "UO-CC-TURNO-B");
  assert.throws(() => alcanceUnidad(lider, "UO-LOG-TURNO-A", HttpError), (err) => err.status === 403);
  assert.equal(alcanceUnidad({ perfil: "ESPECIALISTA" }, "UO-LOG-TURNO-A", HttpError), "UO-LOG-TURNO-A");
});

test("el XML de campañas válidas pasa el XSD y el inválido falla", () => {
  const envelope = {
    success: true,
    message: "Campañas consultadas",
    data: {
      campanias: [
        {
          campania_id: "CAMP-2026-S4",
          nombre: "Medicion semana 4",
          estado: "ABIERTA",
          fecha_inicio: "2026-08-24",
          fecha_fin: "2026-08-28",
          secuencia: 4,
          instrumento_id: "INST-BIENESTAR",
          version_instrumento: 1,
          activa: true,
        },
      ],
    },
    pagination: { page: 1, limit: 20, total: 4, totalPages: 1 },
    meta: { cache: "MISS", servicio: "queries-service", correlacion_id: "abc", clave_cache: "cache:queries:campanias:abc" },
  };
  const xsd = readFileSync(path.join(directorioXsd(), "consulta-campanias.xsd"), "utf8");
  const xml = aXml(envelope);
  assert.match(xml, /<campania>/);
  assert.equal(validarXmlContraXsd(xml, xsd).valido, true);

  const roto = xml.replace("<estado>ABIERTA</estado>", "<estado>DESCONOCIDO</estado>");
  const invalido = validarXmlContraXsd(roto, xsd);
  assert.equal(invalido.valido, false);

  const errorXsd = readFileSync(path.join(directorioXsd(), "envelope-error.xsd"), "utf8");
  const errorXml = aXml(envelopeError(new HttpError(404, "NO_ENCONTRADO", "La campaña no existe", { campo: "campania_id" })));
  assert.equal(validarXmlContraXsd(errorXml, errorXsd).valido, true);
  const errorRoto = errorXml.replace("<code>NO_ENCONTRADO</code>", "");
  assert.equal(validarXmlContraXsd(errorRoto, errorXsd).valido, false);
});

test("la búsqueda XML válida pasa y un estado fuera de catálogo falla", () => {
  const xsd = readFileSync(path.join(directorioXsd(), "busqueda-campanias.xsd"), "utf8");
  const valido = `<?xml version="1.0" encoding="UTF-8"?><busqueda><estado>ABIERTA</estado><page>1</page><limit>20</limit></busqueda>`;
  assert.equal(validarXmlContraXsd(valido, xsd).valido, true);
  const invalido = valido.replace("ABIERTA", "OTRA");
  assert.equal(validarXmlContraXsd(invalido, xsd).valido, false);
  const pagina = valido.replace("<page>1</page>", "<page>0</page>");
  assert.equal(validarXmlContraXsd(pagina, xsd).valido, false);
});

test("el reporte Highcharts en XML cumple su XSD", () => {
  const xsd = readFileSync(path.join(directorioXsd(), "reporte-highcharts.xsd"), "utf8");
  const xml = aXml({
    success: true,
    message: "Distribución de campañas",
    data: {
      categories: ["ABIERTA", "CERRADA"],
      series: [{ name: "Campañas", data: [1, null] }],
      nota: "Ejemplo",
    },
    meta: { cache: "HIT", servicio: "reports-service" },
  });
  const resultado = validarXmlContraXsd(xml, xsd);
  assert.equal(resultado.valido, true, resultado.errores.join("; "));
  const tendencia = readFileSync(path.join(directorioXsd(), "reporte-tendencia.xsd"), "utf8");
  assert.equal(
    validarXmlContraXsd(
      `<?xml version="1.0"?><reporte><unidad_organizacional_id>UO-CC-TURNO-B</unidad_organizacional_id></reporte>`,
      tendencia
    ).valido,
    true
  );
});

test("la caché distingue miss y hit y guarda con TTL", async () => {
  const redis = crearRedisFalso();
  const eventos = [];
  const log = { info(msg, extra) { eventos.push(msg); }, warn() {}, error() {} };
  const cache = crearCache({ redis, cfg, log });
  let calculos = 0;
  const primero = await cache.obtener("campanias", { page: 1 }, async () => {
    calculos += 1;
    return { filas: [1] };
  });
  const segundo = await cache.obtener("campanias", { page: 1 }, async () => {
    calculos += 1;
    return { filas: [2] };
  });
  assert.equal(primero.cache, "MISS");
  assert.equal(segundo.cache, "HIT");
  assert.equal(calculos, 1);
  assert.deepEqual(eventos.filter((item) => item.startsWith("CACHE")), ["CACHE MISS", "CACHE HIT"]);
  assert.ok((await redis.ttl(primero.clave)) > 0);
});

test("el rate limit responde 429 y si Redis falla responde 503", async () => {
  const redis = crearRedisFalso();
  const limitar = crearRateLimit({ redis, cfg, log: crearLogger("test") });
  const req = { actor: { usuario_id: "USR-00003" }, ip: "127.0.0.1" };
  const cabeceras = {};
  const res = { setHeader(nombre, valor) { cabeceras[nombre] = valor; } };
  await limitar(req, res, (err) => assert.equal(err, undefined));
  await limitar(req, res, (err) => assert.equal(err, undefined));
  await limitar(req, res, (err) => {
    assert.equal(err.status, 429);
    assert.equal(err.code, "LIMITE_EXCEDIDO");
  });

  const roto = crearRateLimit({
    redis: { async incr() { throw new Error("redis down"); }, async ttl() { return -1; }, async expire() {} },
    cfg,
    log: { info() {}, warn() {}, error() {} },
  });
  await roto(req, res, (err) => assert.equal(err.status, 503));
});

test("el JWT acepta una sesión vigente y rechaza ausencia, firma, expiración, revocación y rol", async () => {
  const redis = crearRedisFalso();
  await redis.set("session:jti-prueba", "1");
  const autenticar = crearAutenticacion({
    redis,
    query: async () => ({ rows: [{ unidad_organizacional_id: "UO-CC-TURNO-B" }] }),
    cfg,
    log: { info() {}, warn() {}, error() {} },
  });

  const req = { headers: { authorization: `Bearer ${token()}` }, path: "/campanias" };
  await autenticar(req, {}, (err) => assert.equal(err, undefined));
  assert.equal(req.actor.perfil, "ESPECIALISTA");
  assert.equal(req.actor.unidad_organizacional_id, "UO-CC-TURNO-B");

  await autenticar({ headers: {}, path: "/" }, {}, (err) => assert.equal(err.code, "SIN_TOKEN"));
  await autenticar({ headers: { authorization: "Bearer no-es-jwt" }, path: "/" }, {}, (err) => assert.equal(err.code, "TOKEN_INVALIDO"));
  await autenticar(
    { headers: { authorization: `Bearer ${token({}, { expiresIn: -10 })}` }, path: "/" },
    {},
    (err) => assert.equal(err.code, "TOKEN_EXPIRADO")
  );

  await redis.set("revoked:jti-malo", "1");
  await autenticar(
    { headers: { authorization: `Bearer ${token({ jti: "jti-malo" })}` }, path: "/" },
    {},
    (err) => assert.equal(err.code, "TOKEN_REVOCADO")
  );
  await autenticar(
    { headers: { authorization: `Bearer ${token({ jti: "sin-sesion" })}` }, path: "/" },
    {},
    (err) => assert.equal(err.code, "SESION_INVALIDA")
  );
});

test("el catálogo de Redis documenta patrón, TTL y responsable", () => {
  for (const clave of CATALOGO_CLAVES) {
    assert.ok(clave.patron);
    assert.ok(clave.ttl);
    assert.ok(clave.componente);
    assert.ok(clave.proposito);
    assert.ok(clave.tipo);
  }
  assert.ok(CATALOGO_CLAVES.some((clave) => clave.patron === "revoked:{jti}"));
  assert.ok(CATALOGO_CLAVES.some((clave) => clave.patron.startsWith("lock:cache:")));
});

test("el logger no escribe secretos", () => {
  const lineas = [];
  const original = console.log;
  console.log = (linea) => lineas.push(linea);
  try {
    crearLogger("queries-service").info("inicio", { password: "demo123", token: "abc.def.ghi", usuario_id: "USR-00001" });
  } finally {
    console.log = original;
  }
  assert.match(lineas[0], /omitido/);
  assert.doesNotMatch(lineas[0], /demo123/);
  assert.doesNotMatch(lineas[0], /abc\.def\.ghi/);
});

test("el contador diario recibe TTL y el total no", async () => {
  const redis = crearRedisFalso();
  const contador = crearContador({ redis, log: { warn() {} }, operacion: "queries:consultas", ttlDiario: 100 });
  await contador.incrementar();
  const lectura = await contador.leer();
  assert.equal(lectura.valor, 1);
  assert.equal(lectura.ttl, -1);
  const dia = new Date().toISOString().slice(0, 10);
  assert.ok((await redis.ttl(`counter:queries:consultas:${dia}`)) > 0);
});
