import pg from "pg";
import { env } from "./env.js";

export const pgPool = new pg.Pool({
  host: env.postgres.host,
  port: env.postgres.port,
  database: env.postgres.database,
  user: env.postgres.user,
  password: env.postgres.password,
  max: env.postgres.max,
  idleTimeoutMillis: 30_000,
});

export async function pgQuery(text, params = []) {
  return pgPool.query(text, params);
}

export async function verificarPostgres() {
  const r = await pgQuery("SELECT 1 AS ok");
  return r.rows[0].ok === 1;
}
