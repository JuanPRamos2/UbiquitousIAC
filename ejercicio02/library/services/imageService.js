const fs = require('fs');
const path = require('path');
const { query } = require('../config/db');
const { uploadDir } = require('../config/upload');

const addImage = async (bookId, file, { altText, isCover }) => {
  const result = await query(
    'SELECT * FROM sp_add_book_image($1, $2, $3, $4, $5, $6)',
    [bookId, file.filename, altText || '', file.mimetype, file.size, Boolean(isCover)]
  );
  return result.rows[0];
};

const deleteImage = async (bookId, imageId) => {
  const result = await query('SELECT sp_delete_book_image($1, $2) AS stored_name', [bookId, imageId]);
  const storedName = result.rows[0] && result.rows[0].stored_name;
  if (storedName) {
    const filePath = path.join(uploadDir, storedName);
    fs.unlink(filePath, () => {});
  }
};

const setCover = async (bookId, imageId) => {
  await query('SELECT sp_set_cover($1, $2)', [bookId, imageId]);
};

const updateAlt = async (imageId, altText) => {
  await query('SELECT sp_update_image_alt($1, $2)', [imageId, altText]);
};

module.exports = { addImage, deleteImage, setCover, updateAlt };
