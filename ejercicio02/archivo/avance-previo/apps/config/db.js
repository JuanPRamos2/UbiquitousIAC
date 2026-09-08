const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: Number(process.env.DB_PORT || 5432),
  user: process.env.DB_USER || 'library',
  password: process.env.DB_PASSWORD || '666',
  database: process.env.DB_NAME || 'library',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 20000
});

pool.on('error', (err) => {
  console.error('Error inesperado en la conexión PostgreSQL', err);
});

module.exports = { pool };
