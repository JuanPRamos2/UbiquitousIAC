/** Acceso a PostgreSQL. Las consultas SIEMPRE van parametrizadas. */
import pg from "pg";
import { postgres as cfg } from "./entorno.js";

// Una columna DATE se entrega tal como la guarda la base: "2026-08-07".
//
// Por omision, la biblioteca pg convierte DATE a un objeto Date de
// JavaScript, que al serializarse sale como "2026-08-07T00:00:00.000Z".
// Eso tiene dos consecuencias malas y ninguna buena: el contrato declara
// xs:date y la respuesta deja de validar contra el XSD, y un cliente en
// una zona horaria al poniente de UTC lee ese instante como el 6 de
// agosto, de modo que la fecha de cierre de una campania se corre un dia.
// La fecha de inicio de una campania no tiene hora ni zona: es un dia del
// calendario, y asi viaja.
pg.types.setTypeParser(1082, (valor) => valor);   // 1082 = DATE

let pool = null;

export function obtenerPool() {
  if (pool === null) {
    pool = new pg.Pool({
      host: cfg.host, port: cfg.port, database: cfg.database,
      user: cfg.user, password: cfg.password, max: cfg.max,
      // Si la base no responde se falla rapido: la sonda /health/ready del
      // llamador tiene su propio presupuesto de tiempo y no puede esperar
      // el valor por omision de la biblioteca.
      connectionTimeoutMillis: 1500,
      idleTimeoutMillis: 10000,
      application_name: process.env.NOMBRE_SERVICIO || "microservicio-node",
    });
    pool.on("error", () => { /* una conexion ociosa que muere no tumba el proceso */ });
  }
  return pool;
}

export async function pgQuery(sql, valores = []) {
  return obtenerPool().query(sql, valores);
}

export const ejecutar = pgQuery;

export async function consultar(sql, valores = []) {
  const r = await pgQuery(sql, valores);
  return r.rows;
}

export async function consultarUno(sql, valores = []) {
  const r = await pgQuery(sql, valores);
  return r.rows[0] || null;
}

/** Una transaccion real: o se aplica todo, o no se aplica nada. */
export async function enTransaccion(fn) {
  const cliente = await obtenerPool().connect();
  try {
    await cliente.query("BEGIN");
    const resultado = await fn(cliente);
    await cliente.query("COMMIT");
    return resultado;
  } catch (e) {
    await cliente.query("ROLLBACK");
    throw e;
  } finally {
    cliente.release();
  }
}

export async function ping() {
  await pgQuery("SELECT 1");
  return true;
}

export async function verificarPostgres() {
  try { await ping(); return true; } catch { return false; }
}

export async function cerrarPostgres() {
  if (pool) { await pool.end(); pool = null; }
}
