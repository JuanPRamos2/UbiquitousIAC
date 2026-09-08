const bcrypt = require('bcryptjs');
const { pool } = require('../config/db');

const getUserByEmail = async (email) => {
  const result = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
  return result.rows[0];
};

const getUserById = async (id) => {
  const result = await pool.query('SELECT * FROM users WHERE id = $1', [id]);
  return result.rows[0];
};

const listUsers = async () => {
  const result = await pool.query('SELECT * FROM users ORDER BY created_at DESC');
  return result.rows;
};

const createUser = async ({ fullName, email, password, role = 'client' }) => {
  const passwordHash = await bcrypt.hash(password, 10);
  const result = await pool.query(
    `INSERT INTO users (full_name, email, password_hash, role)
     VALUES ($1, $2, $3, $4)
     RETURNING id, full_name, email, role, created_at`,
    [fullName, email, passwordHash, role]
  );

  return result.rows[0];
};

const updateUserRole = async (id, role) => {
  const result = await pool.query(
    'UPDATE users SET role = $1 WHERE id = $2 RETURNING id, full_name, email, role',
    [role, id]
  );
  return result.rows[0];
};

const deleteUser = async (id) => {
  await pool.query('DELETE FROM users WHERE id = $1', [id]);
};

const verifyPassword = async (password, hash) => bcrypt.compare(password, hash);

module.exports = {
  getUserByEmail,
  getUserById,
  listUsers,
  createUser,
  updateUserRole,
  deleteUser,
  verifyPassword
};
