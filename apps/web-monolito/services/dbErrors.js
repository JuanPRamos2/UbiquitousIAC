function friendlyDbError(err) {
  const constraint = err.constraint || '';
  const message = err.message || '';

  if (err.code === 'P0001' || /Solo se permite un usuario con rol Administrador/i.test(message)) {
    return 'Ya existe un Administrador. El sistema admite como máximo uno.';
  }
  if (err.code === '23505' && /ux_users_single_admin/i.test(`${constraint} ${message}`)) {
    return 'Ya existe un Administrador. El sistema admite como máximo uno.';
  }
  if (err.code === '23505' && /isbn/i.test(`${constraint} ${message}`)) {
    return 'El ISBN ya está registrado.';
  }
  if (err.code === '23505' && /email/i.test(`${constraint} ${message}`)) {
    return 'Ya existe un usuario con ese correo.';
  }
  if (err.code === '23505' && /name/i.test(`${constraint} ${message}`)) {
    return 'Ya existe un registro con ese nombre.';
  }
  if (err.code === '23505' && /full_name/i.test(`${constraint} ${message}`)) {
    return 'Ya existe un autor con ese nombre.';
  }
  if (err.code === '23514') {
    return 'Los datos no cumplen las reglas de integridad (precio, stock, año o definición).';
  }
  if (err.code === '23503') {
    return 'No se puede completar la operación porque el registro está relacionado con otros datos.';
  }
  return 'No se pudo completar la operación.';
}

module.exports = { friendlyDbError };
