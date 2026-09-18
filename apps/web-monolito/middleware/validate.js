function asArray(value) {
  if (value === undefined || value === null || value === '') return [];
  return Array.isArray(value) ? value.filter(Boolean) : [value];
}

function toInt(value) {
  const n = Number.parseInt(value, 10);
  return Number.isInteger(n) ? n : null;
}

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function validatePassword(password) {
  if (!password || password.length < 8) {
    return 'La contraseña debe tener al menos 8 caracteres.';
  }
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
    return 'La contraseña debe incluir letras y números.';
  }
  return null;
}

function validateIsbn(isbn) {
  const value = (isbn || '').trim();
  if (!/^[0-9][0-9-]{8,16}[0-9Xx]$/.test(value) && !/^[0-9]{10,13}$/.test(value)) {
    return 'El ISBN no tiene un formato válido.';
  }
  return null;
}

function validateBookPayload(body) {
  const errors = [];
  const isbnError = validateIsbn(body.isbn);
  if (isbnError) errors.push(isbnError);
  if (!(body.title || '').trim()) errors.push('El título es obligatorio.');

  const year = toInt(body.publication_year);
  if (year === null || year < 1450 || year > 2100) {
    errors.push('El año de publicación no es válido.');
  }

  const price = toNumber(body.price);
  if (price === null || price < 0) errors.push('El precio debe ser un número mayor o igual a 0.');

  const stock = toInt(body.stock);
  if (stock === null || stock < 0) errors.push('El stock debe ser un entero mayor o igual a 0.');

  if (!toInt(body.format_id)) errors.push('Debe seleccionar un formato.');
  if (!toInt(body.category_id)) errors.push('Debe seleccionar una categoría.');

  return errors;
}

module.exports = {
  asArray,
  toInt,
  toNumber,
  validatePassword,
  validateIsbn,
  validateBookPayload
};
