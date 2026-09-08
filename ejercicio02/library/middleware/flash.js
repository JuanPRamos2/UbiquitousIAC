function flash(req, res, next) {
  res.locals.notice = req.session.notice || null;
  res.locals.errorMessage = req.session.errorMessage || null;
  delete req.session.notice;
  delete req.session.errorMessage;
  next();
}

function setNotice(req, message) {
  req.session.notice = message;
}

function setError(req, message) {
  req.session.errorMessage = message;
}

module.exports = { flash, setNotice, setError };
