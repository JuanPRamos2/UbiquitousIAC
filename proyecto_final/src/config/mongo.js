import { MongoClient } from "mongodb";
import { env } from "./env.js";

let client;
let db;

export async function conectarMongo() {
  if (db) {
    try {
      await db.command({ ping: 1 });
      return db;
    } catch {
      await cerrarMongo().catch(() => {});
    }
  }
  client = new MongoClient(env.mongoUrl, {
    maxPoolSize: 10,
    minPoolSize: 1,
  });
  await client.connect();
  db = client.db(env.mongoDb);
  await db.collection("solicitudes_apoyo").createIndex({ fecha: -1 });
  return db;
}

export function mongoDb() {
  if (!db) throw new Error("MongoDB no está conectado");
  return db;
}

export async function verificarMongo() {
  await conectarMongo();
  await mongoDb().command({ ping: 1 });
  return true;
}

export async function cerrarMongo() {
  const actual = client;
  client = undefined;
  db = undefined;
  if (actual) await actual.close();
}
