const { Pool } = require('pg');

const required = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'];
const missing = required.filter((name) => !process.env[name]);
if (missing.length) {
  throw new Error(
    `Faltan variables de entorno de base de datos: ${missing.join(', ')}. ` +
      'Copia .env.example a .env y ejecuta npm run setup (levanta Postgres con Docker).'
  );
}

const pool = new Pool({
  host: process.env.DB_HOST,
  port: Number(process.env.DB_PORT),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 20000
});

pool.on('error', (err) => {
  console.error('Error inesperado en el pool de PostgreSQL');
  console.error(err.message);
});

const query = (text, params) => pool.query(text, params);

module.exports = { pool, query };
