/**
 * Acceso a MongoDB, con las mismas dos reglas que comun/mongo.py.
 *
 * 1. NINGUN documento puede contener empleado_id. La separacion entre
 *    identidad y respuestas vive en PostgreSQL; si el identificador de
 *    empleado llegara a MongoDB, la seudonimizacion dejaria de existir en
 *    la practica. La validacion esta aqui, en la capa de acceso, y no en
 *    cada endpoint: asi no depende de que quien escriba el siguiente
 *    servicio se acuerde de la regla.
 *
 * 2. Los indices se declaran en el codigo y se crean al arrancar. Un
 *    indice que solo existe porque alguien lo creo a mano en su maquina
 *    desaparece en el siguiente despliegue.
 */
import { MongoClient } from "mongodb";

import { mongo as cfg } from "./entorno.js";
import { ErrorApi } from "./errores.js";

export const CAMPOS_PROHIBIDOS = new Set([
  "empleado_id", "numero_empleado", "curp", "rfc",
  "nombre_empleado", "correo_empleado",
]);

let cliente = null;

export function obtenerCliente() {
  if (cliente === null) {
    // El tiempo de seleccion debe ser MENOR que el que espera quien
    // consulta /health/ready: si fuera mayor, un MongoDB caido haria que
    // la sonda no alcanzara a responder y el servicio se veria "caido" en
    // lugar de "degradado", que es informacion distinta para quien opera.
    cliente = new MongoClient(cfg.uri, {
      serverSelectionTimeoutMS: Number(process.env.MONGO_TIMEOUT_MS || 1200),
      connectTimeoutMS: 1200,
    });
  }
  return cliente;
}

export function base() {
  return obtenerCliente().db(cfg.base);
}

export async function ping() {
  await obtenerCliente().db("admin").command({ ping: 1 });
  return true;
}

export async function verificarMongo() {
  try { await ping(); return true; } catch { return false; }
}

/** Recorre el documento completo, incluidos los anidados. */
export function verificarSinIdentidad(doc, ruta = "") {
  if (!doc || typeof doc !== "object") return;
  for (const [clave, valor] of Object.entries(doc)) {
    const completa = ruta ? `${ruta}.${clave}` : clave;
    if (CAMPOS_PROHIBIDOS.has(String(clave).toLowerCase())) {
      throw new ErrorApi("CAMPO_PROHIBIDO",
        `El campo '${completa}' no puede almacenarse en MongoDB: rompe la ` +
        `separacion entre identidad y respuestas.`, 422,
        [{ campo: completa, problema: "identificador directo de persona" }]);
    }
    if (Array.isArray(valor)) {
      valor.forEach((item, i) => {
        if (item && typeof item === "object") verificarSinIdentidad(item, `${completa}[${i}]`);
      });
    } else if (valor && typeof valor === "object" && !(valor instanceof Date)) {
      verificarSinIdentidad(valor, completa);
    }
  }
}

/** definiciones: { coleccion: [ [llaves, opciones], ... ] } */
export async function asegurarIndices(definiciones) {
  const db = base();
  const creados = [];
  for (const [coleccion, indices] of Object.entries(definiciones)) {
    for (const [llaves, opciones] of indices) {
      const nombre = await db.collection(coleccion).createIndex(llaves, opciones || {});
      creados.push(`${coleccion}.${nombre}`);
    }
  }
  return creados;
}

export async function cerrarMongo() {
  if (cliente) { await cliente.close(); cliente = null; }
}
