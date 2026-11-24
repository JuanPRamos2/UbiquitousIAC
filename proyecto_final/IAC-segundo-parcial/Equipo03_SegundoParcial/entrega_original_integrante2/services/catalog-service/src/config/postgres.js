import pg from "pg";
import { config } from "./env.js";

export const pgPool = new pg.Pool({
  host: config.postgres.host,
  port: config.postgres.port,
  database: config.postgres.database,
  user: config.postgres.user,
  password: config.postgres.password,
  max: config.postgres.max,
  idleTimeoutMillis: 30_000,
});

export async function pgQuery(text, params = []) {
  return pgPool.query(text, params);
}

export async function verificarPostgres() {
  try {
    const r = await pgQuery("SELECT 1 AS ok");
    return r.rows[0]?.ok === 1;
  } catch {
    return false;
  }
}
