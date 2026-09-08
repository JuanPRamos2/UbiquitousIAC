const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const { getUserByEmail, createUser, getUserById } = require('../models/userModel');

router.get('/login', (req, res) => {
  res.render('auth/login', { title: 'Iniciar sesión', error: null });
});

router.post('/login', async (req, res) => {
  const { email, password } = req.body;
  const user = await getUserByEmail(email);

  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).render('auth/login', {
      title: 'Iniciar sesión',
      error: 'Credenciales incorrectas.'
    });
  }

  req.session.user = {
    id: user.id,
    full_name: user.full_name,
    email: user.email,
    role: user.role
  };

  res.redirect('/');
});

router.get('/register', (req, res) => {
  res.render('auth/register', { title: 'Registrarse', error: null });
});

router.post('/register', async (req, res) => {
  const { full_name, email, password } = req.body;

  if (!full_name || !email || !password) {
    return res.status(400).render('auth/register', {
      title: 'Registrarse',
      error: 'Todos los campos son obligatorios.'
    });
  }

  const existing = await getUserByEmail(email);
  if (existing) {
    return res.status(409).render('auth/register', {
      title: 'Registrarse',
      error: 'Ya existe un usuario con ese correo.'
    });
  }

  const user = await createUser({ fullName: full_name, email, password, role: 'client' });
  req.session.user = { id: user.id, full_name: user.full_name, email: user.email, role: user.role };
  res.redirect('/');
});

router.post('/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/login'));
});

router.get('/profile', async (req, res) => {
  if (!req.session.user) return res.redirect('/login');
  const user = await getUserById(req.session.user.id);
  res.render('users/profile', { title: 'Mi perfil', user });
});

module.exports = router;
