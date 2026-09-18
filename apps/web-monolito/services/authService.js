const bcrypt = require('bcryptjs');
const { query } = require('../config/db');
const { validatePassword } = require('../middleware/validate');

const getUserByEmail = async (email) => {
  const result = await query('SELECT * FROM users WHERE email = $1', [String(email || '').trim().toLowerCase()]);
  return result.rows[0] || null;
};

const getUserById = async (id) => {
  const result = await query(
    'SELECT id, full_name, email, role, created_at, updated_at FROM users WHERE id = $1',
    [id]
  );
  return result.rows[0] || null;
};

const listUsers = async () => {
  const result = await query(
    'SELECT id, full_name, email, role, created_at FROM users ORDER BY created_at DESC'
  );
  return result.rows;
};

const registerUser = async ({ fullName, email, password }) => {
  const passwordError = validatePassword(password);
  if (passwordError) {
    const error = new Error(passwordError);
    error.status = 400;
    error.expose = true;
    throw error;
  }

  const passwordHash = await bcrypt.hash(password, 10);
  const result = await query(
    `INSERT INTO users (full_name, email, password_hash, role)
     VALUES ($1, $2, $3, 'client')
     RETURNING id, full_name, email, role`,
    [fullName.trim(), String(email).trim().toLowerCase(), passwordHash]
  );
  const user = result.rows[0];
  return { id: user.id, full_name: user.full_name, email: user.email, role: user.role };
};

const authenticate = async (email, password) => {
  const user = await getUserByEmail(email);
  if (!user) return null;
  const ok = await bcrypt.compare(password, user.password_hash);
  if (!ok) return null;
  return { id: user.id, full_name: user.full_name, email: user.email, role: user.role };
};

const updateUserRole = async (id, role) => {
  if (!['admin', 'client'].includes(role)) {
    const error = new Error('Rol no permitido.');
    error.status = 400;
    error.expose = true;
    throw error;
  }
  const result = await query(
    'UPDATE users SET role = $1 WHERE id = $2 RETURNING id, full_name, email, role',
    [role, id]
  );
  return result.rows[0];
};

const deleteUser = async (id) => {
  await query('DELETE FROM users WHERE id = $1', [id]);
};

module.exports = {
  getUserByEmail,
  getUserById,
  listUsers,
  registerUser,
  authenticate,
  updateUserRole,
  deleteUser
};
