import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import jwt from "jsonwebtoken";
import Redis from "ioredis";
import { MongoClient } from "mongodb";

const activo = process.env.INTEGRACION === "1";
const secreto = process.env.JWT_SECRET || "cambia-esta-clave-en-produccion";
const queries = process.env.QUERIES_URL || "http://127.0.0.1:3010";
const reports = process.env.REPORTS_URL || "http://127.0.0.1:3020";
const redisUrl = process.env.REDIS_URL_TEST || "redis://127.0.0.1:6379";
const mongoUrl = process.env.MONGO_URL_TEST || "mongodb://127.0.0.1:27017";

let redis;
let mongo;

function firmar(perfil, usuario, jti) {
  return jwt.sign({ sub: usuario, perfil, jti }, secreto, { expiresIn: 120 });
}

async function sesion(jti) {
  await redis.set(`session:${jti}`, "1", "EX", 120);
}

async function pedir(base, ruta, { token, accept = "application/json", method = "GET", body, contentType } = {}) {
  const headers = { Accept: accept };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (contentType) headers["Content-Type"] = contentType;
  const respuesta = await fetch(`${base}${ruta}`, { method, headers, body });
  const texto = await respuesta.text();
  let json = null;
  if (respuesta.headers.get("content-type")?.includes("json")) {
    json = JSON.parse(texto);
  }
  return { status: respuesta.status, texto, json, headers: respuesta.headers };
}

before(async () => {
  if (!activo) return;
  redis = new Redis(redisUrl, { maxRetriesPerRequest: 1, connectTimeout: 3000 });
  await redis.ping();
  mongo = new MongoClient(mongoUrl, { serverSelectionTimeoutMS: 3000 });
  await mongo.connect();
});

after(async () => {
  if (redis) await redis.quit().catch(() => {});
  if (mongo) await mongo.close().catch(() => {});
});

test("salud, JSON, XML, caché, 401, 403, 404 y 400", { skip: !activo }, async () => {
  const salud = await pedir(queries, "/health");
  assert.equal(salud.status, 200);
  assert.equal(salud.json.dependencies.postgres, "up");
  assert.equal(salud.json.dependencies.redis, "up");
  assert.equal(salud.json.dependencies.mongo, "up");

  const jti = `it-esp-${Date.now()}`;
  const token = firmar("ESPECIALISTA", "USR-00003", jti);
  await sesion(jti);

  const sinToken = await pedir(queries, "/api/v1/queries/campanias");
  assert.equal(sinToken.status, 401);
  assert.equal(sinToken.json.error.code, "SIN_TOKEN");

  const malo = await pedir(queries, "/api/v1/queries/campanias", { token: "no-es-un-jwt" });
  assert.equal(malo.status, 401);

  const invalido = await pedir(queries, "/api/v1/queries/campanias?page=0", { token });
  assert.equal(invalido.status, 400);
  assert.equal(invalido.json.success, false);

  const primera = await pedir(queries, "/api/v1/queries/campanias?estado=ABIERTA&limit=5", { token });
  assert.equal(primera.status, 200);
  assert.equal(primera.json.success, true);
  assert.equal(primera.json.meta.cache, "MISS");
  assert.ok(primera.json.data.campanias.some((fila) => fila.campania_id === "CAMP-2026-S4"));
  assert.equal(primera.json.pagination.page, 1);
  const clave = primera.json.meta.clave_cache;
  assert.match(clave, /^cache:queries-service:campanias:/);
  assert.ok((await redis.ttl(clave)) > 0);

  const segunda = await pedir(queries, "/api/v1/queries/campanias?estado=ABIERTA&limit=5", { token });
  assert.equal(segunda.json.meta.cache, "HIT");

  const xml = await pedir(queries, "/api/v1/queries/campanias?estado=CERRADA&limit=5", {
    token,
    accept: "application/xml",
  });
  assert.equal(xml.status, 200);
  assert.match(xml.headers.get("content-type"), /application\/xml/);
  assert.match(xml.texto, /<campania>/);
  assert.match(xml.texto, /<success>true<\/success>/);

  const ausente = await pedir(queries, "/api/v1/queries/campanias/CAMP-NO-EXISTE", { token });
  assert.equal(ausente.status, 404);

  const formato = await pedir(queries, "/api/v1/queries/campanias/!!!", { token });
  assert.equal(formato.status, 400);

  const colaboradorJti = `it-col-${Date.now()}`;
  const colaborador = firmar("COLABORADOR", "USR-00001", colaboradorJti);
  await sesion(colaboradorJti);
  const prohibido = await pedir(queries, "/api/v1/queries/auditoria", { token: colaborador });
  assert.equal(prohibido.status, 403);
  assert.equal(prohibido.json.error.code, "RBAC");

  const auditorJti = `it-aud-${Date.now()}`;
  const auditor = firmar("AUDITOR", "USR-00004", auditorJti);
  await sesion(auditorJti);
  const bitacora = await pedir(queries, "/api/v1/queries/auditoria?limit=5", { token: auditor });
  assert.equal(bitacora.status, 200);
  assert.ok(bitacora.json.pagination.total >= 1);

  const busqueda = await pedir(queries, "/api/v1/queries/campanias/buscar", {
    token,
    method: "POST",
    contentType: "application/xml",
    accept: "application/xml",
    body: `<?xml version="1.0" encoding="UTF-8"?><busqueda><estado>ABIERTA</estado><page>1</page><limit>5</limit></busqueda>`,
  });
  assert.equal(busqueda.status, 200, busqueda.texto);
  assert.match(busqueda.texto, /<estado>ABIERTA<\/estado>/);

  const xmlRoto = await pedir(queries, "/api/v1/queries/campanias/buscar", {
    token,
    method: "POST",
    contentType: "application/xml",
    body: `<?xml version="1.0" encoding="UTF-8"?><busqueda><estado>OTRA</estado></busqueda>`,
  });
  assert.equal(xmlRoto.status, 422);

  const liderJti = `it-lid-${Date.now()}`;
  const lider = firmar("LIDER", "USR-00005", liderJti);
  await sesion(liderJti);
  const otraUnidad = await pedir(queries, "/api/v1/queries/intervenciones?unidad_organizacional_id=UO-LOG-TURNO-A", {
    token: lider,
  });
  assert.equal(otraUnidad.status, 403);

  const revocadoJti = `it-rev-${Date.now()}`;
  const revocado = firmar("ESPECIALISTA", "USR-00003", revocadoJti);
  await sesion(revocadoJti);
  await redis.set(`revoked:${revocadoJti}`, "1", "EX", 120);
  const bloqueado = await pedir(queries, "/api/v1/queries/campanias", { token: revocado });
  assert.equal(bloqueado.status, 401);
  assert.equal(bloqueado.json.error.code, "TOKEN_REVOCADO");

  const xsd = await pedir(queries, "/api/v1/xsd/consulta-campanias.xsd");
  assert.equal(xsd.status, 200);
  assert.match(xsd.texto, /xs:schema/);
});

