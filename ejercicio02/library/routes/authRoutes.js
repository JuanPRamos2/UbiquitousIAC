const express = require('express');
const router = express.Router();
const { requireGuest, requireAuth } = require('../middleware/auth');
const { validatePassword } = require('../middleware/validate');
const { setNotice, setError } = require('../middleware/flash');
const { friendlyDbError } = require('../services/dbErrors');
const authService = require('../services/authService');

router.get('/login', requireGuest, (req, res) => {
  res.render('auth/login', { title: 'Iniciar sesión', error: null });
});

router.post('/login', requireGuest, async (req, res, next) => {
  try {
    const user = await authService.authenticate(req.body.email, req.body.password);
    if (!user) {
      return res.status(401).render('auth/login', {
        title: 'Iniciar sesión',
        error: 'Credenciales incorrectas.'
      });
    }
    req.session.user = user;
    res.redirect(`${res.locals.basePath}/`);
  } catch (error) {
    console.error(error);
    return res.status(503).render('auth/login', {
      title: 'Iniciar sesión',
      error: 'No se pudo conectar a la base de datos. Intente de nuevo en un momento.'
    });
  }
});

router.get('/register', requireGuest, (req, res) => {
  res.render('auth/register', { title: 'Registrarse', error: null });
});

router.post('/register', requireGuest, async (req, res, next) => {
  try {
    const { full_name, email, password } = req.body;
    if (!full_name || !email || !password) {
      return res.status(400).render('auth/register', {
        title: 'Registrarse',
        error: 'Todos los campos son obligatorios.'
      });
    }
    const passwordError = validatePassword(password);
    if (passwordError) {
      return res.status(400).render('auth/register', {
        title: 'Registrarse',
        error: passwordError
      });
    }
    const user = await authService.registerUser({ fullName: full_name, email, password });
    req.session.user = user;
    setNotice(req, 'Cuenta creada. Bienvenido a la librería.');
    res.redirect(`${res.locals.basePath}/`);
  } catch (error) {
    console.error(error);
    const connectionFailed = ['ECONNREFUSED', 'ENOTFOUND', 'ETIMEDOUT', '28P01', '3D000'].includes(error.code);
    return res.status(connectionFailed ? 503 : 400).render('auth/register', {
      title: 'Registrarse',
      error: connectionFailed
        ? 'No se pudo conectar a la base de datos. Intente de nuevo en un momento.'
        : friendlyDbError(error)
    });
  }
});

router.post('/logout', requireAuth, (req, res) => {
  req.session.destroy(() => res.redirect(`${res.locals.basePath}/login`));
});

router.get('/profile', requireAuth, async (req, res, next) => {
  try {
    const user = await authService.getUserById(req.session.user.id);
    res.render('users/profile', { title: 'Mi perfil', user });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
