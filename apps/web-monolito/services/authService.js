const bcrypt = require('bcryptjs');
const { query } = require('../config/db');
const { validatePassword } = require('../middleware/validate');

const getUserByEmail = async (email) => {
  const result = await query('SELECT * FROM v_users WHERE email = $1', [
    String(email || '').trim().toLowerCase()
  ]);
  return result.rows[0] || null;
};

const getUserById = async (id) => {
  const result = await query(
    `SELECT id, first_name, paternal_surname, maternal_surname, full_name,
            email, role, role_id, email_verified, created_at, updated_at
     FROM v_users WHERE id = $1`,
    [id]
  );
  return result.rows[0] || null;
};

const listUsers = async () => {
  const result = await query(
    `SELECT id, first_name, paternal_surname, maternal_surname, full_name,
            email, role, email_verified, created_at
     FROM v_users ORDER BY created_at DESC`
  );
  return result.rows;
};

const splitFullName = (fullName) => {
  const parts = String(fullName || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  return {
    firstName: parts[0] || '',
    paternalSurname: parts[1] || parts[0] || '',
    maternalSurname: parts.slice(2).join(' ')
  };
};

const registerUser = async ({
  firstName,
  paternalSurname,
  maternalSurname,
  fullName,
  email,
  password
}) => {
  const passwordError = validatePassword(password);
  if (passwordError) {
    const error = new Error(passwordError);
    error.status = 400;
    error.expose = true;
    throw error;
  }

  const names = firstName
    ? {
        firstName: String(firstName).trim(),
        paternalSurname: String(paternalSurname || '').trim(),
        maternalSurname: String(maternalSurname || '').trim()
      }
    : splitFullName(fullName);

  if (!names.firstName || !names.paternalSurname) {
    const error = new Error('Nombre y apellido paterno son obligatorios.');
    error.status = 400;
    error.expose = true;
    throw error;
  }

  const passwordHash = await bcrypt.hash(password, 10);
  const result = await query(
    'SELECT * FROM sp_register_user($1, $2, $3, $4, $5, $6)',
    [
      names.firstName,
      names.paternalSurname,
      names.maternalSurname,
      String(email).trim().toLowerCase(),
      passwordHash,
      'client'
    ]
  );
  const user = result.rows[0];
  return {
    id: user.id,
    first_name: user.first_name,
    paternal_surname: user.paternal_surname,
    maternal_surname: user.maternal_surname,
    full_name: user.full_name,
    email: user.email,
    role: user.role
  };
};

const authenticate = async (email, password) => {
  const user = await getUserByEmail(email);
  if (!user) return null;
  const ok = await bcrypt.compare(password, user.password_hash);
  if (!ok) return null;
  return {
    id: user.id,
    first_name: user.first_name,
    paternal_surname: user.paternal_surname,
    maternal_surname: user.maternal_surname,
    full_name: user.full_name,
    email: user.email,
    role: user.role
  };
};

const updateUserRole = async (id, role) => {
  if (!['admin', 'client'].includes(role)) {
    const error = new Error('Rol no permitido.');
    error.status = 400;
    error.expose = true;
    throw error;
  }
  const result = await query('SELECT * FROM sp_update_user_role($1, $2)', [id, role]);
  return result.rows[0];
};

const deleteUser = async (id) => {
  await query('SELECT sp_delete_user($1)', [id]);
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
