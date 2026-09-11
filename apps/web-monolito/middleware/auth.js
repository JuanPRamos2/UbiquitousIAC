function requireAuth(req, res, next) {
  if (!req.session.user) {
    return res.redirect(`${res.locals.basePath}/login`);
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session.user) {
    return res.redirect(`${res.locals.basePath}/login`);
  }
  if (req.session.user.role !== 'admin') {
    return res.status(403).render('error/403', { title: 'Acceso denegado' });
  }
  next();
}

function requireGuest(req, res, next) {
  if (req.session.user) {
    return res.redirect(`${res.locals.basePath}/`);
  }
  next();
}

module.exports = { requireAuth, requireAdmin, requireGuest };