test("reportes reales, XML y MongoDB", { skip: !activo }, async () => {
  const jti = `it-rep-${Date.now()}`;
  const token = firmar("ESPECIALISTA", "USR-00003", jti);
  await sesion(jti);
  const grafica = await pedir(reports, "/api/v1/reports/campanias-por-estado", { token });
  assert.equal(grafica.status, 200, grafica.texto);
  assert.ok(grafica.json.data.categories.includes("ABIERTA"));
  assert.ok(grafica.json.data.series[0].data.some((n) => n > 0));
  assert.equal(grafica.json.meta.cache, "MISS");
  const repetida = await pedir(reports, "/api/v1/reports/campanias-por-estado", { token });
  assert.equal(repetida.json.meta.cache, "HIT");

  const liderJti = `it-rep-lid-${Date.now()}`;
  const lider = firmar("LIDER", "USR-00005", liderJti);
  await sesion(liderJti);
  const tendencia = await pedir(reports, "/api/v1/reports/tendencia", { token: lider });
  assert.equal(tendencia.status, 200, tendencia.texto);
  assert.equal(tendencia.json.data.unidad_organizacional_id, "UO-CC-TURNO-B");
  assert.ok(tendencia.json.data.series[0].data.includes(1));
  assert.equal(JSON.stringify(tendencia.json.data).includes('"n":'), false);

  const ajena = await pedir(reports, "/api/v1/reports/tendencia", {
    token: lider,
    method: "POST",
    contentType: "application/json",
    body: JSON.stringify({ unidad_organizacional_id: "UO-LOG-TURNO-A" }),
  });
  assert.equal(ajena.status, 403);

  const xml = await pedir(reports, "/api/v1/reports/fuentes", { token, accept: "application/xml" });
  assert.equal(xml.status, 200);
  assert.match(xml.texto, /<category>/);

  const colaboradorJti = `it-rep-col-${Date.now()}`;
  await sesion(colaboradorJti);
  const sinPermiso = await pedir(reports, "/api/v1/reports/resumen", {
    token: firmar("COLABORADOR", "USR-00001", colaboradorJti),
  });
  assert.equal(sinPermiso.status, 403);

  const auditorJti = `it-rep-aud-${Date.now()}`;
  await sesion(auditorJti);
  const auditor = firmar("AUDITOR", "USR-00004", auditorJti);
  const id = `it-${Date.now()}`;
  await mongo.db("bienestar_nexum").collection("solicitudes_apoyo").insertOne({
    seudonimo_id: "SEUD-OCULTO",
    mensaje: `solicitud ${id}`,
    fecha: new Date(),
    estado: "ABIERTA",
  });
  try {
    const solicitudes = await pedir(reports, "/api/v1/reports/solicitudes-apoyo", { token: auditor });
    assert.equal(solicitudes.status, 200, solicitudes.texto);
    assert.ok(solicitudes.json.data.series[0].data.some((n) => n >= 1));
    assert.equal(JSON.stringify(solicitudes.json).includes("SEUD-OCULTO"), false);
    const lista = await pedir(queries, `/api/v1/queries/solicitudes-apoyo?search=${encodeURIComponent(id)}`, {
      token: auditor,
    });
    assert.equal(lista.status, 200, lista.texto);
    assert.equal(lista.json.data.solicitudes.length, 1);
    assert.equal(lista.json.data.solicitudes[0].seudonimo_id, undefined);
  } finally {
    await mongo.db("bienestar_nexum").collection("solicitudes_apoyo").deleteMany({ mensaje: `solicitud ${id}` });
  }
});

test("rate limit 429 con un límite bajo", { skip: !activo }, async () => {
  const jti = `it-rl-${Date.now()}`;
  const token = firmar("ADMINISTRADOR", "USR-00002", jti);
  await sesion(jti);
  const identidad = "USR-00002";
  const claves = await redis.keys(`ratelimit:queries-service:${identidad}:*`);
  if (claves.length) await redis.del(...claves);
  let ultimo = 200;
  for (let i = 0; i < 80 && ultimo !== 429; i += 1) {
    const respuesta = await pedir(queries, "/api/v1/queries/fuentes?limit=1", { token });
    ultimo = respuesta.status;
  }
  assert.equal(ultimo, 429);
});
