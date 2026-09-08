function notFound(req, res) {
  res.status(404).render('error/404', { title: 'Página no encontrada' });
}

function errorHandler(err, req, res, next) {
  if (res.headersSent) {
    return next(err);
  }

  if (err.code === 'LIMIT_FILE_SIZE') {
    err.status = 400;
    err.expose = true;
    err.message = 'El archivo excede el tamaño máximo de 5 MB.';
  }

  console.error(err.message);

  const status = err.status || err.statusCode || 500;
  const expose = Boolean(err.expose) && status < 500;
  const message = expose ? err.message : 'Ocurrió un error al procesar la solicitud.';

  if (req.accepts('html')) {
    return res.status(status).render('error/500', {
      title: 'Error',
      message
    });
  }

  res.status(status).type('text').send(message);
}

module.exports = { notFound, errorHandler };
